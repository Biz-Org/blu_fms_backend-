# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .constants import FINDING_STATES, SEVERITY_LEVELS


class FireSafetyFinding(models.Model):
    _name = "fire.safety.finding"
    _description = "Fire & Safety Finding"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "id desc"
    _check_company_auto = True
    _fs_state_transitions = {
        "open": {"in_progress"},
        "in_progress": {"closed", "open"},
        "closed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    inspection_id = fields.Many2one(
        "fire.safety.inspection",
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Canonical inspection origin. Optional when the finding comes from an incident.",
    )
    line_id = fields.Many2one("fire.safety.inspection.line", ondelete="set null")
    incident_id = fields.Many2one("fire.safety.incident", ondelete="set null", index=True)
    severity = fields.Selection(SEVERITY_LEVELS, default="medium", required=True, tracking=True)
    state = fields.Selection(
        FINDING_STATES,
        default="open",
        required=True,
        tracking=True,
        index=True,
    )
    description = fields.Html()
    evidence_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_finding_attachment_rel",
        "finding_id",
        "attachment_id",
        string="Evidence",
    )
    action_ids = fields.One2many("fire.safety.action", "finding_id")
    action_count = fields.Integer(compute="_compute_action_count")

    @api.depends("action_ids")
    def _compute_action_count(self):
        for record in self:
            record.action_count = len(record.action_ids)

    @api.constrains("inspection_id", "incident_id")
    def _check_finding_origin(self):
        for record in self:
            if not record.inspection_id and not record.incident_id:
                raise ValidationError(
                    _("A finding must belong to an inspection or an incident.")
                )

    def _fs_copy_scope_from(self, origin):
        if not origin or self.property_id:
            return
        self.write(
            {
                "company_id": origin.company_id.id,
                "property_id": origin.property_id.id,
                "building_id": origin.building_id.id,
                "area_id": origin.area_id.id,
                "assigned_user_id": origin.assigned_user_id.id,
            }
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._fs_copy_scope_from(record.inspection_id or record.incident_id)
        return records

    def action_mark_in_progress(self):
        self._fs_require_safety_manager()
        self._fs_set_state("in_progress")
        return True

    def action_close_finding(self):
        self._fs_require_safety_manager()
        open_actions = self.action_ids.filtered(lambda act: act.state != "closed")
        if open_actions:
            raise UserError(_("Close all corrective actions before closing the finding."))
        self._fs_set_state("closed")
        return True
