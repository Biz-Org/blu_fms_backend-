# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import FireSafetyCase


@tagged("post_install", "-at_install")
class TestFireSafetyEquipment(FireSafetyCase):
    def test_due_and_expired_states(self):
        today = self.today
        operational = self.env["fire.safety.equipment"].create({
            "name": "Extinguisher A",
            "code": "FE-A",
            "equipment_type": "fire_extinguisher",
            "property_id": self.property.id,
            "inspection_due_date": today + timedelta(days=30),
            "service_due_date": today + timedelta(days=60),
            "expiry_date": today + timedelta(days=90),
        })
        self.assertEqual(operational.state, "operational")

        inspection_due = operational.copy({"code": "FE-B", "inspection_due_date": today})
        self.assertEqual(inspection_due.state, "inspection_due")

        service_due = operational.copy({
            "code": "FE-C",
            "inspection_due_date": today + timedelta(days=10),
            "service_due_date": today,
        })
        self.assertEqual(service_due.state, "service_due")

        expired = operational.copy({
            "code": "FE-D",
            "expiry_date": today - timedelta(days=1),
        })
        self.assertEqual(expired.state, "expired")

        faulty = operational.copy({"code": "FE-E", "condition": "faulty"})
        self.assertEqual(faulty.state, "faulty")

        replaced = operational.copy({"code": "FE-F", "condition": "replaced"})
        self.assertEqual(replaced.state, "replaced")

    def test_cron_refreshes_due_status(self):
        equipment = self.env["fire.safety.equipment"].create({
            "name": "Hydrant",
            "code": "FH-1",
            "equipment_type": "fire_hydrant",
            "inspection_due_date": self.today + timedelta(days=5),
        })
        self.assertEqual(equipment.state, "operational")
        equipment.inspection_due_date = self.today - timedelta(days=1)
        equipment.status_as_of = self.today
        self.assertEqual(equipment.state, "inspection_due")
        self.env["fire.safety.equipment"]._cron_refresh_equipment_status()
        self.assertEqual(equipment.state, "inspection_due")

    def test_compliance_is_not_hardcoded(self):
        Dashboard = self.env["fire.safety.dashboard"]
        data = Dashboard.compute_compliance(self.company)
        expected = round(
            data["inspection_score"] * 0.4
            + data["equipment_score"] * 0.3
            + data["action_score"] * 0.3,
            2,
        )
        self.assertEqual(data["compliance"], expected)
        self.assertEqual(data["target"], 95.0)
        self.assertNotEqual(data["compliance"], data["target"])
