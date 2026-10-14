# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import FireSafetyCase


@tagged("post_install", "-at_install")
class TestFireSafetyWorkflow(FireSafetyCase):
    def test_inspection_create_copies_checklist(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        self.assertEqual(inspection.state, "scheduled")
        self.assertEqual(len(inspection.line_ids), 2)
        self.assertTrue(inspection.name.startswith("FSI-") or inspection.name != "New")

    def test_invalid_inspection_close_from_scheduled(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        with self.assertRaises(UserError):
            inspection.action_close_inspection()

    def test_complete_requires_checklist_results(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        inspection.action_start_inspection()
        with self.assertRaises(UserError):
            inspection.action_complete_inspection()

    def test_failed_line_requires_finding(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        inspection.action_start_inspection()
        inspection.line_ids.write({"result": "fail"})
        with self.assertRaises(UserError):
            inspection.action_complete_inspection()

    def test_inspection_pass_complete_close(self):
        inspection = self.env["fire.safety.inspection"].with_user(self.manager).create(
            self._inspection_vals()
        )
        inspection.with_user(self.manager).action_start_inspection()
        inspection.line_ids.with_user(self.manager).write({"result": "pass"})
        inspection.with_user(self.manager).action_complete_inspection()
        self.assertEqual(inspection.state, "completed")
        inspection.with_user(self.manager).action_close_inspection()
        self.assertEqual(inspection.state, "closed")

    def test_finding_action_verify_close(self):
        inspection = self.env["fire.safety.inspection"].create(self._inspection_vals())
        inspection.action_start_inspection()
        inspection.line_ids[0].result = "fail"
        inspection.line_ids[1].result = "pass"
        finding = self.env["fire.safety.finding"].create({
            "name": "Blocked exit",
            "inspection_id": inspection.id,
            "line_id": inspection.line_ids[0].id,
            "severity": "high",
        })
        action = self.env["fire.safety.action"].create({
            "name": "Clear the exit",
            "finding_id": finding.id,
            "deadline": self.today + timedelta(days=7),
            "assigned_user_id": self.security.id,
        })
        self.assertEqual(finding.state, "in_progress")
        inspection.action_complete_inspection()
        self.assertEqual(inspection.state, "pending")
        action.with_user(self.security).action_mark_done()
        self.assertEqual(action.state, "done")
        action.with_user(self.manager).action_verify()
        self.assertTrue(action.verified_by_id)
        action.with_user(self.manager).action_close()
        self.assertEqual(action.state, "closed")
        inspection.with_user(self.manager).action_mark_completed()
        inspection.with_user(self.manager).action_close_inspection()
        self.assertEqual(inspection.state, "closed")
        finding.with_user(self.manager).action_close_finding()
        self.assertEqual(finding.state, "closed")

    def test_direct_state_write_blocked_for_manager(self):
        inspection = self.env["fire.safety.inspection"].with_user(self.manager).create(
            self._inspection_vals()
        )
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).write({"state": "closed"})

    def test_incident_lifecycle(self):
        incident = self.env["fire.safety.incident"].with_user(self.security).action_report_incident({
            "incident_type": "fire_alarm",
            "severity": "medium",
            "description": "<p>Manual alarm mapped to fire alarm.</p>",
            "property_id": self.property.id,
        })
        self.assertEqual(incident.state, "open")
        self.assertEqual(incident.incident_type, "fire_alarm")
        incident.with_user(self.security).action_start_investigation()
        self.assertEqual(incident.state, "investigating")
        incident.with_user(self.manager).action_resolve_incident()
        self.assertEqual(incident.state, "resolved")

    def test_invalid_incident_resolve_from_open(self):
        incident = self.env["fire.safety.incident"].action_report_incident({
            "incident_type": "other",
            "severity": "low",
            "description": "<p>Other type.</p>",
        })
        with self.assertRaises(UserError):
            incident.action_resolve_incident()

    def test_drill_lifecycle(self):
        drill = self.env["fire.safety.drill"].create({
            "name": "Fire Evacuation Q1",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": self.now + timedelta(days=1),
            "property_id": self.property.id,
            "expected_participants": 20,
            "participant_ids": [(6, 0, [self.manager.id, self.security.id])],
        })
        self.assertEqual(drill.conducted_by, "Internal Safety Team")
        self.assertEqual(drill.target_participation, 100.0)
        self.assertEqual(drill.state, "scheduled")
        drill.with_user(self.manager).action_reschedule_drill(self.now + timedelta(days=2))
        self.assertEqual(drill.state, "rescheduled")
        drill.with_user(self.manager).action_confirm_reschedule()
        self.assertEqual(drill.state, "scheduled")
        drill.with_user(self.manager).action_complete_drill({
            "attendance_count": 18,
            "response_time_minutes": 4.5,
            "observations": "<p>Orderly.</p>",
        })
        self.assertEqual(drill.state, "completed")
        self.assertAlmostEqual(drill.participation_rate, 90.0)

    def test_drill_cancel(self):
        drill = self.env["fire.safety.drill"].create({
            "name": "Cancelled drill",
            "drill_type": "other",
            "scheduled_datetime": self.now + timedelta(days=3),
        })
        drill.action_cancel_drill("Weather")
        self.assertEqual(drill.state, "cancelled")
        with self.assertRaises(UserError):
            drill.action_complete_drill()

    def test_emergency_single_active(self):
        first = self.env["fire.safety.emergency"].action_activate_emergency({
            "emergency_type": "fire",
            "severity": "critical",
            "information": "<p>Smoke in lobby.</p>",
            "property_id": self.property.id,
        })
        self.assertEqual(first.state, "active")
        with self.assertRaises(ValidationError):
            self.env["fire.safety.emergency"].action_activate_emergency({
                "emergency_type": "smoke",
                "severity": "high",
            })
        first.action_close_emergency("<p>Contained.</p>")
        self.assertEqual(first.state, "closed")
        second = self.env["fire.safety.emergency"].action_activate_emergency({
            "emergency_type": "evacuation",
            "severity": "medium",
        })
        self.assertEqual(second.state, "active")

    def test_mobile_assigned_inspections(self):
        inspection = self.env["fire.safety.inspection"].create(
            self._inspection_vals(assigned_user_id=self.security.id)
        )
        assigned = self.env["fire.safety.inspection"].with_user(self.security).get_assigned_inspections()
        self.assertIn(inspection, assigned)

    def test_overdue_is_computed(self):
        inspection = self.env["fire.safety.inspection"].create(
            self._inspection_vals(scheduled_date=self.today - timedelta(days=2))
        )
        self.assertTrue(inspection.is_overdue)
        self.assertEqual(inspection.state, "scheduled")
        self.assertNotIn("overdue", dict(inspection._fields["state"].selection))
