# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import DOCUMENT_STATES, DOCUMENT_TYPES, RENEWAL_REMINDERS


class ComplianceDocument(models.Model):
    _name = "compliance.document"
    _description = "Compliance Document"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "expiry_date, name"
    _check_company_auto = True
    _ca_state_transitions = {
        "active": {"expiring_soon", "renewal_due", "under_renewal", "expired", "archived"},
        "expiring_soon": {"active", "renewal_due", "under_renewal", "expired", "archived"},
        "renewal_due": {"under_renewal", "expired", "active", "archived"},
        "under_renewal": {"renewed", "expired", "active", "archived"},
        "expired": {"under_renewal", "renewed", "archived"},
        "renewed": {"active", "archived"},
        "archived": set(),
    }

    name = fields.Char(required=True, tracking=True)
    document_type = fields.Selection(DOCUMENT_TYPES, required=True, default="certificate", tracking=True)
    issuing_authority = fields.Char()
    requirement_id = fields.Many2one(
        "compliance.requirement",
        ondelete="set null",
        index=True,
        check_company=True,
    )
    issue_date = fields.Date()
    expiry_date = fields.Date(required=True, tracking=True, index=True)
    renewal_reminder_days = fields.Selection(
        RENEWAL_REMINDERS,
        default="60",
        required=True,
        string="Renewal Reminder",
    )
    state = fields.Selection(
        DOCUMENT_STATES,
        default="active",
        required=True,
        tracking=True,
        index=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_document_attachment_rel",
        "document_id",
        "attachment_id",
        string="Files",
    )
    history_ids = fields.One2many("compliance.document.history", "document_id")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ca_refresh_expiry_state()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(key in vals for key in ("expiry_date", "renewal_reminder_days", "state")):
            if "state" not in vals or self.env.context.get("ca_refresh_expiry"):
                self._ca_refresh_expiry_state()
        return res

    def _ca_refresh_expiry_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ("archived", "under_renewal", "renewed"):
                continue
            reminder_days = int(record.renewal_reminder_days or "60")
            warn_date = record.expiry_date - relativedelta(days=reminder_days)
            if record.expiry_date < today:
                target = "expired"
            elif today >= warn_date:
                target = "expiring_soon" if (record.expiry_date - today).days > 7 else "renewal_due"
            else:
                target = "active"
            if record.state != target:
                record.with_context(ca_allow_state_write=True, ca_refresh_expiry=True).write(
                    {"state": target}
                )


    def action_start_renewal(self):
        self._ca_require_manager()
        self._ca_set_state("under_renewal")
        return True

    def action_mark_renewed(self, new_expiry_date=None, attachment_ids=None):
        self._ca_require_manager()
        for record in self:
            History = self.env["compliance.document.history"]
            History.create(
                {
                    "document_id": record.id,
                    "event_type": "renewed",
                    "previous_expiry_date": record.expiry_date,
                    "new_expiry_date": new_expiry_date or record.expiry_date,
                    "attachment_ids": [(6, 0, attachment_ids or [])],
                    "note": _("Document renewed"),
                }
            )
            vals = {"state": "renewed"}
            if new_expiry_date:
                vals["expiry_date"] = new_expiry_date
            if attachment_ids:
                vals["attachment_ids"] = [(6, 0, attachment_ids)]
            record.with_context(ca_allow_state_write=True).write(vals)
            record.with_context(ca_allow_state_write=True).write({"state": "active"})
        return True

    def action_archive(self):
        self._ca_require_manager()
        self.env["compliance.document.history"].create(
            [
                {
                    "document_id": record.id,
                    "event_type": "archived",
                    "previous_expiry_date": record.expiry_date,
                    "note": _("Document archived"),
                }
                for record in self
            ]
        )
        self._ca_set_state("archived")
        return True

    @api.model
    def _cron_refresh_document_states(self):
        docs = self.search([("state", "not in", ["archived", "under_renewal"])])
        docs._ca_refresh_expiry_state()
        return True

    @api.model
    def get_document_kpis(self):
        """KPI strip for the Compliance Documents OWL screen."""
        return {
            "active": self.search_count([("state", "=", "active")]),
            "expiring_soon": self.search_count([("state", "=", "expiring_soon")]),
            "renewal_due": self.search_count([("state", "=", "renewal_due")]),
            "expired": self.search_count([("state", "=", "expired")]),
        }


class ComplianceDocumentHistory(models.Model):
    _name = "compliance.document.history"
    _description = "Compliance Document History"
    _order = "create_date desc, id desc"

    document_id = fields.Many2one(
        "compliance.document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="document_id.company_id", store=True, index=True)
    event_type = fields.Selection(
        [
            ("created", "Created"),
            ("renewed", "Renewed"),
            ("archived", "Archived"),
            ("updated", "Updated"),
        ],
        required=True,
        default="updated",
    )
    previous_expiry_date = fields.Date()
    new_expiry_date = fields.Date()
    note = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_document_history_attachment_rel",
        "history_id",
        "attachment_id",
    )
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
