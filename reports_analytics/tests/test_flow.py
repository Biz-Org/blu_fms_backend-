# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import ReportsAnalyticsCase


@tagged("post_install", "-at_install")
class TestReportsAnalyticsFlow(ReportsAnalyticsCase):
    def test_report_create_persist_and_execute(self):
        Report = self.env["analytics.report"].with_user(self.manager)
        detail = Report.action_save_draft({
            "name": "Partner Directory",
            "report_type": "tabular",
            "data_source_id": self.source.id,
            "config": {
                "data_source_id": self.source.id,
                "visualization": "table",
                "fields": ["name", "email"],
                "metrics": [{"name": "__count", "label": "Count", "aggregation": "count"}],
                "filters": {"date_range": "last_90"},
            },
        })
        self.assertTrue(detail["id"])
        report = Report.browse(detail["id"])
        self.assertEqual(report.status, "draft")
        self.assertEqual(report.config_json["fields"], ["name", "email"])

        generated = Report.action_generate({
            "name": report.name,
            "data_source_id": self.source.id,
            "config": report.get_config(),
            "output_format": "csv",
        }, report.id)
        report.invalidate_recordset()
        self.assertTrue(report.generated_date)
        self.assertEqual(generated["execution"]["status"], "success")
        self.assertTrue(report.execution_ids)
        self.assertIn("columns", generated["execution"]["result"])

    def test_unavailable_source_preview(self):
        payload = self.env["analytics.query.engine"].execute_config({
            "data_source_id": self.missing_source.id,
            "visualization": "table",
            "fields": ["name"],
        })
        self.assertFalse(payload["available"])
        self.assertTrue(payload["reason"])

    def test_kpi_calculation(self):
        kpi = self.env["analytics.kpi"].with_user(self.manager).create({
            "name": "Partner Count",
            "category": "operations",
            "data_source_id": self.source.id,
            "source_model": "res.partner",
            "aggregation": "count",
            "target": 1,
        })
        snapshot = kpi.compute_snapshot({"date_range": "this_year"})
        self.assertTrue(snapshot["available"])
        self.assertGreaterEqual(snapshot["value"], 1)

    def test_dashboard_access_payload(self):
        data = self.env["analytics.dashboard.service"].with_user(self.manager).get_analytics_dashboard({})
        self.assertIn("kpis", data)
        self.assertEqual(len(data["kpis"]), 6)
        dashboard = self.env["analytics.dashboard"].with_user(self.manager).action_create_from_ui({
            "name": "Ops board",
            "dashboard_type": "operational",
        })
        self.assertTrue(dashboard["id"])

    def test_schedule_creates_execution(self):
        report = self.env["analytics.report"].with_user(self.manager).create({
            "name": "Scheduled Partners",
            "source_module": "base",
            "data_source_id": self.source.id,
            "config_json": {"data_source_id": self.source.id, "fields": ["name"], "visualization": "table"},
            "status": "active",
        })
        schedule = self.env["analytics.report.schedule"].with_user(self.manager).action_create_from_ui({
            "report_id": report.id,
            "recipient_ids": [self.manager.id],
            "frequency": "daily",
            "output_format": "csv",
        })
        self.assertTrue(schedule["id"])
        record = self.env["analytics.report.schedule"].browse(schedule["id"])
        record.with_user(self.manager).action_run_now()
        self.assertTrue(report.execution_ids)
        self.assertEqual(report.execution_ids[:1].status, "success")

    def test_alert_configuration_and_evaluation(self):
        kpi = self.env["analytics.kpi"].with_user(self.manager).create({
            "name": "Always Partners",
            "category": "operations",
            "data_source_id": self.source.id,
            "source_model": "res.partner",
            "aggregation": "count",
            "target": 0,
        })
        alert = self.env["analytics.alert"].with_user(self.manager).action_create_from_ui({
            "name": "Too many partners",
            "kpi_id": kpi.id,
            "condition": "gte",
            "threshold": 1,
            "severity": "warning",
            "recipient_ids": [self.manager.id],
            "frequency": "every",
        })
        self.assertTrue(alert["id"])
        record = self.env["analytics.alert"].browse(alert["id"])
        record.action_evaluate()
        self.assertTrue(record.is_triggered)

    def test_security_rbac(self):
        report_vals = {
            "name": "Secret",
            "source_module": "base",
            "data_source_id": self.source.id,
        }
        with self.assertRaises(AccessError):
            self.env["analytics.report"].with_user(self.other).create(report_vals)
        with self.assertRaises(AccessError):
            self.env["analytics.report"].with_user(self.management).create(report_vals)
        report = self.env["analytics.report"].with_user(self.manager).create(report_vals)
        self.assertTrue(
            self.env["analytics.report"].with_user(self.management).browse(report.id).name
        )

    def test_company_isolation(self):
        company_b = self.env["res.company"].create({"name": "Analytics Co B"})
        report = self.env["analytics.report"].create({
            "name": "Company A report",
            "source_module": "base",
            "company_id": self.env.company.id,
        })
        other_user = new_test_user(
            self.env,
            login="ra_company_b",
            groups="reports_analytics.group_analytics_manager",
            company_id=company_b.id,
            company_ids=[(6, 0, [company_b.id])],
        )
        hidden = self.env["analytics.report"].with_user(other_user).search([("id", "=", report.id)])
        self.assertFalse(hidden)

    def test_financial_restricted_for_manager(self):
        payload = self.env["analytics.dashboard.service"].with_user(self.manager).get_financial_analytics({})
        self.assertTrue(payload.get("restricted") or not payload.get("available"))
