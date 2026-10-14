# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

from .constants import (
    INCIDENT_STATES,
    INCIDENT_TYPES,
    SEVERITY_LEVELS,
    XMLID_GUARD,
    XMLID_SAFETY_MANAGER,
    XMLID_SECURITY,
)


class FireSafetyIncidentPerson(models.Model):
    _name = "fire.safety.incident.person"
    _description = "Person Involved in a Fire & Safety Incident"

    incident_id = fields.Many2one(
        "fire.safety.incident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="incident_id.company_id", store=True, index=True)
    name = fields.Char(required=True)
    role = fields.Char()
    contact = fields.Char()
    notes = fields.Text()


class FireSafetyIncident(models.Model):
    _name = "fire.safety.incident"
    _description = "Fire & Safety Incident"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "incident_datetime desc, id desc"
    _check_company_auto = True
    _fs_state_transitions = {
        "open": {"investigating"},
        "investigating": {"resolved", "open"},
        "resolved": set(),
    }

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    incident_type = fields.Selection(
        INCIDENT_TYPES,
        required=True,
        tracking=True,
        index=True,
    )
    severity = fields.Selection(
        SEVERITY_LEVELS,
        required=True,
        default="medium",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        INCIDENT_STATES,
        default="open",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    incident_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
    )
    location_detail = fields.Char()
    description = fields.Html(required=True)
    immediate_action = fields.Html()
    reported_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
        index=True,
    )
    person_ids = fields.One2many("fire.safety.incident.person", "incident_id")
    investigation_notes = fields.Html()
    root_cause = fields.Html()
    finding_ids = fields.One2many("fire.safety.finding", "incident_id")
    resolved_datetime = fields.Datetime(readonly=True)
    evidence_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_incident_attachment_rel",
        "incident_id",
        "attachment_id",
        string="Evidence",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("fire.safety.incident") or "New"
            if not vals.get("reported_by_id"):
                vals["reported_by_id"] = self.env.user.id
        return super().create(vals_list)

    @api.model
    def action_report_incident(self, vals):
        """Mobile-ready incident report used by web and future Operations app."""
        user = self.env.user
        if not self.env.su and not user._fs_has_fs_access():
            raise AccessError(_("You cannot report a Fire & Safety incident."))
        allowed = [XMLID_SAFETY_MANAGER, XMLID_SECURITY, XMLID_GUARD]
        if not self.env.su and not any(user.has_group(xmlid) for xmlid in allowed):
            raise AccessError(_("Your role cannot report Fire & Safety incidents."))
        payload = dict(vals or {})
        payload.setdefault("reported_by_id", user.id)
        payload.setdefault("assigned_user_id", user.id)
        payload.setdefault("state", "open")
        return self.create(payload)

    def action_start_investigation(self):
        self._fs_require_groups(
            [XMLID_SAFETY_MANAGER, XMLID_SECURITY],
            _("Only Safety Manager or Security can investigate incidents."),
        )
        self._fs_set_state("investigating")
        return True

    def action_resolve_incident(self):
        self._fs_require_safety_manager(_("Only a Safety Manager can resolve an incident."))
        self._fs_set_state("resolved")
        self.write({"resolved_datetime": fields.Datetime.now()})
        return True
