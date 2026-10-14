# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .constants import LIGHTING_ACTIONS, SCHEDULE_KINDS


class IntegrationIotSchedule(models.Model):
    _name = "integration.iot.schedule"
    _description = "Building System Schedule"
    _inherit = ["mail.thread", "integration.iot.scoped.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    system_kind = fields.Selection(SCHEDULE_KINDS, required=True, default="lighting", index=True)
    device_id = fields.Many2one("integration.iot.device", ondelete="cascade", index=True)
    lighting_action = fields.Selection(LIGHTING_ACTIONS, default="turn_on")
    hvac_mode = fields.Selection(related="device_id.hvac_mode", readonly=False)
    hvac_setpoint = fields.Float(digits=(5, 1))
    start_time = fields.Float(required=True, help="Hours from midnight, e.g. 18.0 for 18:00")
    end_time = fields.Float(required=True)
    active = fields.Boolean(default=True, tracking=True)
    day_mon = fields.Boolean(default=True)
    day_tue = fields.Boolean(default=True)
    day_wed = fields.Boolean(default=True)
    day_thu = fields.Boolean(default=True)
    day_fri = fields.Boolean(default=True)
    day_sat = fields.Boolean(default=True)
    day_sun = fields.Boolean(default=True)
    last_run = fields.Datetime(readonly=True)

    @api.constrains("start_time", "end_time")
    def _iot_check_times(self):
        for record in self:
            if not (0 <= record.start_time <= 24 and 0 <= record.end_time <= 24):
                raise ValidationError(_("Schedule times must be between 00:00 and 24:00."))

    def _iot_weekday_flags(self):
        self.ensure_one()
        return {
            0: self.day_mon,
            1: self.day_tue,
            2: self.day_wed,
            3: self.day_thu,
            4: self.day_fri,
            5: self.day_sat,
            6: self.day_sun,
        }

    def _iot_applies_now(self, when):
        self.ensure_one()
        if not self.active:
            return False
        if not self._iot_weekday_flags().get(when.weekday(), False):
            return False
        current = when.hour + when.minute / 60.0
        if self.start_time <= self.end_time:
            return self.start_time <= current < self.end_time
        return current >= self.start_time or current < self.end_time

    @api.model
    def action_create_from_ui(self, vals):
        self._iot_require_admin()
        return self.create(self._iot_prepare_vals(vals)).id

    @api.model
    def _iot_prepare_vals(self, vals):
        allowed = {
            "name", "system_kind", "device_id", "property_id", "building_id", "area_id",
            "lighting_action", "hvac_setpoint", "start_time", "end_time", "active",
            "day_mon", "day_tue", "day_wed", "day_thu", "day_fri", "day_sat", "day_sun",
        }
        return {key: vals[key] for key in allowed if key in vals}

    @api.model
    def _cron_run_schedules(self):
        now = fields.Datetime.now()
        for schedule in self.search([("active", "=", True)]):
            if not schedule._iot_applies_now(now):
                continue
            device = schedule.device_id
            if not device:
                device = self.env["integration.iot.device"].search(
                    [
                        ("device_type", "=", schedule.system_kind if schedule.system_kind != "lighting" else "lighting"),
                        ("property_id", "=", schedule.property_id.id or False),
                        ("building_id", "=", schedule.building_id.id or False),
                        ("area_id", "=", schedule.area_id.id or False),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
            if not device:
                continue
            if schedule.system_kind == "lighting":
                if schedule.lighting_action == "turn_on":
                    device.action_turn_on()
                else:
                    device.action_turn_off()
            elif schedule.system_kind == "hvac":
                device.action_set_hvac(setpoint=schedule.hvac_setpoint or device.hvac_setpoint)
            schedule.last_run = now
        return True
