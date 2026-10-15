# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceReports(ComplianceCase):
    def test_get_compliance_reports_payload(self):
        today = fields.Date.today()
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Report Check",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today,
            }
        )
        self.env["compliance.audit"].with_user(self.manager).create(
            {
                "name": "Report Audit",
                "kind": "audit",
                "audit_type": "internal",
                "date_planned": today,
                "property_id": self.property.id,
            }
        )

        payload = (
            self.env["compliance.dashboard"]
            .with_user(self.manager)
            .get_compliance_reports("checks", self.property.id, False, False, 0, 20)
        )
        self.assertIn("kpis", payload)
        self.assertIn("overall_compliance_rate", payload["kpis"])
        self.assertTrue(payload["status_blocks"])
        self.assertEqual(payload["dataset"], "checks")
        self.assertGreaterEqual(payload["total"], 1)
        self.assertTrue(any(row["name"] == "Report Check" for row in payload["records"]))

        audits = (
            self.env["compliance.dashboard"]
            .with_user(self.auditor)
            .get_compliance_reports("audits", False, False, False, 0, 20)
        )
        self.assertEqual(audits["dataset"], "audits")
        self.assertGreaterEqual(audits["total"], 1)

    def test_reports_date_filter(self):
        today = fields.Date.today()
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "In Range",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today,
            }
        )
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Out of Range",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today + timedelta(days=60),
            }
        )
        payload = self.env["compliance.dashboard"].get_compliance_reports(
            "checks",
            False,
            fields.Date.to_string(today - timedelta(days=1)),
            fields.Date.to_string(today + timedelta(days=1)),
            0,
            50,
        )
        names = {row["name"] for row in payload["records"]}
        self.assertIn("In Range", names)
        self.assertNotIn("Out of Range", names)
