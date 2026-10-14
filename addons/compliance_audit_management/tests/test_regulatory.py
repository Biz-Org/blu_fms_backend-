# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceRegulatoryBoard(ComplianceCase):
    def _create_report(self, **extra):
        vals = {
            "name": "Annual Safety Return",
            "regulatory_authority": "City Fire Dept",
            "reporting_period": "FY 2026",
            "deadline": fields.Date.today() + timedelta(days=20),
            "priority": "high",
            "owner_id": self.manager.id,
            "property_id": self.property.id,
            "requirement_id": self.requirement.id,
        }
        vals.update(extra)
        return self.env["compliance.regulatory.report"].with_user(self.manager).create(vals)

    def test_regulatory_kpis_and_workflow(self):
        self._create_report(name="Due Soon")
        overdue = self._create_report(
            name="Overdue Filing",
            deadline=fields.Date.today() - timedelta(days=2),
        )
        preparing = self._create_report(name="Preparing")
        preparing.action_prepare()
        self.assertEqual(preparing.state, "in_preparation")
        self.assertTrue(overdue.is_overdue)

        kpis = (
            self.env["compliance.regulatory.report"]
            .with_user(self.manager)
            .get_regulatory_kpis()
        )
        self.assertGreaterEqual(kpis["due_soon"], 1)
        self.assertGreaterEqual(kpis["overdue"], 1)
        self.assertGreaterEqual(kpis["in_preparation"], 1)

        preparing.write({"submission_reference": "ACK-100"})
        preparing.action_submit()
        self.assertEqual(preparing.state, "submitted")
        self.assertTrue(preparing.submission_date)

        kpis_after = (
            self.env["compliance.regulatory.report"]
            .with_user(self.manager)
            .get_regulatory_kpis()
        )
        self.assertGreaterEqual(kpis_after["submitted"], 1)

        overdue_count = self.env["compliance.regulatory.report"].search_count(
            [("is_overdue", "=", True)]
        )
        self.assertGreaterEqual(overdue_count, 1)

    def test_auditor_cannot_create_or_submit(self):
        with self.assertRaises(AccessError):
            self.env["compliance.regulatory.report"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized",
                    "regulatory_authority": "Agency",
                    "reporting_period": "Q1",
                    "deadline": fields.Date.today(),
                }
            )
        report = self._create_report(name="Protected")
        with self.assertRaises(AccessError):
            report.with_user(self.auditor).action_prepare()
