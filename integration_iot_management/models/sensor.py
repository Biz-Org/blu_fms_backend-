# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .constants import DEFAULT_STALE_MINUTES, SENSOR_PARAMETERS


class IntegrationIotSensor(models.Model):
    _name = "integration.iot.sensor"
    _description = "IoT Sensor"
    _inherit = ["mail.thread", "integration.iot.scoped.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(index=True)
    device_id = fields.Many2one(
        "integration.iot.device",
        required=True,
        ondelete="cascade",
        index=True,
    )
    parameter = fields.Selection(SENSOR_PARAMETERS, required=True, default="temperature", index=True)
    unit = fields.Char()
    last_value = fields.Float(digits=(12, 3))
    last_reading_at = fields.Datetime(index=True)
    min_threshold = fields.Float(digits=(12, 3))
    max_threshold = fields.Float(digits=(12, 3))
    stale_minutes = fields.Integer(default=DEFAULT_STALE_MINUTES)
    active = fields.Boolean(default=True)
    reading_ids = fields.One2many("integration.iot.reading", "sensor_id")

    @api.onchange("device_id")
    def _iot_onchange_device(self):
        if self.device_id:
            self.property_id = self.device_id.property_id
            self.building_id = self.device_id.building_id
            self.area_id = self.device_id.area_id
            self.company_id = self.device_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            device = self.env["integration.iot.device"].browse(vals.get("device_id"))
            if device:
                vals.setdefault("property_id", device.property_id.id)
                vals.setdefault("building_id", device.building_id.id)
                vals.setdefault("area_id", device.area_id.id)
                vals.setdefault("company_id", device.company_id.id)
        return super().create(vals_list)

    @api.constrains("min_threshold", "max_threshold")
    def _iot_check_thresholds(self):
        for record in self:
            if (
                record.min_threshold
                and record.max_threshold
                and record.min_threshold > record.max_threshold
            ):
                raise ValidationError(_("Minimum threshold cannot exceed maximum threshold."))

    def _iot_quality_for(self, value):
        self.ensure_one()
        if value is False or value is None:
            return "missing"
        if self.min_threshold and value < self.min_threshold:
            return "abnormal"
        if self.max_threshold and value > self.max_threshold:
            return "abnormal"
        return "valid"
