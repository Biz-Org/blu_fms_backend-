# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _


class IntegrationIotEnergyReading(models.Model):
    _name = "integration.iot.energy.reading"
    _description = "Energy Consumption Reading"
    _inherit = ["integration.iot.scoped.mixin"]
    _order = "captured_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default="Energy Reading")
    device_id = fields.Many2one("integration.iot.device", ondelete="set null", index=True)
    kwh = fields.Float(required=True, digits=(12, 3))
    is_peak = fields.Boolean(default=False)
    captured_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    source = fields.Selection(
        [("simulated", "Simulated"), ("manual", "Manual"), ("live", "Live")],
        default="simulated",
        required=True,
    )
    note = fields.Text()

    @api.model
    def _iot_from_sensor_reading(self, reading):
        if reading.parameter != "energy":
            return self.browse()
        peak = False
        siblings = self.search(
            [("building_id", "=", reading.building_id.id or False)],
            limit=20,
        )
        if siblings:
            avg = sum(siblings.mapped("kwh")) / len(siblings)
            peak = reading.value > avg * 1.5 if avg else False
        record = self.create(
            {
                "name": _("Meter %s") % (reading.device_id.display_name or reading.sensor_id.display_name),
                "device_id": reading.device_id.id,
                "kwh": reading.value,
                "is_peak": peak,
                "captured_at": reading.captured_at,
                "source": reading.source,
                "property_id": reading.property_id.id,
                "building_id": reading.building_id.id,
                "area_id": reading.area_id.id,
                "company_id": reading.company_id.id,
            }
        )
        if peak:
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Abnormal energy consumption: %s") % record.display_name,
                alert_type="energy_abnormal",
                priority="medium",
                device=reading.device_id,
                sensor=reading.sensor_id,
                reading=reading,
                origin=record,
            )
        return record


class IntegrationIotEnergyOpportunity(models.Model):
    _name = "integration.iot.energy.opportunity"
    _description = "Energy Saving Opportunity"
    _inherit = ["mail.thread", "integration.iot.scoped.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    estimated_kwh = fields.Float(digits=(12, 3))
    applied_kwh = fields.Float(digits=(12, 3))
    state = fields.Selection(
        [("open", "Open"), ("applied", "Applied")],
        default="open",
        required=True,
        tracking=True,
    )
    note = fields.Text()

    def action_apply(self):
        self._iot_require_admin()
        for record in self:
            record.write(
                {
                    "state": "applied",
                    "applied_kwh": record.applied_kwh or record.estimated_kwh,
                }
            )
        return True
