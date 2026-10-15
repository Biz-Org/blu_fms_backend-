# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotEnergy(IntegrationIotCase):
    def test_energy_reading_and_aggregation(self):
        meter = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Tower A Meter",
                "device_type": "meter",
                "building_id": self.tower_a.id,
            }
        )
        sensor = self.env["integration.iot.sensor"].with_user(self.admin).create(
            {
                "name": "Main Meter",
                "device_id": meter.id,
                "parameter": "energy",
                "unit": "kWh",
                "max_threshold": 500,
            }
        )
        self.env["integration.iot.reading"].with_user(self.admin).ingest_reading(sensor.id, 120)
        self.env["integration.iot.energy.opportunity"].with_user(self.admin).create(
            {
                "name": "Lobby lighting schedule",
                "estimated_kwh": 15,
                "building_id": self.tower_a.id,
            }
        ).action_apply()
        data = self.env["integration.iot.dashboard"].get_energy_data()
        self.assertGreaterEqual(data["kpis"]["current"], 120)
        self.assertGreaterEqual(data["kpis"]["peak"], 120)
        self.assertEqual(data["kpis"]["savings"], 15)
        self.assertTrue(data["by_location"])
