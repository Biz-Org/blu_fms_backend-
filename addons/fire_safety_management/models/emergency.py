# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .constants import EMERGENCY_STATES, EMERGENCY_TYPES, SEVERITY_LEVELS, XMLID_SAFETY_MANAGER, XMLID_SECURITY


class FireSafetyEmergencyEvent(models.Model):
    _name = "fire.safety.emergency.event"
    _description = "Fire & Safety Emergency Timeline Event"
    _order = "event_datetime desc, id desc"

    emergency_id = fields.Many2one(
        "fire.safety.emergency",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="emergency_id.company_id", store=True, index=True)
    event_datetime = fields.Datetime(required=True, default=fields.Datetime.now)
    name = fields.Char(required=True)
    description = fields.Text()
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)


class FireSafetyEmergency(models.Model):
    _name = "fire.safety.emergency"
    _description = "Fire & Safety Emergency"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "activation_datetime desc, id desc"
    _check_company_auto = True
    _fs_state_transitions = {
        "active": {"closed"},
        "closed": set(),
    }

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    emergency_type = fields.Selection(EMERGENCY_TYPES, required=True, tracking=True)
    severity = fields.Selection(
        SEVERITY_LEVELS,
        required=True,
        default="high",
        tracking=True,
    )
    state = fields.Selection(
        EMERGENCY_STATES,
        default="active",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    location_detail = fields.Char()
    information = fields.Html()
    response_team = fields.Char(
        help="FUTURE / NOT IMPLEMENTED: Command Center (#33) response-team reference.",
    )
    command_center_ref = fields.Char(
        help="FUTURE / NOT IMPLEMENTED: Command Center (#33) integration reference.",
    )
    activation_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    closed_datetime = fields.Datetime(readonly=True)
    outcome = fields.Html()
    event_ids = fields.One2many("fire.safety.emergency.event", "emergency_id")
    activated_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("fire.safety.emergency") or "New"
            vals.setdefault("state", "active")
        records = super().create(vals_list)
        for record in records.filtered(lambda rec: rec.state == "active"):
            record._log_event(_("Emergency activated"))
        return records

    @api.constrains("state", "company_id")
    def _constrain_single_active(self):
        self._check_single_active()

    def _check_single_active(self):
        companies = self.mapped("company_id")
        Emergency = self.env["fire.safety.emergency"].sudo()
        for company in companies:
            active = Emergency.search_count(
                [("company_id", "=", company.id), ("state", "=", "active")]
            )
            if active > 1:
                raise ValidationError(
                    _("Only one active emergency is allowed per company.")
                )

    def _log_event(self, name, description=None):
        Event = self.env["fire.safety.emergency.event"]
        for record in self:
            Event.create(
                {
                    "emergency_id": record.id,
                    "name": name,
                    "description": description,
                }
            )

    @api.model
    def action_activate_emergency(self, vals):
        """Mobile-ready emergency activation. Enforces one active emergency per company."""
        self._fs_require_groups(
            [XMLID_SAFETY_MANAGER, XMLID_SECURITY],
            _("Only Safety Manager or Security can activate an emergency."),
        )
        payload = dict(vals or {})
        payload.setdefault("company_id", self.env.company.id)
        payload.setdefault("activated_by_id", self.env.user.id)
        payload["state"] = "active"
        emergency = self.create(payload)
        emergency._notify_activation()
        return emergency

    def _notify_activation(self):
        template = self.env.ref(
            "fire_safety_management.mail_template_emergency_activate",
            raise_if_not_found=False,
        )
        for record in self:
            if template:
                record.message_post_with_source(
                    template,
                    subtype_xmlid="mail.mt_comment",
                )
            else:
                record.message_post(
                    body=_("Emergency %(name)s has been activated.") % {"name": record.name},
                    subtype_xmlid="mail.mt_comment",
                )

    def action_close_emergency(self, outcome=None):
        self._fs_require_safety_manager(_("Only a Safety Manager can close an emergency."))
        if outcome:
            self.write({"outcome": outcome})
        self._fs_set_state("closed")
        self.write({"closed_datetime": fields.Datetime.now()})
        self._log_event(_("Emergency closed"), outcome)
        return True
