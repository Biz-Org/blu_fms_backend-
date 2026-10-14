# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import LOG_KINDS


class IntegrationIotLog(models.Model):
    _name = "integration.iot.log"
    _description = "IoT Operational Log"
    _order = "event_time desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    kind = fields.Selection(LOG_KINDS, required=True, index=True)
    event_time = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    note = fields.Text()
    simulated = fields.Boolean(default=True)
    integration_id = fields.Many2one("integration.iot.integration", ondelete="set null", index=True)
    device_id = fields.Many2one("integration.iot.device", ondelete="set null", index=True)
    sensor_id = fields.Many2one("integration.iot.sensor", ondelete="set null", index=True)
    reading_id = fields.Many2one("integration.iot.reading", ondelete="set null", index=True)
    automation_id = fields.Many2one("integration.iot.automation.rule", ondelete="set null", index=True)
    execution_id = fields.Many2one("integration.iot.automation.execution", ondelete="set null", index=True)
    property_id = fields.Many2one("integration.iot.property", ondelete="set null", index=True)
    building_id = fields.Many2one("integration.iot.building", ondelete="set null", index=True)
    area_id = fields.Many2one("integration.iot.area", ondelete="set null", index=True)

    @api.model
    def _iot_record(self, *, kind, name, note=False, simulated=True, integration=None,
                    device=None, sensor=None, reading=None, automation=None, execution=None):
        location_src = device or sensor or integration or automation
        vals = {
            "kind": kind,
            "name": name,
            "note": note or False,
            "simulated": simulated,
            "event_time": fields.Datetime.now(),
        }
        if integration:
            vals["integration_id"] = integration.id
            vals["company_id"] = integration.company_id.id
        if device:
            vals.update(
                {
                    "device_id": device.id,
                    "company_id": device.company_id.id,
                    "property_id": device.property_id.id,
                    "building_id": device.building_id.id,
                    "area_id": device.area_id.id,
                    "integration_id": device.integration_id.id or vals.get("integration_id"),
                }
            )
        if sensor:
            vals.update(
                {
                    "sensor_id": sensor.id,
                    "device_id": sensor.device_id.id or vals.get("device_id"),
                    "company_id": sensor.company_id.id,
                    "property_id": sensor.property_id.id,
                    "building_id": sensor.building_id.id,
                    "area_id": sensor.area_id.id,
                }
            )
        if reading:
            vals["reading_id"] = reading.id
        if automation:
            vals["automation_id"] = automation.id
        if execution:
            vals["execution_id"] = execution.id
        if location_src and "company_id" not in vals and getattr(location_src, "company_id", False):
            vals["company_id"] = location_src.company_id.id
        return self.sudo().create(vals)
