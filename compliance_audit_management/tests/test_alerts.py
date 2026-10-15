# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceAlerts(ComplianceCase):
    def test_cron_generates_and_dedupes_alerts(self):
        today = fields.Date.today()
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Due Check",
                "requirement_id": self.requirement.id,
                "property_id": self.property.id,
                "due_date": today - timedelta(days=1),
                "assigned_user_id": self.manager.id,
            }
        )
        audit = self.env["compliance.audit"].with_user(self.manager).create(
            {
                "name": "Due Audit",
                "kind": "audit",
                "audit_type": "internal",
                "date_planned": today,
                "property_id": self.property.id,
                "assigned_user_id": self.manager.id,
            }
        )
        doc = self.env["compliance.document"].with_user(self.manager).create(
            {
                "name": "Expiring Cert",
                "document_type": "certificate",
                "property_id": self.property.id,
                "issue_date": today - timedelta(days=100),
                "expiry_date": today + timedelta(days=5),
                "renewal_reminder_days": "30",
                "assigned_user_id": self.manager.id,
            }
        )
        report = self.env["compliance.regulatory.report"].with_user(self.manager).create(
            {
                "name": "Due Filing",
                "regulatory_authority": "Agency",
                "reporting_period": "Q1",
                "deadline": today + timedelta(days=10),
                "owner_id": self.manager.id,
            }
        )

        Alert = self.env["compliance.alert"]
        Alert._cron_generate_alerts()

        check_alerts = Alert.search(
            [
                ("res_model", "=", "compliance.check"),
                ("res_id", "=", check.id),
                ("state", "!=", "closed"),
            ]
        )
        self.assertEqual(len(check_alerts), 1)
        self.assertEqual(check_alerts.alert_type, "compliance_check")
        self.assertEqual(check_alerts.priority, "high")

        audit_alerts = Alert.search(
            [
                ("res_model", "=", "compliance.audit"),
                ("res_id", "=", audit.id),
                ("state", "!=", "closed"),
            ]
        )
        self.assertEqual(len(audit_alerts), 1)

        doc.invalidate_recordset()
        self.assertIn(doc.state, ("expiring_soon", "renewal_due", "expired"))
        doc_alerts = Alert.search(
            [
                ("res_model", "=", "compliance.document"),
                ("res_id", "=", doc.id),
                ("state", "!=", "closed"),
            ]
        )
        self.assertEqual(len(doc_alerts), 1)
        self.assertEqual(doc_alerts.alert_type, "document_renewal")

        reg_alerts = Alert.search(
            [
                ("res_model", "=", "compliance.regulatory.report"),
                ("res_id", "=", report.id),
                ("state", "!=", "closed"),
            ]
        )
        self.assertEqual(len(reg_alerts), 1)

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "compliance.check"),
                ("res_id", "=", check.id),
                ("user_id", "=", self.manager.id),
            ]
        )
        self.assertTrue(activities)

        # idempotent second run
        Alert._cron_generate_alerts()
        self.assertEqual(
            Alert.search_count(
                [
                    ("res_model", "=", "compliance.check"),
                    ("res_id", "=", check.id),
                    ("state", "!=", "closed"),
                ]
            ),
            1,
        )

    def test_cron_closes_stale_alert_when_check_completed(self):
        today = fields.Date.today()
        check = self.env["compliance.check"].with_user(self.manager).create(
            {
                "name": "Closeable Check",
                "requirement_id": self.requirement.id,
                "template_id": self.template.id,
                "property_id": self.property.id,
                "due_date": today - timedelta(days=2),
                "assigned_user_id": self.manager.id,
            }
        )
        Alert = self.env["compliance.alert"]
        Alert._cron_generate_alerts()
        alert = Alert.search(
            [("res_model", "=", "compliance.check"), ("res_id", "=", check.id)],
            limit=1,
        )
        self.assertEqual(alert.state, "open")

        check.action_start()
        for line in check.line_ids:
            line.result = "compliant"
        check.action_complete()
        Alert._cron_generate_alerts()
        self.assertEqual(alert.state, "closed")

    def test_manager_can_acknowledge_alert(self):
        alert = self.env["compliance.alert"].with_user(self.manager).create(
            {
                "name": "Manual alert",
                "alert_type": "compliance_check",
                "priority": "medium",
                "due_date": fields.Date.today(),
            }
        )
        alert.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")
        self.assertEqual(alert.acknowledged_by_id, self.manager)
