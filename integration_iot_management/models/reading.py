# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .constants import DEFAULT_STALE_MINUTES, READING_QUALITIES, READING_SOURCES


class IntegrationIotReading(models.Model):
    _name = "integration.iot.reading"
    _description = "IoT Sensor Reading"
    _inherit = ["integration.iot.scoped.mixin"]
    _order = "captured_at desc, id desc"
    _check_company_auto = True

    sensor_id = fields.Many2one(
        "integration.iot.sensor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    device_id = fields.Many2one(related="sensor_id.device_id", store=True, index=True)
    parameter = fields.Selection(related="sensor_id.parameter", store=True, index=True)
    value = fields.Float(digits=(12, 3))
    unit = fields.Char()
    quality = fields.Selection(READING_QUALITIES, required=True, default="valid", index=True)
    source = fields.Selection(READING_SOURCES, required=True, default="simulated", index=True)
    captured_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    note = fields.Text()

    @api.constrains("value", "quality")
    def _iot_check_value(self):
        for record in self:
            if record.quality == "missing":
                continue
            if record.value is False:
                raise ValidationError(_("A numeric value is required unless the reading is marked missing."))

    @api.model
    def ingest_reading(self, sensor_id, value, captured_at=None, source="simulated", missing=False):
        """Server-side ingestion used by mock/dev and future adapters."""
        sensor = self.env["integration.iot.sensor"].browse(sensor_id)
        if not sensor.exists() or not sensor.active:
            raise ValidationError(_("Sensor is missing or inactive."))
        if missing:
            quality = "missing"
            value = 0.0
        else:
            try:
                value = float(value)
            except (TypeError, ValueError) as err:
                raise ValidationError(_("Sensor value must be numeric.")) from err
            quality = sensor._iot_quality_for(value)
        when = fields.Datetime.to_datetime(captured_at) if captured_at else fields.Datetime.now()
        reading = self.create(
            {
                "sensor_id": sensor.id,
                "value": value,
                "unit": sensor.unit,
                "quality": quality,
                "source": source if source in dict(READING_SOURCES) else "simulated",
                "captured_at": when,
                "property_id": sensor.property_id.id,
                "building_id": sensor.building_id.id,
                "area_id": sensor.area_id.id,
                "company_id": sensor.company_id.id,
            }
        )
        sensor.write({"last_value": value, "last_reading_at": when})
        if sensor.device_id:
            sensor.device_id._iot_mark_seen("online" if quality != "abnormal" else "warning")
        self.env["integration.iot.log"]._iot_record(
            kind="reading_received",
            name=_("%s reading: %s %s") % (sensor.display_name, value, sensor.unit or ""),
            sensor=sensor,
            device=sensor.device_id,
            reading=reading,
            simulated=reading.source != "live",
        )
        if quality == "abnormal":
            alert_type = "air_quality" if sensor.parameter in ("air_quality", "co2") else "threshold_exceeded"
            if sensor.parameter == "energy":
                alert_type = "energy_abnormal"
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Threshold exceeded: %s") % sensor.display_name,
                alert_type=alert_type,
                priority="high" if sensor.parameter in ("air_quality", "co2", "energy") else "medium",
                sensor=sensor,
                device=sensor.device_id,
                reading=reading,
                origin=sensor,
            )
            self.env["integration.iot.log"]._iot_record(
                kind="threshold_exceeded",
                name=_("Threshold exceeded: %s") % sensor.display_name,
                sensor=sensor,
                device=sensor.device_id,
                reading=reading,
                simulated=reading.source != "live",
            )
        if sensor.parameter == "energy" and sensor.device_id:
            self.env["integration.iot.energy.reading"]._iot_from_sensor_reading(reading)
        self.env["integration.iot.automation.rule"]._iot_evaluate_for_reading(reading)
        return reading.id

    @api.model
    def _cron_detect_stale(self):
        now = fields.Datetime.now()
        sensors = self.env["integration.iot.sensor"].search([("active", "=", True)])
        for sensor in sensors:
            minutes = sensor.stale_minutes or DEFAULT_STALE_MINUTES
            stale = not sensor.last_reading_at or sensor.last_reading_at < now - relativedelta(minutes=minutes)
            if not stale:
                continue
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("Sensor data unavailable: %s") % sensor.display_name,
                alert_type="sensor_unavailable",
                priority="medium",
                sensor=sensor,
                device=sensor.device_id,
                origin=sensor,
            )
        return True
