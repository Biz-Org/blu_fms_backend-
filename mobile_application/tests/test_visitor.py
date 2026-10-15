# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileVisitor(MobileApplicationCase):
    def test_visitor_creation_and_approval(self):
        payload = {
            "name": "Guest One",
            "purpose": "Delivery",
            "expected_start": fields.Datetime.to_string(fields.Datetime.now()),
        }
        created = self.api.with_user(self.resident).create_visitor(payload, idempotency_key="v-test-1")
        self.assertEqual(created["state"], "submitted")
        self.api.with_user(self.resident).visitor_action(created["id"], "approve")
        verified = self.env["mobile.visitor"].browse(created["id"])
        self.assertEqual(verified.state, "approved")

    def test_security_verification(self):
        visitor = self.env["mobile.visitor"].with_user(self.resident).create({
            "name": "Guest Two",
            "purpose": "Meeting",
            "expected_start": fields.Datetime.now(),
            "resident_user_id": self.resident.id,
            "state": "approved",
        })
        self.api.with_user(self.security).visitor_action(visitor.id, "verify")
        self.assertEqual(visitor.state, "verified")

    def test_resident_isolation(self):
        from odoo.tests.common import new_test_user

        other_resident = new_test_user(
            self.env,
            login="mob_resident_b",
            groups="mobile_application.group_mobile_resident",
        )
        visitor = self.env["mobile.visitor"].with_user(self.resident).create({
            "name": "Guest Three",
            "purpose": "Visit",
            "expected_start": fields.Datetime.now(),
            "resident_user_id": self.resident.id,
        })
        with self.assertRaises(AccessError):
            self.env["mobile.visitor"].with_user(other_resident).browse(visitor.id).read(["name"])
