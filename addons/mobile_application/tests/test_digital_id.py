# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileDigitalId(MobileApplicationCase):
    def test_digital_id_generation(self):
        payload = self.api.with_user(self.resident).get_digital_id()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["name"], self.resident.name)

    def test_digital_id_verification(self):
        payload = self.api.with_user(self.resident).get_digital_id()
        verified = self.api.with_user(self.security).verify_digital_id(payload["token"])
        self.assertTrue(verified["verified"])

    def test_resident_cannot_verify(self):
        payload = self.api.with_user(self.resident).get_digital_id()
        with self.assertRaises(AccessError):
            self.api.with_user(self.resident).verify_digital_id(payload["token"])
