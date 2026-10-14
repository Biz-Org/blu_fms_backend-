# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotSecurity(IntegrationIotCase):
    def test_admin_can_create_device(self):
        device = self.env["integration.iot.device"].with_user(self.admin).create(
            {
                "name": "Lobby Light",
                "device_type": "lighting",
                "property_id": self.property.id,
                "building_id": self.tower_a.id,
                "area_id": self.lobby.id,
            }
        )
        self.assertTrue(device.code)
        self.assertNotEqual(device.code, "New")

    def test_unauthorized_user_cannot_create_device(self):
        with self.assertRaises(AccessError):
            self.env["integration.iot.device"].with_user(self.other).create(
                {"name": "Blocked", "device_type": "lighting"}
            )

    def test_unauthorized_user_cannot_control_device(self):
        device = self.env["integration.iot.device"].with_user(self.admin).create(
            {"name": "HVAC-1", "device_type": "hvac", "control_supported": True}
        )
        with self.assertRaises(AccessError):
            device.with_user(self.other).action_turn_on()

    def test_unauthorized_cannot_change_credentials(self):
        with self.assertRaises(AccessError):
            self.integration.with_user(self.other).action_set_secret("secret-value")

    def test_admin_can_set_secret_without_exposing_in_dashboard(self):
        self.integration.with_user(self.admin).action_set_secret("secret-value")
        self.assertTrue(self.integration.auth_secret_set)
        payload = self.env["integration.iot.dashboard"].with_user(self.admin).get_lookups()
        self.assertTrue(payload["integrations"])
        self.assertNotIn("auth_secret", payload["integrations"][0])
