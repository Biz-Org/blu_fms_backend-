# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import ACTION_STATES


class FireSafetyAction(models.Model):
    _name = "fire.safety.action"
    _description = "Fire & Safety Corrective Action"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "deadline, id"
    _check_company_auto = True
    _fs_state_transitions = {
        "open": {"done"},
        "done": {"closed", "open"},
        "closed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    finding_id = fields.Many2one(
        "fire.safety.finding",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    inspection_id = fields.Many2one(
        related="finding_id.inspection_id",
        store=True,
        index=True,
    )
    incident_id = fields.Many2one(
        related="finding_id.incident_id",
        store=True,
        index=True,
    )
    description = fields.Html()
    deadline = fields.Date(required=True, tracking=True, index=True)
    state = fields.Selection(
        ACTION_STATES,
        default="open",
        required=True,
        tracking=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    verification_notes = fields.Text()
    verified_by_id = fields.Many2one("res.users", readonly=True)
    verified_datetime = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)
    closed_datetime = fields.Datetime(readonly=True)
    evidence_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_action_attachment_rel",
        "action_id",
        "attachment_id",
        string="Evidence",
    )

    @api.depends("deadline", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = record.state != "closed" and bool(record.deadline) and record.deadline < today

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        overdue_domain = [("state", "!=", "closed"), ("deadline", "<", today)]
        if (operator in ("=", "==") and value) or (operator in ("!=", "<>") and not value):
            return overdue_domain
        return ["!"] + overdue_domain

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            finding = record.finding_id
            vals = {}
            if finding and not record.property_id:
                vals.update(
                    {
                        "company_id": finding.company_id.id,
                        "property_id": finding.property_id.id,
                        "building_id": finding.building_id.id,
                        "area_id": finding.area_id.id,
                    }
                )
            if finding and not record.assigned_user_id:
                vals["assigned_user_id"] = finding.assigned_user_id.id
            if vals:
                record.write(vals)
            if finding.state == "open":
                finding.action_mark_in_progress()
        return records

    def action_mark_done(self):
        for record in self:
            if not self.env.su and not (
                self.env.user._fs_is_safety_manager()
                or record.assigned_user_id == self.env.user
            ):
                raise AccessError(_("Only the assignee or a Safety Manager can mark this action done."))
        self._fs_set_state("done")
        return True

    def action_reopen(self):
        self._fs_require_safety_manager()
        self._fs_set_state("open")
        return True

    def action_verify(self):
        self._fs_require_safety_manager(
            _("Only a Safety Manager can verify corrective actions.")
        )
        for record in self:
            if record.state != "done":
                raise UserError(_("Mark the corrective action done before verification."))
            if record.assigned_user_id and record.assigned_user_id == self.env.user and not self.env.su:
                raise AccessError(
                    _("A Safety Manager cannot verify their own corrective action.")
                )
        self.write(
            {
                "verified_by_id": self.env.user.id,
                "verified_datetime": fields.Datetime.now(),
            }
        )
        return True

    def action_close(self):
        self._fs_require_safety_manager(
            _("Only a Safety Manager can close corrective actions.")
        )
        for record in self:
            if record.state != "done":
                raise UserError(_("Verify the completed corrective action before closure."))
            if not record.verified_by_id:
                raise UserError(_("Verification is required before closing a corrective action."))
        self._fs_set_state("closed")
        self.write(
            {
                "closed_by_id": self.env.user.id,
                "closed_datetime": fields.Datetime.now(),
            }
        )
        return True
