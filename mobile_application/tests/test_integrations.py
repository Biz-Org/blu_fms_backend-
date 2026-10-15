# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileIntegrations(MobileApplicationCase):
    def test_community_unavailable_without_module(self):
        integration = self.env["mobile.integration.community"]
        if not integration.available:
            data = integration.get_updates(self.resident)
            self.assertFalse(data["available"])
        else:
            data = integration.get_updates(self.resident)
            self.assertTrue(data["available"])

    def test_sync(self):
        result = self.api.with_user(self.resident).sync(idempotency_key="sync-1")
        self.assertIn("capabilities", result)
        self.assertIn("last_sync", result)
        again = self.api.with_user(self.resident).sync(idempotency_key="sync-1")
        self.assertIn("last_sync", again)

    def test_payments_resident_only(self):
        data = self.api.with_user(self.resident).get_payments()
        self.assertIn("items", data)
