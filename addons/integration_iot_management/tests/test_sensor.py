# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotSensor(IntegrationIotCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["integration.iot.device"].create(
            {
                "name": "Floor 3 Temp",
                "device_type": "temperature",
                "building_id": cls.tower_a.id,
                "area_id": cls.lobby.id,
            }
        )
        cls.sensor = cls.env["integration.iot.sensor"].create(
            {
                "name": "Lobby Temperature",
                "device_id": cls.device.id,
                "parameter": "temperature",
                "unit": "°C",
                "min_threshold": 16,
                "max_threshold": 26,
            }
        )

    def test_reading_creation_and_threshold_alert(self):
        reading_id = self.env["integration.iot.reading"].with_user(self.admin).ingest_reading(
            self.sensor.id,
            31,
        )
        reading = self.env["integration.iot.reading"].browse(reading_id)
        self.assertEqual(reading.quality, "abnormal")
        self.assertEqual(self.sensor.last_value, 31)
        alert = self.env["integration.iot.alert"].search(
            [("sensor_id", "=", self.sensor.id), ("alert_type", "=", "threshold_exceeded")]
        )
        self.assertTrue(alert)

    def test_invalid_sensor_data_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["integration.iot.reading"].ingest_reading(self.sensor.id, "hot")

    def test_missing_reading_quality(self):
        reading_id = self.env["integration.iot.reading"].ingest_reading(
            self.sensor.id, None, missing=True
        )
        reading = self.env["integration.iot.reading"].browse(reading_id)
        self.assertEqual(reading.quality, "missing")
