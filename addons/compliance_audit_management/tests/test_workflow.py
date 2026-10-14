# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceWorkflow(ComplianceCase):
    def test_check_to_finding_to_nc_to_action(self):
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Annual Extinguisher Check",
                "requirement_id": self.requirement.id,
                "template_id": self.template.id,
                "property_id": self.property.id,
                "building_id": self.building.id,
                "area_id": self.area.id,
                "assigned_user_id": self.manager.id,
                "due_date": fields.Date.today() + timedelta(days=7),
            }
        )
        self.assertEqual(len(check.line_ids), 2)
        check.action_start()
        self.assertEqual(check.state, "in_progress")
        check.line_ids[0].result = "compliant"
        check.line_ids[1].result = "non_compliant"
        check.action_complete()
        self.assertEqual(check.state, "completed")

        finding = self.env["compliance.finding"].with_user(self.manager).create(
            {
                "name": "Exit blocked",
                "check_id": check.id,
                "check_line_id": check.line_ids[1].id,
                "severity": "high",
            }
        )
        finding.action_convert_to_non_compliance()
        self.assertEqual(finding.state, "converted")
        nc = finding.non_compliance_id
        self.assertTrue(nc)
        self.assertEqual(nc.severity, "high")

        action = self.env["compliance.action"].with_user(self.manager).create(
            {
                "name": "Clear exit path",
                "non_compliance_id": nc.id,
                "deadline": fields.Date.today() + timedelta(days=3),
                "assigned_user_id": self.manager.id,
            }
        )
        action.action_start()
        action.action_submit_verification()
        with self.assertRaises(AccessError):
            action.action_verify()

        verifier = new_test_user(
            self.env,
            login="ca_verifier",
            groups="compliance_audit_management.group_compliance_manager",
        )
        action.with_user(verifier).action_verify()
        self.assertEqual(action.state, "verified")
        action.with_user(verifier).action_close()
        self.assertEqual(action.state, "closed")

    def test_auditor_cannot_create_check(self):
        with self.assertRaises(AccessError):
            self.env["compliance.check"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized",
                    "requirement_id": self.requirement.id,
                    "due_date": fields.Date.today(),
                }
            )

    def test_invalid_state_write_blocked(self):
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "State guard",
                "requirement_id": self.requirement.id,
                "due_date": fields.Date.today(),
            }
        )
        with self.assertRaises(UserError):
            check.with_user(self.manager).write({"state": "completed"})
