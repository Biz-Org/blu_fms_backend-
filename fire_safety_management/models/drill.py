# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import DRILL_STATES, DRILL_TYPES


class FireSafetyDrill(models.Model):
    _name = "fire.safety.drill"
    _description = "Fire & Safety Mock Drill"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "scheduled_datetime desc, id desc"
    _check_company_auto = True
    _fs_state_transitions = {
        "scheduled": {"completed", "cancelled", "rescheduled"},
        "rescheduled": {"scheduled", "completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    name = fields.Char(required=True, tracking=True)
    drill_type = fields.Selection(DRILL_TYPES, required=True, tracking=True, index=True)
    state = fields.Selection(
        DRILL_STATES,
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    scheduled_datetime = fields.Datetime(required=True, tracking=True, index=True)
    scheduled_date = fields.Date(compute="_compute_scheduled_date", store=True, index=True)
    conducted_by = fields.Char(
        required=True,
        default="Internal Safety Team",
        tracking=True,
    )
    expected_participants = fields.Integer(default=0)
    target_participation = fields.Float(
        default=100.0,
        help="Target participation percentage. Default is 100%.",
    )
    description = fields.Html()
    participant_ids = fields.Many2many(
        "res.users",
        "fire_safety_drill_participant_rel",
        "drill_id",
        "user_id",
        string="Participants / Users",
    )
    attendance_count = fields.Integer()
    participation_rate = fields.Float(compute="_compute_participation_rate", store=True)
    response_time_minutes = fields.Float()
    observations = fields.Html()
    issues = fields.Html()
    completed_datetime = fields.Datetime(readonly=True)
    cancelled_reason = fields.Text()

    @api.depends("scheduled_datetime")
    def _compute_scheduled_date(self):
        for record in self:
            record.scheduled_date = (
                fields.Date.to_date(record.scheduled_datetime) if record.scheduled_datetime else False
            )

    @api.depends("attendance_count", "expected_participants")
    def _compute_participation_rate(self):
        for record in self:
            if record.expected_participants:
                record.participation_rate = (
                    record.attendance_count / record.expected_participants
                ) * 100.0
            else:
                record.participation_rate = 0.0

    def action_notify_participants(self):
        template = self.env.ref(
            "fire_safety_management.mail_template_drill_notify",
            raise_if_not_found=False,
        )
        for record in self:
            partners = record.participant_ids.mapped("partner_id")
            if template:
                record.message_post_with_source(
                    template,
                    subtype_xmlid="mail.mt_comment",
                )
            elif partners:
                record.message_post(
                    body=_("Mock drill %(name)s is scheduled for %(when)s.")
                    % {"name": record.name, "when": record.scheduled_datetime},
                    partner_ids=partners.ids,
                    subtype_xmlid="mail.mt_comment",
                )
        return True

    def action_complete_drill(self, vals=None):
        self._fs_require_safety_manager(_("Only a Safety Manager can complete a mock drill."))
        payload = dict(vals or {})
        payload["completed_datetime"] = fields.Datetime.now()
        self.write(payload)
        self._fs_set_state("completed")
        return True

    def action_cancel_drill(self, reason=None):
        self._fs_require_safety_manager(_("Only a Safety Manager can cancel a mock drill."))
        if reason:
            self.write({"cancelled_reason": reason})
        self._fs_set_state("cancelled")
        return True

    def action_reschedule_drill(self, new_datetime):
        self._fs_require_safety_manager(_("Only a Safety Manager can reschedule a mock drill."))
        if not new_datetime:
            raise UserError(_("A new date/time is required to reschedule."))
        self.write({"scheduled_datetime": new_datetime})
        self._fs_set_state("rescheduled")
        self.action_notify_participants()
        return True

    def action_open_reschedule(self):
        self.ensure_one()
        self._fs_require_safety_manager(_("Only a Safety Manager can reschedule a mock drill."))
        return {
            "type": "ir.actions.act_window",
            "name": "Reschedule Mock Drill",
            "res_model": "fire.safety.drill.reschedule",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_drill_id": self.id,
                "default_new_datetime": self.scheduled_datetime,
            },
        }

    def action_confirm_reschedule(self):
        self._fs_require_safety_manager()
        self._fs_set_state("scheduled")
        return True
