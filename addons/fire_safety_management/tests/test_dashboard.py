# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import FireSafetyCase


@tagged("post_install", "-at_install")
class TestFireSafetyDashboard(FireSafetyCase):
    def test_manager_dashboard_uses_live_counts(self):
        self.env["fire.safety.inspection"].create(self._inspection_vals())
        self.env["fire.safety.incident"].with_user(self.manager).action_report_incident({
            "incident_type": "safety_hazard",
            "severity": "low",
            "description": "<p>Dashboard incident</p>",
        })
        data = self.env["fire.safety.dashboard"].with_user(self.manager).get_dashboard_data()
        self.assertTrue(data["compliance"])
        self.assertNotEqual(data["compliance"]["compliance"], data["compliance"]["target"])
        self.assertGreaterEqual(data["inspection_counts"].get("scheduled", 0), 1)
        self.assertGreaterEqual(data["incident_counts"].get("open", 0), 1)
        self.assertIn("overdue_inspections", data)
        self.assertIn("recent_incidents", data)
        self.assertIn("upcoming_drills", data)

    def test_guard_dashboard_does_not_raise(self):
        self.env["fire.safety.inspection"].create(self._inspection_vals())
        own = self.env["fire.safety.incident"].with_user(self.guard).action_report_incident({
            "incident_type": "safety_hazard",
            "severity": "low",
            "description": "<p>Guard incident</p>",
        })
        data = self.env["fire.safety.dashboard"].with_user(self.guard).get_dashboard_data()
        self.assertFalse(data["compliance"])
        self.assertEqual(data["inspection_counts"], {})
        self.assertEqual(data["equipment_counts"], {})
        self.assertEqual(data["drill_counts"], {})
        self.assertEqual(data["open_actions"], 0)
        self.assertEqual(data["incident_counts"].get("open", 0), 1)
        self.assertEqual(data["recent_incidents"][0]["id"], own.id)

    def test_auditor_dashboard_is_read_only_data(self):
        self.env["fire.safety.inspection"].create(self._inspection_vals())
        data = self.env["fire.safety.dashboard"].with_user(self.auditor).get_dashboard_data()
        self.assertTrue(data["compliance"])
        self.assertGreaterEqual(sum(data["inspection_counts"].values()), 1)

    def test_upcoming_drill_is_listed(self):
        self.env["fire.safety.drill"].create({
            "name": "Evacuation drill",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": fields.Datetime.now() + timedelta(days=2),
            "property_id": self.property.id,
            "company_id": self.company.id,
        })
        data = self.env["fire.safety.dashboard"].with_user(self.manager).get_dashboard_data()
        self.assertTrue(any(row["name"] == "Evacuation drill" for row in data["upcoming_drills"]))
