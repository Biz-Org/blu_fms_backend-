# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceAuditsBoard(ComplianceCase):
    def _create_audit(self, **extra):
        vals = {
            "name": "Q3 Safety Review",
            "kind": "audit",
            "audit_type": "internal",
            "date_planned": fields.Date.today() + timedelta(days=7),
            "property_id": self.property.id,
            "building_id": self.building.id,
            "template_id": self.template.id,
            "assigned_user_id": self.manager.id,
        }
        vals.update(extra)
        return self.env["compliance.audit"].with_user(self.manager).create(vals)

    def test_audit_kpis_and_workflow_with_finding(self):
        self._create_audit(name="Scheduled Month", date_planned=fields.Date.today())
        overdue = self._create_audit(
            name="Overdue Audit",
            date_planned=fields.Date.today() - timedelta(days=3),
        )
        running = self._create_audit(name="Running")
        running.action_start()

        kpis = self.env["compliance.audit"].with_user(self.manager).get_audit_kpis()
        self.assertGreaterEqual(kpis["scheduled_month"], 1)
        self.assertGreaterEqual(kpis["in_progress"], 1)
        self.assertTrue(overdue.is_overdue)
        self.assertGreaterEqual(kpis["overdue"], 1)

        self.assertEqual(len(running.line_ids), 2)
        running.line_ids[0].result = "compliant"
        with self.assertRaises(UserError):
            running.action_complete()
        running.line_ids[1].result = "non_compliant"
        running.action_complete()
        self.assertEqual(running.state, "completed")

        finding = (
            self.env["compliance.finding"]
            .with_user(self.manager)
            .create(
                {
                    "name": "Blocked exit",
                    "audit_id": running.id,
                    "audit_line_id": running.line_ids[1].id,
                    "severity": "high",
                }
            )
        )
        finding.action_convert_to_non_compliance()
        self.assertEqual(finding.state, "converted")
        self.assertTrue(finding.non_compliance_id)

        # overdue search used by OWL filter
        overdue_count = self.env["compliance.audit"].search_count([("is_overdue", "=", True)])
        self.assertGreaterEqual(overdue_count, 1)
        self.assertIn(overdue.id, self.env["compliance.audit"].search([("is_overdue", "=", True)]).ids)

    def test_auditor_cannot_create_audit(self):
        with self.assertRaises(AccessError):
            self.env["compliance.audit"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized",
                    "kind": "inspection",
                    "inspection_type": "safety",
                    "date_planned": fields.Date.today(),
                    "property_id": self.property.id,
                }
            )
