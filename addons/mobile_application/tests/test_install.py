# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileInstall(MobileApplicationCase):
    def test_client_action(self):
        action = self.env.ref("mobile_application.action_mobile_application")
        self.assertEqual(action.tag, "mobile_application.action_mobile_app")
