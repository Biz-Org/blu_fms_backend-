# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import IntegrationIotCase


@tagged("post_install", "-at_install")
class TestIntegrationIotInstall(IntegrationIotCase):
    def test_module_models_exist(self):
        for model in (
            "integration.iot.property",
            "integration.iot.integration",
            "integration.iot.device",
            "integration.iot.sensor",
            "integration.iot.reading",
            "integration.iot.schedule",
            "integration.iot.automation.rule",
            "integration.iot.automation.execution",
            "integration.iot.alert",
            "integration.iot.log",
            "integration.iot.alarm.event",
            "integration.iot.energy.reading",
            "integration.iot.dashboard",
        ):
            self.assertIn(model, self.env)

    def test_group_exists(self):
        self.assertTrue(self.env.ref("integration_iot_management.group_integration_admin"))

    def test_dashboard_payload(self):
        data = self.env["integration.iot.dashboard"].get_dashboard_data()
        self.assertIn("kpis", data)
        self.assertIn("connected_devices", data["kpis"])
        self.assertIn("systems", data)
        self.assertIn("attention", data)
