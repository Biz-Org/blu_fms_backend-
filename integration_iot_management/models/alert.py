# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import ALERT_PRIORITIES, ALERT_STATES, ALERT_TYPES


class IntegrationIotAlert(models.Model):
    _name = "integration.iot.alert"
    _description = "IoT Alert"
    _inherit = ["mail.thread", "mail.activity.mixin", "integration.iot.scoped.mixin"]
    _order = "priority_rank desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    alert_type = fields.Selection(ALERT_TYPES, required=True, index=True)
    priority = fields.Selection(ALERT_PRIORITIES, default="medium", required=True, tracking=True, index=True)
    priority_rank = fields.Integer(compute="_compute_priority_rank", store=True)
    state = fields.Selection(ALERT_STATES, default="open", required=True, tracking=True, index=True)
    note = fields.Text()
    integration_id = fields.Many2one("integration.iot.integration", ondelete="set null", index=True)
    device_id = fields.Many2one("integration.iot.device", ondelete="set null", index=True)
    sensor_id = fields.Many2one("integration.iot.sensor", ondelete="set null", index=True)
    reading_id = fields.Many2one("integration.iot.reading", ondelete="set null", index=True)
    automation_id = fields.Many2one("integration.iot.automation.rule", ondelete="set null", index=True)
    origin_model = fields.Char(index=True)
    origin_id = fields.Integer(index=True)
    acknowledged_by_id = fields.Many2one("res.users", readonly=True)
    acknowledged_datetime = fields.Datetime(readonly=True)

    @api.depends("priority")
    def _compute_priority_rank(self):
        rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        for record in self:
            record.priority_rank = rank.get(record.priority, 0)

    def action_acknowledge(self):
        self._iot_require_admin()
        self.write(
            {
                "state": "acknowledged",
                "acknowledged_by_id": self.env.user.id,
                "acknowledged_datetime": fields.Datetime.now(),
            }
        )
        return True

    def action_close(self):
        self._iot_require_admin()
        self.write({"state": "closed"})
        return True

    def _iot_find_open(self, origin_model, origin_id, alert_type):
        return self.search(
            [
                ("origin_model", "=", origin_model),
                ("origin_id", "=", origin_id),
                ("alert_type", "=", alert_type),
                ("state", "in", ["open", "acknowledged"]),
            ],
            limit=1,
        )

    @api.model
    def _iot_ensure_alert(
        self,
        *,
        name,
        alert_type,
        priority="medium",
        note=False,
        origin=None,
        integration=None,
        device=None,
        sensor=None,
        reading=None,
        automation=None,
    ):
        origin_model = origin._name if origin is not None else False
        origin_id = origin.id if origin is not None else False
        alert = self._iot_find_open(origin_model, origin_id, alert_type) if origin_model else self.browse()
        vals = {
            "name": name,
            "alert_type": alert_type,
            "priority": priority,
            "note": note or False,
            "integration_id": integration.id if integration else False,
            "device_id": device.id if device else False,
            "sensor_id": sensor.id if sensor else False,
            "reading_id": reading.id if reading else False,
            "automation_id": automation.id if automation else False,
        }
        location_src = device or sensor or origin
        if location_src is not None:
            if getattr(location_src, "company_id", False):
                vals["company_id"] = location_src.company_id.id
            if getattr(location_src, "property_id", False):
                vals["property_id"] = location_src.property_id.id
            if getattr(location_src, "building_id", False):
                vals["building_id"] = location_src.building_id.id
            if getattr(location_src, "area_id", False):
                vals["area_id"] = location_src.area_id.id
        if alert:
            write_vals = {key: vals[key] for key in ("name", "note") if vals.get(key) and alert[key] != vals[key]}
            rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            if rank.get(priority, 0) > rank.get(alert.priority, 0):
                write_vals["priority"] = priority
            if write_vals:
                alert.write(write_vals)
            return alert
        vals.update(
            {
                "origin_model": origin_model,
                "origin_id": origin_id,
                "state": "open",
            }
        )
        alert = self.sudo().create(vals)
        record = origin or device or sensor
        if record is not None and hasattr(record, "activity_schedule"):
            activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if activity_type:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=self.env.user.id,
                    summary=name,
                    date_deadline=fields.Date.context_today(self),
                )
        return alert
