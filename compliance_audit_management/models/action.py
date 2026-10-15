# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import ACTION_STATES


class ComplianceAction(models.Model):
    _name = "compliance.action"
    _description = "Compliance Corrective Action"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "deadline, id"
    _check_company_auto = True
    _ca_state_transitions = {
        "open": {"in_progress"},
        "in_progress": {"pending_verification", "open"},
        "pending_verification": {"verified", "in_progress"},
        "verified": {"closed"},
        "closed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    non_compliance_id = fields.Many2one(
        "compliance.non.compliance",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
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
        "compliance_action_attachment_rel",
        "action_id",
        "attachment_id",
        string="Evidence",
    )

    @api.depends("deadline", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = (
                record.state not in ("verified", "closed")
                and bool(record.deadline)
                and record.deadline < today
            )

    def _search_is_overdue(self, operator, value):
        # Odoo 19 rewrites Boolean '=' to 'in' [True] (False → 'not in').
        if operator != "in":
            return NotImplemented
        today = fields.Date.context_today(self)
        return [
            ("state", "not in", ["verified", "closed"]),
            ("deadline", "<", today),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._ca_copy_scope_from(record.non_compliance_id)
            nc = record.non_compliance_id
            if nc.state == "open" and nc.assigned_user_id:
                nc._ca_set_state("assigned")
            elif nc.state in ("open", "assigned") and record:
                pass
        return records

    def action_start(self):
        self._ca_require_manager()
        self._ca_set_state("in_progress")
        nc = self.mapped("non_compliance_id").filtered(lambda r: r.state in ("open", "assigned"))
        if nc:
            nc._ca_set_state("in_progress")
        return True

    def action_submit_verification(self):
        self._ca_require_manager()
        self._ca_set_state("pending_verification")
        return True

    def action_verify(self):
        self._ca_require_manager()
        for record in self:
            if record.assigned_user_id == self.env.user and not self.env.su:
                raise AccessError(
                    _("You cannot verify a corrective action assigned to yourself.")
                )
        self.write(
            {
                "verified_by_id": self.env.user.id,
                "verified_datetime": fields.Datetime.now(),
            }
        )
        self._ca_set_state("verified")
        return True

    def action_close(self):
        self._ca_require_manager()
        for record in self:
            if record.state != "verified":
                raise UserError(_("Verify the corrective action before closing it."))
        self.write(
            {
                "closed_by_id": self.env.user.id,
                "closed_datetime": fields.Datetime.now(),
            }
        )
        self._ca_set_state("closed")
        return True
