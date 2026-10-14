# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import FireSafetyCase


@tagged("post_install", "-at_install")
class TestFireSafetySecurity(FireSafetyCase):
    def test_guard_own_incident_scope(self):
        own = self.env["fire.safety.incident"].with_user(self.guard).action_report_incident({
            "incident_type": "safety_hazard",
            "severity": "low",
            "description": "<p>Own report.</p>",
        })
        other = self.env["fire.safety.incident"].with_user(self.security).action_report_incident({
            "incident_type": "electrical",
            "severity": "medium",
            "description": "<p>Security report.</p>",
        })
        visible = self.env["fire.safety.incident"].with_user(self.guard).search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)

    def test_security_cannot_verify_or_close_action(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        finding = self.env["fire.safety.finding"].create({
            "name": "Finding",
            "inspection_id": inspection.id,
        })
        action = self.env["fire.safety.action"].create({
            "name": "Fix it",
            "finding_id": finding.id,
            "deadline": self.today,
            "assigned_user_id": self.security.id,
        })
        action.with_user(self.security).action_mark_done()
        with self.assertRaises(AccessError):
            action.with_user(self.security).action_verify()
        with self.assertRaises(AccessError):
            action.with_user(self.security).action_close()

    def test_manager_cannot_verify_own_action(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        finding = self.env["fire.safety.finding"].create({
            "name": "Own finding",
            "inspection_id": inspection.id,
        })
        action = self.env["fire.safety.action"].with_user(self.manager).create({
            "name": "Own action",
            "finding_id": finding.id,
            "deadline": self.today,
            "assigned_user_id": self.manager.id,
        })
        action.with_user(self.manager).action_mark_done()
        with self.assertRaises(AccessError):
            action.with_user(self.manager).action_verify()

    def test_auditor_cannot_create_inspection(self):
        Inspection = self.env["fire.safety.inspection"].with_user(self.auditor)
        with self.assertRaises(AccessError):
            Inspection.create(self._inspection_vals())

    def test_guard_cannot_manage_equipment(self):
        with self.assertRaises(AccessError):
            self.env["fire.safety.equipment"].with_user(self.guard).create({
                "name": "Extinguisher",
                "code": "FE-GUARD",
                "equipment_type": "fire_extinguisher",
            })

    def test_security_cannot_complete_inspection(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        inspection.with_user(self.security).action_start_inspection()
        inspection.line_ids.write({"result": "pass"})
        with self.assertRaises(AccessError):
            inspection.with_user(self.security).action_complete_inspection()

    def test_company_scope(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        visible = self.env["fire.safety.inspection"].with_user(self.manager_b).search([])
        self.assertNotIn(inspection, visible)

    def test_guard_cannot_activate_emergency(self):
        with self.assertRaises(AccessError):
            self.env["fire.safety.emergency"].with_user(self.guard).action_activate_emergency({
                "emergency_type": "fire",
                "severity": "high",
            })
