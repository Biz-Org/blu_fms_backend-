# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotAutomation(IntegrationIotCase):
    def test_rule_trigger_and_simulated_execution(self):
        hvac = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Tower A HVAC",
                "device_type": "hvac",
                "building_id": self.tower_a.id,
                "hvac_setpoint": 24,
                "hvac_mode": "cool",
                "control_supported": True,
                "integration_id": self.integration.id,
            }
        )
        sensor_device = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Tower A Temp",
                "device_type": "temperature",
                "building_id": self.tower_a.id,
            }
        )
        sensor = self.env["integration.iot.sensor"].with_user(self.admin).create(
            {
                "name": "Zone Temp",
                "device_id": sensor_device.id,
                "parameter": "temperature",
                "unit": "°C",
                "max_threshold": 26,
            }
        )
        rule = self.env["integration.iot.automation.rule"].with_user(self.admin).create(
            {
                "name": "Cool when hot",
                "building_id": self.tower_a.id,
                "trigger_parameter": "temperature",
                "operator": "gt",
                "threshold": 26,
                "action": "increase_hvac_cooling",
                "action_value": 1,
                "target_device_id": hvac.id,
                "schedule_mode": "always",
            }
        )
        self.env["integration.iot.reading"].with_user(self.admin).ingest_reading(sensor.id, 28)
        execution = self.env["integration.iot.automation.execution"].search(
            [("rule_id", "=", rule.id)], limit=1
        )
        self.assertTrue(execution)
        self.assertEqual(execution.state, "simulated")
        self.assertEqual(hvac.hvac_setpoint, 23)
        self.assertTrue(rule.last_executed)

    def test_unauthorized_cannot_create_or_override(self):
        with self.assertRaises(AccessError):
            self.env["integration.iot.automation.rule"].with_user(self.other).create(
                {
                    "name": "Blocked",
                    "trigger_parameter": "temperature",
                    "operator": "gt",
                    "threshold": 30,
                    "action": "raise_alert",
                }
            )
        rule = self.env["integration.iot.automation.rule"].with_user(self.admin).create(
            {
                "name": "Alert only",
                "trigger_parameter": "temperature",
                "operator": "gt",
                "threshold": 1,
                "action": "raise_alert",
            }
        )
        execution = rule.with_user(self.admin)._iot_execute()
        with self.assertRaises(AccessError):
            execution.with_user(self.other).action_manual_override()
        execution.with_user(self.admin).action_manual_override()
        self.assertEqual(execution.state, "overridden")
