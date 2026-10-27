# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .adapter import get_adapter
from .constants import (
    DEFAULT_OFFLINE_MINUTES,
    DEVICE_STATUSES,
    DEVICE_TYPES,
    FIRE_ALARM_CONDITIONS,
    HVAC_MODES,
    POWER_STATES,
)


class IntegrationIotDevice(models.Model):
    _name = "integration.iot.device"
    _description = "IoT Device"
    _inherit = ["mail.thread", "mail.activity.mixin", "integration.iot.scoped.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, copy=False, default="New")
    device_type = fields.Selection(DEVICE_TYPES, required=True, default="other", tracking=True, index=True)
    integration_id = fields.Many2one(
        "integration.iot.integration",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    status = fields.Selection(DEVICE_STATUSES, default="offline", required=True, tracking=True, index=True)
    connectivity = fields.Boolean(default=True, tracking=True)
    health_score = fields.Integer(default=100)
    last_seen = fields.Datetime(index=True)
    offline_minutes = fields.Integer(default=DEFAULT_OFFLINE_MINUTES)
    control_supported = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    archived = fields.Boolean(default=False, index=True)
    note = fields.Text()
    settings_note = fields.Char(help="Free-text supported settings description.")
    power_state = fields.Selection(POWER_STATES, default="off")
    brightness = fields.Integer(default=100)
    hvac_mode = fields.Selection(HVAC_MODES, default="off")
    hvac_setpoint = fields.Float(digits=(5, 1))
    fire_alarm_condition = fields.Selection(FIRE_ALARM_CONDITIONS, default="normal", index=True)
    replaced_by_id = fields.Many2one("integration.iot.device", ondelete="set null")
    sensor_ids = fields.One2many("integration.iot.sensor", "device_id")
    log_ids = fields.One2many("integration.iot.log", "device_id")

    _sql_constraints = [
        (
            "code_company_uniq",
            "unique(code, company_id)",
            "Device code must be unique per company.",
        ),
    ]
    @api.constrains("brightness")
    def _iot_check_brightness(self):
        for record in self:
            if record.brightness < 0 or record.brightness > 100:
                raise ValidationError(_("Brightness must be between 0 and 100."))

    @api.constrains("health_score")
    def _iot_check_health(self):
        for record in self:
            if record.health_score < 0 or record.health_score > 100:
                raise ValidationError(_("Health score must be between 0 and 100."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("integration.iot.device") or "IOT-DEV"
        records = super().create(vals_list)
        for record in records:
            self.env["integration.iot.log"]._iot_record(
                kind="device_connected" if record.status == "online" else "device_updated",
                name=_("Device registered: %s") % record.display_name,
                device=record,
                simulated=True,
            )
        return records

    def write(self, vals):
        sensitive = {"integration_id", "device_type", "control_supported", "settings_note"}
        if sensitive & set(vals):
            self._iot_require_admin()
        return super().write(vals)

    def action_activate(self):
        self._iot_require_admin()
        self.write({"active": True, "archived": False, "status": "online", "last_seen": fields.Datetime.now()})
        for record in self:
            self.env["integration.iot.log"]._iot_record(
                kind="device_connected",
                name=_("Device activated: %s") % record.display_name,
                device=record,
            )
        return True

    def action_deactivate(self):
        self._iot_require_admin()
        self.write({"active": False, "status": "maintenance"})
        for record in self:
            self.env["integration.iot.log"]._iot_record(
                kind="device_updated",
                name=_("Device deactivated: %s") % record.display_name,
                device=record,
            )
        return True

    def action_archive(self):
        self._iot_require_admin()
        self.write({"archived": True, "active": False, "status": "offline"})
        return True

    def action_replace(self, replacement_id):
        self.ensure_one()
        self._iot_require_admin()
        replacement = self.browse(replacement_id)
        if not replacement.exists() or replacement.id == self.id:
            raise UserError(_("Select a different replacement device."))
        self.write({"replaced_by_id": replacement.id, "archived": True, "active": False, "status": "offline"})
        replacement.write({"active": True, "archived": False})
        self.env["integration.iot.log"]._iot_record(
            kind="device_updated",
            name=_("Device replaced: %s → %s") % (self.display_name, replacement.display_name),
            device=self,
        )
        return True

    def _iot_mark_seen(self, status="online"):
        self.write({"last_seen": fields.Datetime.now(), "status": status, "connectivity": True})

    def _iot_mark_offline(self, reason=None):
        for record in self:
            if record.status == "offline":
                continue
            record.write({"status": "offline", "connectivity": False})
            self.env["integration.iot.log"]._iot_record(
                kind="device_disconnected",
                name=_("Device offline: %s") % record.display_name,
                device=record,
                note=reason,
            )
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("IoT device offline: %s") % record.display_name,
                alert_type="device_offline",
                priority="high",
                device=record,
                origin=record,
                note=reason,
            )

    def _iot_mark_faulty(self, reason=None):
        self._iot_require_admin()
        for record in self:
            record.write({"status": "faulty", "health_score": min(record.health_score, 40)})
            alert_type = "hvac_fault" if record.device_type == "hvac" else "device_malfunction"
            if record.device_type == "fire_alarm":
                alert_type = "fire_alarm_fault"
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Device malfunction: %s") % record.display_name,
                alert_type=alert_type,
                priority="high",
                device=record,
                origin=record,
                note=reason,
            )
            self.env["integration.iot.log"]._iot_record(
                kind="device_updated",
                name=_("Device faulty: %s") % record.display_name,
                device=record,
                note=reason,
            )
        return True

    def _iot_execute(self, command, params=None):
        self.ensure_one()
        self._iot_require_admin(_("Only an Integration Admin can control connected equipment."))
        if not self.control_supported:
            raise UserError(_("Remote control is not supported for %s.") % self.display_name)
        if self.archived or not self.active:
            raise UserError(_("Archived or inactive devices cannot be controlled."))
        integration = self.integration_id
        adapter = get_adapter(integration) if integration else get_adapter(
            self.env["integration.iot.integration"].new({"system_kind": "mock"})
        )
        simulated = not integration or integration.connection_mode != "live"
        try:
            result = adapter.execute(self, command, params or {})
        except UserError:
            self.env["integration.iot.log"]._iot_record(
                kind="integration_failure",
                name=_("Command failed: %s (%s)") % (self.display_name, command),
                device=self,
                integration=integration,
                simulated=False,
            )
            raise
        simulated = bool(result.get("simulated", simulated))
        return result, simulated

    def action_turn_on(self):
        self.ensure_one()
        result, simulated = self._iot_execute("turn_on")
        self.write({"power_state": "on"})
        self._iot_mark_seen("online")
        self.env["integration.iot.log"]._iot_record(
            kind="lighting_changed",
            name=_("Lighting turned on: %s") % self.display_name,
            device=self,
            simulated=simulated,
            note=result.get("message"),
        )
        return {"simulated": simulated, "message": result.get("message")}

    def action_turn_off(self):
        self.ensure_one()
        result, simulated = self._iot_execute("turn_off")
        self.write({"power_state": "off"})
        self._iot_mark_seen("online")
        self.env["integration.iot.log"]._iot_record(
            kind="lighting_changed",
            name=_("Lighting turned off: %s") % self.display_name,
            device=self,
            simulated=simulated,
            note=result.get("message"),
        )
        return {"simulated": simulated, "message": result.get("message")}

    def action_set_hvac(self, setpoint=None, mode=None):
        self.ensure_one()
        params = {}
        vals = {}
        if setpoint is not None:
            params["setpoint"] = setpoint
            vals["hvac_setpoint"] = setpoint
        if mode:
            params["mode"] = mode
            vals["hvac_mode"] = mode
        result, simulated = self._iot_execute("set_hvac", params)
        if vals:
            self.write(vals)
        self._iot_mark_seen("online")
        self.env["integration.iot.log"]._iot_record(
            kind="hvac_adjusted",
            name=_("HVAC adjusted: %s") % self.display_name,
            device=self,
            simulated=simulated,
            note=result.get("message"),
        )
        return {"simulated": simulated, "message": result.get("message")}

    def action_set_fire_condition(self, condition):
        self.ensure_one()
        self._iot_require_admin()
        if condition not in dict(FIRE_ALARM_CONDITIONS):
            raise ValidationError(_("Invalid fire alarm condition."))
        self.write({"fire_alarm_condition": condition})
        event = self.env["integration.iot.alarm.event"].create(
            {
                "name": _("%s: %s") % (self.display_name, dict(FIRE_ALARM_CONDITIONS).get(condition)),
                "condition": condition,
                "device_id": self.id,
                "property_id": self.property_id.id,
                "building_id": self.building_id.id,
                "area_id": self.area_id.id,
                "company_id": self.company_id.id,
                "note": _("Recorded by Integration & IoT. Fire & Safety incident workflows are not duplicated."),
            }
        )
        self.env["integration.iot.log"]._iot_record(
            kind="fire_alarm_event",
            name=event.name,
            device=self,
        )
        if condition == "alarm":
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Fire alarm triggered: %s") % self.display_name,
                alert_type="fire_alarm_triggered",
                priority="critical",
                device=self,
                origin=self,
            )
        elif condition in ("fault", "communication_failure"):
            alert_type = "fire_alarm_fault" if condition == "fault" else "bms_failure"
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Fire alarm system %s: %s") % (condition.replace("_", " "), self.display_name),
                alert_type=alert_type,
                priority="high",
                device=self,
                origin=self,
            )
        if condition == "communication_failure":
            self._iot_mark_offline(_("Fire alarm communication failure"))
        else:
            self._iot_mark_seen("warning" if condition != "normal" else "online")
        return True

    @api.model
    def _cron_check_heartbeats(self):
        now = fields.Datetime.now()
        devices = self.search([("active", "=", True), ("archived", "=", False)])
        for device in devices:
            minutes = device.offline_minutes or DEFAULT_OFFLINE_MINUTES
            if not device.last_seen or device.last_seen < now - relativedelta(minutes=minutes):
                device._iot_mark_offline(_("No heartbeat within %s minutes") % minutes)
        return True
