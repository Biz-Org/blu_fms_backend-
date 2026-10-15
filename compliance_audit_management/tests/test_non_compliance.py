# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceNonComplianceBoard(ComplianceCase):
    def _create_nc(self, **extra):
        vals = {
            "name": "Blocked exit corridor",
            "severity": "high",
            "source": "manual",
            "due_date": fields.Date.today() + timedelta(days=5),
            "property_id": self.property.id,
            "assigned_user_id": self.manager.id,
        }
        vals.update(extra)
        return self.env["compliance.non.compliance"].with_user(self.manager).create(vals)

    def test_nc_kpis_and_corrective_action_workflow(self):
        self._create_nc(name="Open Assigned")
        overdue = self._create_nc(
            name="Overdue NC",
            due_date=fields.Date.today() - timedelta(days=2),
            assigned_user_id=False,
        )
        self.assertEqual(overdue.state, "open")
        self.assertTrue(overdue.is_overdue)

        running = self._create_nc(name="Running NC")
        running.action_start()
        self.assertEqual(running.state, "in_progress")

        kpis = self.env["compliance.non.compliance"].with_user(self.manager).get_nc_kpis()
        self.assertGreaterEqual(kpis["open"], 1)
        self.assertGreaterEqual(kpis["overdue"], 1)
        self.assertGreaterEqual(kpis["high_severity"], 1)

        action = (
            self.env["compliance.action"]
            .with_user(self.manager)
            .create(
                {
                    "name": "Clear corridor",
                    "non_compliance_id": running.id,
                    "deadline": fields.Date.today() + timedelta(days=2),
                    "assigned_user_id": self.manager.id,
                }
            )
        )
        action.action_start()
        self.assertEqual(action.state, "in_progress")
        action.action_submit_verification()

        with self.assertRaises(UserError):
            running.action_submit_verification()

        verifier = new_test_user(
            self.env,
            login="ca_nc_verifier",
            groups="compliance_audit_management.group_compliance_manager",
        )
        action.with_user(verifier).action_verify()
        action.with_user(verifier).action_close()
        running.action_submit_verification()
        self.assertEqual(running.state, "pending_verification")
        running.action_resolve()
        running.action_close()
        self.assertEqual(running.state, "closed")

        overdue_count = self.env["compliance.non.compliance"].search_count(
            [("is_overdue", "=", True)]
        )
        self.assertGreaterEqual(overdue_count, 1)

    def test_auditor_cannot_create_nc_or_action(self):
        with self.assertRaises(AccessError):
            self.env["compliance.non.compliance"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized",
                    "severity": "low",
                    "due_date": fields.Date.today(),
                }
            )
        nc = self._create_nc(name="RO Guard")
        with self.assertRaises(AccessError):
            self.env["compliance.action"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized CA",
                    "non_compliance_id": nc.id,
                    "deadline": fields.Date.today(),
                }
            )
