# -*- coding: utf-8 -*-

from odoo.modules.module import get_manifest
from odoo.tests import tagged

from .common import ReportsAnalyticsCase


@tagged("post_install", "-at_install")
class TestReportsAnalyticsInstall(ReportsAnalyticsCase):
    def test_models_exist(self):
        for model in (
            "analytics.report",
            "analytics.data.source",
            "analytics.report.execution",
            "analytics.kpi",
            "analytics.dashboard",
            "analytics.audit.log",
            "analytics.report.schedule",
            "analytics.alert",
            "analytics.query.engine",
            "analytics.dashboard.service",
        ):
            self.assertIn(model, self.env)

    def test_groups_exist(self):
        self.env.ref("reports_analytics.group_analytics_management")
        self.env.ref("reports_analytics.group_analytics_admin")
        self.env.ref("reports_analytics.group_analytics_manager")

    def test_backend_assets_registered(self):
        manifest = get_manifest("reports_analytics")
        backend = " ".join(str(item) for item in manifest.get("assets", {}).get("web.assets_backend", []))
        self.assertIn("reports_analytics/static/src/scss/_tokens.scss", backend)
        self.assertIn("reports_analytics/static/src/owl/ui", backend)
        self.assertIn("reports_analytics/static/src/owl/screens", backend)

    def test_root_menu_uses_client_action(self):
        menu = self.env.ref("reports_analytics.menu_analytics_root")
        action = self.env.ref("reports_analytics.action_ra_dashboard")
        self.assertEqual(menu.action, action)
        self.assertEqual(action.type, "ir.actions.client")
        self.assertEqual(action.tag, "reports_analytics.action_dashboard")
        self.assertEqual(action.path, "analytics-reports")
        native = self.env.ref("reports_analytics.action_analytics_report")
        self.assertEqual(native.type, "ir.actions.act_window")
        self.assertNotEqual(native.path, "analytics-reports")
