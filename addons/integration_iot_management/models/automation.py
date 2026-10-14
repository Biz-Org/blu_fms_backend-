# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .constants import (
    AUTOMATION_ACTIONS,
    COMPARISON_OPERATORS,
    EXECUTION_STATES,
    SCHEDULE_MODES,
    SENSOR_PARAMETERS,
)


class IntegrationIotAutomationRule(models.Model):
    _name = "integration.iot.automation.rule"
    _description = "Building Automation Rule"
    _inherit = ["mail.thread", "mail.activity.mixin", "integration.iot.scoped.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    trigger_parameter = fields.Selection(SENSOR_PARAMETERS, required=True, default="temperature")
    operator = fields.Selection(COMPARISON_OPERATORS, required=True, default="gt")
    threshold = fields.Float(required=True, digits=(12, 3))
    action = fields.Selection(AUTOMATION_ACTIONS, required=True, default="increase_hvac_cooling")
    action_value = fields.Float(digits=(12, 3), help="Setpoint or cooling step, depending on the action.")
    target_device_id = fields.Many2one("integration.iot.device", ondelete="set null", index=True)
    schedule_mode = fields.Selection(SCHEDULE_MODES, default="always", required=True)
    start_time = fields.Float()
    end_time = fields.Float()
    day_mon = fields.Boolean(default=True)
    day_tue = fields.Boolean(default=True)
    day_wed = fields.Boolean(default=True)
    day_thu = fields.Boolean(default=True)
    day_fri = fields.Boolean(default=True)
    day_sat = fields.Boolean(default=True)
    day_sun = fields.Boolean(default=True)
    last_executed = fields.Datetime(readonly=True)
    execution_ids = fields.One2many("integration.iot.automation.execution", "rule_id")

    @api.constrains("schedule_mode", "start_time", "end_time")
    def _iot_check_schedule(self):
        for record in self:
            if record.schedule_mode != "scheduled":
                continue
            if not (0 <= record.start_time <= 24 and 0 <= record.end_time <= 24):
                raise ValidationError(_("Scheduled automation times must be between 00:00 and 24:00."))

    def write(self, vals):
        if set(vals) - {"last_executed"}:
            self._iot_require_admin(_("Only an Integration Admin can change automation rules."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        self._iot_require_admin(_("Only an Integration Admin can create automation rules."))
        return super().create(vals_list)

    def unlink(self):
        self._iot_require_admin()
        return super().unlink()

    def action_enable(self):
        self._iot_require_admin()
        self.write({"active": True})
        return True

    def action_disable(self):
        self._iot_require_admin()
        self.write({"active": False})
        return True

    def _iot_applies_now(self, when):
        self.ensure_one()
        if self.schedule_mode != "scheduled":
            return True
        flags = {
            0: self.day_mon, 1: self.day_tue, 2: self.day_wed, 3: self.day_thu,
            4: self.day_fri, 5: self.day_sat, 6: self.day_sun,
        }
        if not flags.get(when.weekday(), False):
            return False
        current = when.hour + when.minute / 60.0
        if self.start_time <= self.end_time:
            return self.start_time <= current < self.end_time
        return current >= self.start_time or current < self.end_time

    def _iot_compare(self, value):
        self.ensure_one()
        ops = {
            "gt": value > self.threshold,
            "gte": value >= self.threshold,
            "lt": value < self.threshold,
            "lte": value <= self.threshold,
            "eq": value == self.threshold,
            "neq": value != self.threshold,
        }
        return ops.get(self.operator, False)

    def _iot_evaluate_for_reading(self, reading):
        if reading.quality == "missing":
            return True
        rules = self.search(
            [
                ("active", "=", True),
                ("trigger_parameter", "=", reading.parameter),
            ]
        )
        for rule in rules:
            if not rule._iot_matches_location(reading):
                continue
            if not rule._iot_applies_now(reading.captured_at or fields.Datetime.now()):
                continue
            if not rule._iot_compare(reading.value):
                continue
            rule._iot_execute(reading=reading)
        return True

    def _iot_target_device(self, reading=None):
        self.ensure_one()
        if self.target_device_id:
            return self.target_device_id
        wanted = {
            "increase_hvac_cooling": "hvac",
            "decrease_hvac_cooling": "hvac",
            "set_hvac_setpoint": "hvac",
            "lighting_on": "lighting",
            "lighting_off": "lighting",
        }.get(self.action)
        domain = [("active", "=", True), ("archived", "=", False)]
        if wanted:
            domain.append(("device_type", "=", wanted))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        elif self.building_id:
            domain.append(("building_id", "=", self.building_id.id))
        elif self.property_id:
            domain.append(("property_id", "=", self.property_id.id))
        elif reading:
            if reading.area_id:
                domain.append(("area_id", "=", reading.area_id.id))
            elif reading.building_id:
                domain.append(("building_id", "=", reading.building_id.id))
        return self.env["integration.iot.device"].search(domain, limit=1)

    def _iot_execute(self, reading=None, manual=False):
        self.ensure_one()
        if manual:
            self._iot_require_admin(_("Only an Integration Admin can manually run automation."))
        device = self._iot_target_device(reading)
        Execution = self.env["integration.iot.automation.execution"]
        if self.action == "raise_alert":
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Automation alert: %s") % self.display_name,
                alert_type="threshold_exceeded",
                priority="medium",
                automation=self,
                device=device,
                sensor=reading.sensor_id if reading else False,
                reading=reading,
                origin=self,
            )
            execution = Execution._iot_create_result(
                self, device, reading, "simulated", _("Alert raised. No physical action sent."), True
            )
            self.last_executed = fields.Datetime.now()
            return execution
        if not device:
            return Execution._iot_create_result(
                self, device, reading, "failed", _("No target device found for this rule."), True
            )
        try:
            if self.action == "increase_hvac_cooling":
                step = self.action_value or 1.0
                new_setpoint = (device.hvac_setpoint or 24.0) - step
                result = device.action_set_hvac(setpoint=new_setpoint, mode=device.hvac_mode or "cool")
            elif self.action == "decrease_hvac_cooling":
                step = self.action_value or 1.0
                new_setpoint = (device.hvac_setpoint or 24.0) + step
                result = device.action_set_hvac(setpoint=new_setpoint, mode=device.hvac_mode or "heat")
            elif self.action == "set_hvac_setpoint":
                result = device.action_set_hvac(setpoint=self.action_value, mode=device.hvac_mode or "auto")
            elif self.action == "lighting_on":
                result = device.action_turn_on()
            elif self.action == "lighting_off":
                result = device.action_turn_off()
            else:
                raise UserError(_("Unsupported automation action."))
        except UserError as err:
            execution = Execution._iot_create_result(self, device, reading, "failed", str(err), False)
            self.env["integration.iot.log"]._iot_record(
                kind="automation_triggered",
                name=_("Automation failed: %s") % self.display_name,
                automation=self,
                device=device,
                reading=reading,
                execution=execution,
                simulated=False,
                note=str(err),
            )
            return execution
        simulated = bool(result.get("simulated", True))
        state = "simulated" if simulated else "success"
        execution = Execution._iot_create_result(
            self, device, reading, state, result.get("message"), simulated
        )
        self.last_executed = fields.Datetime.now()
        self.env["integration.iot.log"]._iot_record(
            kind="automation_executed",
            name=_("Automation executed: %s") % self.display_name,
            automation=self,
            device=device,
            reading=reading,
            execution=execution,
            simulated=simulated,
        )
        return execution

    def action_run_now(self):
        self.ensure_one()
        return self._iot_execute(manual=True).id


class IntegrationIotAutomationExecution(models.Model):
    _name = "integration.iot.automation.execution"
    _description = "Automation Execution History"
    _order = "executed_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    rule_id = fields.Many2one(
        "integration.iot.automation.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="rule_id.company_id", store=True, index=True)
    device_id = fields.Many2one("integration.iot.device", ondelete="set null", index=True)
    reading_id = fields.Many2one("integration.iot.reading", ondelete="set null", index=True)
    state = fields.Selection(EXECUTION_STATES, required=True, default="simulated", index=True)
    simulated = fields.Boolean(default=True)
    message = fields.Text()
    executed_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    overridden_by_id = fields.Many2one("res.users", readonly=True)
    overridden_at = fields.Datetime(readonly=True)

    @api.model
    def _iot_create_result(self, rule, device, reading, state, message, simulated):
        return self.create(
            {
                "name": _("%s @ %s") % (rule.display_name, fields.Datetime.now()),
                "rule_id": rule.id,
                "device_id": device.id if device else False,
                "reading_id": reading.id if reading else False,
                "state": state,
                "simulated": simulated,
                "message": message,
            }
        )

    def action_manual_override(self):
        self._iot_require_admin(_("Only an Integration Admin can override automation."))
        self.write(
            {
                "state": "overridden",
                "overridden_by_id": self.env.user.id,
                "overridden_at": fields.Datetime.now(),
            }
        )
        for record in self:
            self.env["integration.iot.log"]._iot_record(
                kind="manual_override",
                name=_("Manual override: %s") % record.rule_id.display_name,
                automation=record.rule_id,
                device=record.device_id,
                execution=record,
                simulated=record.simulated,
            )
        return True

    def _iot_require_admin(self, message=None):
        return self.env["integration.iot.device"]._iot_require_admin(message)
