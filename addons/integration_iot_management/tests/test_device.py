# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotDevice(IntegrationIotCase):
    def test_device_state_changes_and_history(self):
        device = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Clubhouse Light",
                "device_type": "lighting",
                "building_id": self.tower_a.id,
                "control_supported": True,
            }
        )
        device.with_user(self.admin).action_activate()
        self.assertEqual(device.status, "online")
        result = device.with_user(self.admin).action_turn_on()
        self.assertTrue(result["simulated"])
        self.assertEqual(device.power_state, "on")
        device.with_user(self.admin).action_turn_off()
        self.assertEqual(device.power_state, "off")
        logs = self.env["integration.iot.log"].search([("device_id", "=", device.id)])
        self.assertTrue(logs.filtered(lambda rec: rec.kind == "lighting_changed"))

    def test_heartbeat_marks_offline_and_alerts(self):
        device = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Offline Candidate",
                "device_type": "gateway",
                "status": "online",
                "last_seen": fields.Datetime.now() - timedelta(hours=2),
                "offline_minutes": 15,
            }
        )
        self.env["integration.iot.device"]._cron_check_heartbeats()
        self.assertEqual(device.status, "offline")
        alert = self.env["integration.iot.alert"].search(
            [("device_id", "=", device.id), ("alert_type", "=", "device_offline")]
        )
        self.assertTrue(alert)

    def test_live_adapter_does_not_claim_physical_success(self):
        live = self.env["integration.iot.integration"].create(
            {"name": "Live HVAC", "system_kind": "hvac", "state": "configured"}
        )
        device = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "AHU-1",
                "device_type": "hvac",
                "integration_id": live.id,
                "control_supported": True,
            }
        )
        with self.assertRaises(UserError):
            device.with_user(self.admin).action_set_hvac(setpoint=22)
