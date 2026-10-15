# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceCalendar(ComplianceCase):
    def test_get_calendar_events_across_types(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Calendar Check",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today,
                "assigned_user_id": self.manager.id,
            }
        )
        audit = self.env["compliance.audit"].with_user(self.manager).create(
            {
                "name": "Calendar Audit",
                "kind": "audit",
                "audit_type": "internal",
                "date_planned": today + timedelta(days=2),
                "property_id": self.property.id,
                "assigned_user_id": self.manager.id,
            }
        )
        doc = self.env["compliance.document"].with_user(self.manager).create(
            {
                "name": "Calendar Certificate",
                "document_type": "certificate",
                "property_id": self.property.id,
                "issue_date": today - timedelta(days=30),
                "expiry_date": today + timedelta(days=5),
            }
        )
        nc = self.env["compliance.non.compliance"].with_user(self.manager).create(
            {
                "name": "Calendar NC",
                "severity": "medium",
                "due_date": today + timedelta(days=3),
                "property_id": self.property.id,
            }
        )

        events = (
            self.env["compliance.dashboard"]
            .with_user(self.manager)
            .get_calendar_events(
                fields.Date.to_string(month_start),
                fields.Date.to_string(month_end),
            )
        )
        keys = {row["key"] for row in events}
        self.assertIn(f"check-{check.id}", keys)
        self.assertIn(f"audit-{audit.id}", keys)
        self.assertIn(f"document-{doc.id}", keys)
        self.assertIn(f"nc-{nc.id}", keys)

        filtered = (
            self.env["compliance.dashboard"]
            .with_user(self.manager)
            .get_calendar_events(
                fields.Date.to_string(month_start),
                fields.Date.to_string(month_end),
                ["check"],
            )
        )
        self.assertTrue(all(row["type"] == "check" for row in filtered))
        self.assertIn(f"check-{check.id}", {row["key"] for row in filtered})

    def test_auditor_can_read_calendar_events(self):
        today = fields.Date.today()
        self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Visible Check",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today,
            }
        )
        events = (
            self.env["compliance.dashboard"]
            .with_user(self.auditor)
            .get_calendar_events(
                fields.Date.to_string(today - timedelta(days=1)),
                fields.Date.to_string(today + timedelta(days=1)),
                ["check"],
            )
        )
        self.assertTrue(any(row["type"] == "check" for row in events))
