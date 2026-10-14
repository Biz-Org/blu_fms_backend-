# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceActivitiesBoard(ComplianceCase):
    def test_activity_kpis_and_template_preview(self):
        today = fields.Date.today()
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Overdue Check",
                "requirement_id": self.requirement.id,
                "template_id": self.template.id,
                "property_id": self.property.id,
                "due_date": today - timedelta(days=2),
                "assigned_user_id": self.manager.id,
            }
        )
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Pending Check",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today + timedelta(days=5),
                "assigned_user_id": self.manager.id,
            }
        ).action_mark_pending()
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Scheduled Soon",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today + timedelta(days=10),
                "assigned_user_id": self.manager.id,
            }
        )

        kpis = self.env["compliance.check"].with_user(self.manager).get_activity_kpis()
        self.assertGreaterEqual(kpis["overdue"], 1)
        self.assertGreaterEqual(kpis["pending"], 1)
        self.assertGreaterEqual(kpis["scheduled_30d"], 1)
        self.assertIn("completion_rate", kpis)

        preview = (
            self.env["compliance.check"]
            .with_user(self.manager)
            .get_template_preview(self.template.id)
        )
        self.assertEqual(len(preview), 2)
        self.assertEqual(preview[0]["name"], "Extinguishers inspected")

        auditor_kpis = self.env["compliance.check"].with_user(self.auditor).get_activity_kpis()
        self.assertEqual(auditor_kpis["overdue"], kpis["overdue"])

    def test_auditor_cannot_write_check_or_start(self):
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "RO Guard",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": fields.Date.today() + timedelta(days=3),
            }
        )
        with self.assertRaises(AccessError):
            check.with_user(self.auditor).write({"notes": "Nope"})
        with self.assertRaises(AccessError):
            check.with_user(self.auditor).action_start()

    def test_manager_create_copies_checklist_lines(self):
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Walkthrough",
                "requirement_id": self.requirement.id,
                "template_id": self.template.id,
                "property_id": self.property.id,
                "building_id": self.building.id,
                "area_id": self.area.id,
                "due_date": fields.Date.today() + timedelta(days=14),
                "assigned_user_id": self.manager.id,
            }
        )
        self.assertEqual(check.category, "fire_life_safety")
        self.assertEqual(len(check.line_ids), 2)
        check.action_start()
        check.line_ids[0].result = "compliant"
        check.line_ids[1].result = "compliant"
        check.action_complete()
        self.assertEqual(check.state, "completed")
