# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileServiceRequests(MobileApplicationCase):
    def test_create_service_request(self):
        req = self.api.with_user(self.resident).create_service_request(
            "Plumbing",
            "Leaking tap",
            idempotency_key="sr-test-1",
        )
        self.assertEqual(req["state"], "submitted")

    def test_idempotent_retry(self):
        first = self.api.with_user(self.resident).create_service_request(
            "Electrical",
            "Power issue",
            idempotency_key="sr-test-2",
        )
        second = self.api.with_user(self.resident).create_service_request(
            "Electrical",
            "Power issue",
            idempotency_key="sr-test-2",
        )
        self.assertEqual(first["id"], second["id"])

    def test_staff_cannot_create_as_resident(self):
        with self.assertRaises(AccessError):
            self.api.with_user(self.staff).create_service_request("X", "Y")
