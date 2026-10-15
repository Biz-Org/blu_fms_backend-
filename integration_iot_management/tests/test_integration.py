# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotIntegration(IntegrationIotCase):
    def test_mock_connection_ready(self):
        result = self.integration.with_user(self.admin).action_test_connection()
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "simulated")
        self.assertEqual(self.integration.state, "connected")
        self.assertEqual(self.integration.connection_mode, "simulated")

    def test_unconfigured_live_kind_records_failure(self):
        bms = self.env["integration.iot.integration"].with_user(self.admin).create(
            {"name": "Vendor BMS", "system_kind": "bms", "auth_type": "api_key"}
        )
        result = bms.with_user(self.admin).action_test_connection()
        self.assertFalse(result["ok"])
        self.assertEqual(bms.state, "error")
        alert = self.env["integration.iot.alert"].search(
            [("integration_id", "=", bms.id), ("alert_type", "=", "bms_failure")]
        )
        self.assertTrue(alert)
        log = self.env["integration.iot.log"].search(
            [("integration_id", "=", bms.id), ("kind", "=", "integration_failure")]
        )
        self.assertTrue(log)

    def test_fire_alarm_event_does_not_require_fire_safety(self):
        panel = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Tower A Panel",
                "device_type": "fire_alarm",
                "building_id": self.tower_a.id,
            }
        )
        panel.with_user(self.admin).action_set_fire_condition("alarm")
        event = self.env["integration.iot.alarm.event"].search([("device_id", "=", panel.id)])
        self.assertTrue(event)
        self.assertEqual(event.condition, "alarm")
        self.assertNotIn("incident_id", event._fields)
        alert = self.env["integration.iot.alert"].search(
            [("device_id", "=", panel.id), ("alert_type", "=", "fire_alarm_triggered")]
        )
        self.assertTrue(alert)
