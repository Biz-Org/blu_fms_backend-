# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileHome(MobileApplicationCase):
    def test_home_payload(self):
        data = self.api.with_user(self.resident).get_home()
        self.assertIn("profile", data)
        self.assertIn("my_requests", data)
        self.assertEqual(data["my_requests"], [])
