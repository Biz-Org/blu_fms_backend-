# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ComplianceCase


@tagged("post_install", "-at_install")
class TestComplianceDocumentsBoard(ComplianceCase):
    def _create_doc(self, **extra):
        vals = {
            "name": "Fire Safety Certificate",
            "document_type": "certificate",
            "issuing_authority": "City Fire Dept",
            "property_id": self.property.id,
            "issue_date": fields.Date.today() - timedelta(days=200),
            "expiry_date": fields.Date.today() + timedelta(days=120),
            "renewal_reminder_days": "60",
            "requirement_id": self.requirement.id,
        }
        vals.update(extra)
        return self.env["compliance.document"].with_user(self.manager).create(vals)

    def test_document_kpis_and_expiry_states(self):
        self._create_doc(name="Active Doc")
        self._create_doc(
            name="Expiring Doc",
            expiry_date=fields.Date.today() + timedelta(days=20),
            renewal_reminder_days="30",
        )
        self._create_doc(
            name="Expired Doc",
            expiry_date=fields.Date.today() - timedelta(days=3),
        )

        kpis = self.env["compliance.document"].with_user(self.manager).get_document_kpis()
        self.assertGreaterEqual(kpis["active"], 1)
        self.assertGreaterEqual(kpis["expiring_soon"] + kpis["renewal_due"], 1)
        self.assertGreaterEqual(kpis["expired"], 1)

        auditor_kpis = self.env["compliance.document"].with_user(self.auditor).get_document_kpis()
        self.assertEqual(auditor_kpis["expired"], kpis["expired"])

    def test_renewal_and_archive_flow(self):
        doc = self._create_doc(
            name="Renewable Permit",
            document_type="permit",
            expiry_date=fields.Date.today() + timedelta(days=10),
            renewal_reminder_days="30",
        )
        doc.action_start_renewal()
        self.assertEqual(doc.state, "under_renewal")
        new_expiry = fields.Date.today() + timedelta(days=365)
        doc.action_mark_renewed(new_expiry_date=new_expiry)
        self.assertEqual(doc.state, "active")
        self.assertEqual(doc.expiry_date, new_expiry)
        self.assertTrue(doc.history_ids.filtered(lambda h: h.event_type == "renewed"))

        doc.action_archive()
        self.assertEqual(doc.state, "archived")
        self.assertTrue(doc.history_ids.filtered(lambda h: h.event_type == "archived"))

    def test_auditor_cannot_create_or_renew(self):
        with self.assertRaises(AccessError):
            self.env["compliance.document"].with_user(self.auditor).create(
                {
                    "name": "Unauthorized",
                    "document_type": "license",
                    "expiry_date": fields.Date.today() + timedelta(days=30),
                    "property_id": self.property.id,
                }
            )
        doc = self._create_doc(name="Protected")
        with self.assertRaises(AccessError):
            doc.with_user(self.auditor).action_start_renewal()
