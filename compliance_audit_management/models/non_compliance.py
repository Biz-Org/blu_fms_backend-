# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import NC_STATES, SEVERITY_LEVELS


class ComplianceNonCompliance(models.Model):
    _name = "compliance.non.compliance"
    _description = "Non-Compliance Issue"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "id desc"
    _check_company_auto = True
    _ca_state_transitions = {
        "open": {"assigned", "in_progress", "closed"},
        "assigned": {"in_progress", "open"},
        "in_progress": {"pending_verification", "assigned"},
        "pending_verification": {"resolved", "in_progress"},
        "resolved": {"closed", "in_progress"},
        "closed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    description = fields.Html()
    source = fields.Selection(
        [
            ("check", "Compliance Check"),
            ("audit", "Audit"),
            ("inspection", "Inspection"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
        tracking=True,
    )
    severity = fields.Selection(SEVERITY_LEVELS, default="medium", required=True, tracking=True)
    root_cause = fields.Text()
    internal_notes = fields.Text()
    due_date = fields.Date(tracking=True, index=True)
    state = fields.Selection(
        NC_STATES,
        default="open",
        required=True,
        tracking=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    requirement_id = fields.Many2one("compliance.requirement", ondelete="restrict", index=True)
    finding_id = fields.Many2one("compliance.finding", ondelete="set null", index=True)
    check_id = fields.Many2one("compliance.check", ondelete="set null", index=True)
    audit_id = fields.Many2one("compliance.audit", ondelete="set null", index=True)
    action_ids = fields.One2many("compliance.action", "non_compliance_id")
    action_count = fields.Integer(compute="_compute_action_count")
    evidence_ids = fields.Many2many(
        "ir.attachment",
        "compliance_nc_attachment_rel",
        "nc_id",
        "attachment_id",
        string="Evidence",
    )
    closed_by_id = fields.Many2one("res.users", readonly=True)
    closed_datetime = fields.Datetime(readonly=True)

    @api.depends("action_ids")
    def _compute_action_count(self):
        for record in self:
            record.action_count = len(record.action_ids)

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        open_states = {"open", "assigned", "in_progress", "pending_verification"}
        for record in self:
            record.is_overdue = (
                record.state in open_states
                and bool(record.due_date)
                and record.due_date < today
            )

    def _search_is_overdue(self, operator, value):
        # Odoo 19 rewrites Boolean '=' to 'in' [True] (False → 'not in').
        if operator != "in":
            return NotImplemented
        today = fields.Date.context_today(self)
        return [
            ("state", "in", ["open", "assigned", "in_progress", "pending_verification"]),
            ("due_date", "<", today),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = (
                    self.env["ir.sequence"].next_by_code("compliance.non.compliance") or _("New")
                )
            if not vals.get("source"):
                if vals.get("audit_id"):
                    vals["source"] = "audit"
                elif vals.get("check_id"):
                    vals["source"] = "check"
        records = super().create(vals_list)
        for record in records:
            if record.assigned_user_id and record.state == "open":
                record._ca_set_state("assigned")
        return records

    def write(self, vals):
        res = super().write(vals)
        if "assigned_user_id" in vals and vals.get("assigned_user_id"):
            to_assign = self.filtered(lambda rec: rec.state == "open")
            if to_assign:
                to_assign._ca_set_state("assigned")
        return res

    def action_assign(self):
        self._ca_require_manager()
        for record in self:
            if not record.assigned_user_id:
                raise UserError(_("Set an assignee before assigning the issue."))
        self._ca_set_state("assigned")
        return True

    def action_start(self):
        self._ca_require_manager()
        self._ca_set_state("in_progress")
        return True

    def action_submit_verification(self):
        self._ca_require_manager()
        for record in self:
            open_actions = record.action_ids.filtered(
                lambda act: act.state not in ("verified", "closed")
            )
            if open_actions:
                raise UserError(
                    _("Complete and verify corrective actions before requesting verification.")
                )
        self._ca_set_state("pending_verification")
        return True

    def action_resolve(self):
        self._ca_require_manager()
        self._ca_set_state("resolved")
        return True

    def action_close(self):
        self._ca_require_manager()
        for record in self:
            open_actions = record.action_ids.filtered(lambda act: act.state != "closed")
            if open_actions:
                raise UserError(_("Close all corrective actions before closing the issue."))
        self.write(
            {
                "closed_by_id": self.env.user.id,
                "closed_datetime": fields.Datetime.now(),
            }
        )
        self._ca_set_state("closed")
        return True

    @api.model
    def get_nc_kpis(self):
        """KPI strip for the Non-Compliance OWL screen."""
        today = fields.Date.context_today(self)
        open_states = ["open", "assigned", "in_progress", "pending_verification"]
        open_count = self.search_count([("state", "in", open_states)])
        overdue = self.search_count(
            [
                ("state", "in", open_states),
                ("due_date", "<", today),
            ]
        )
        pending_verification = self.search_count([("state", "=", "pending_verification")])
        high_severity = self.search_count(
            [
                ("state", "in", open_states),
                ("severity", "in", ["high", "critical"]),
            ]
        )
        return {
            "open": open_count,
            "overdue": overdue,
            "pending_verification": pending_verification,
            "high_severity": high_severity,
        }
