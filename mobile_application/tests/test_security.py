# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileSecurity(MobileApplicationCase):
    def test_groups_exist(self):
        self.env.ref("mobile_application.group_mobile_resident")
        self.env.ref("mobile_application.group_mobile_staff")
        self.env.ref("mobile_application.group_mobile_security")

    def test_unauthorized_user(self):
        with self.assertRaises(AccessError):
            self.api.with_user(self.other).get_capabilities()

    def test_resident_capabilities(self):
        caps = self.api.with_user(self.resident).get_capabilities()
        self.assertEqual(caps["role"], "resident")
        self.assertTrue(caps["modules"]["digital_id"])

    def test_security_no_payments(self):
        caps = self.api.with_user(self.security).get_capabilities()
        self.assertFalse(caps["modules"]["payments"])
