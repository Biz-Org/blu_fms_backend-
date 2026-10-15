# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceInstall(ComplianceCase):
    def test_module_models_exist(self):
        for model in (
            "compliance.requirement",
            "compliance.checklist.template",
            "compliance.check",
            "compliance.audit",
            "compliance.finding",
            "compliance.non.compliance",
            "compliance.action",
            "compliance.document",
            "compliance.regulatory.report",
            "compliance.alert",
            "compliance.dashboard",
        ):
            self.assertIn(model, self.env)

    def test_groups_exist(self):
        self.assertTrue(self.env.ref("compliance_audit_management.group_compliance_manager"))
        self.assertTrue(self.env.ref("compliance_audit_management.group_compliance_auditor"))

    def test_dashboard_payload(self):
        data = self.env["compliance.dashboard"].get_dashboard_data()
        self.assertIn("kpis", data)
        self.assertIn("overall_compliance_rate", data["kpis"])
        self.assertIn("health_by_category", data)
        self.assertIn("attention", data)
        self.assertIn("upcoming_activities", data)
