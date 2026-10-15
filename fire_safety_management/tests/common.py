# -*- coding: utf-8 -*-

from datetime import timedelta
from uuid import uuid4

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class FireSafetyCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        suffix = uuid4().hex[:8]
        cls.company = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": f"FS Other Company {suffix}"})
        cls.property = cls.env["fire.safety.property"].create({
            "name": "Plaza One",
            "code": f"P-{suffix}",
            "company_id": cls.company.id,
        })
        cls.building = cls.env["fire.safety.building"].create({
            "name": "Tower A",
            "code": f"TA-{suffix}",
            "property_id": cls.property.id,
        })
        cls.area = cls.env["fire.safety.area"].create({
            "name": "Floor 3",
            "code": f"F3-{suffix}",
            "building_id": cls.building.id,
            "area_kind": "floor",
        })
        cls.template = cls.env["fire.safety.checklist.template"].create({
            "name": "Test Fire Checklist",
            "inspection_type": "fire_inspection",
            "company_id": cls.company.id,
        })
        cls.env["fire.safety.checklist.item"].create([
            {
                "template_id": cls.template.id,
                "name": "Extinguishers present",
                "category": "fire_extinguishers",
                "sequence": 10,
                "required": True,
            },
            {
                "template_id": cls.template.id,
                "name": "Exits clear",
                "category": "fire_exits",
                "sequence": 20,
                "required": True,
            },
        ])
        cls.manager = new_test_user(
            cls.env,
            login=f"fs_manager_{suffix}",
            groups="fire_safety_management.group_fire_safety_manager",
        )
        cls.security = new_test_user(
            cls.env,
            login=f"fs_security_{suffix}",
            groups="fire_safety_management.group_fire_safety_security",
        )
        cls.guard = new_test_user(
            cls.env,
            login=f"fs_guard_{suffix}",
            groups="fire_safety_management.group_fire_safety_guard",
        )
        cls.auditor = new_test_user(
            cls.env,
            login=f"fs_auditor_{suffix}",
            groups="fire_safety_management.group_fire_safety_auditor",
        )
        cls.manager_b = new_test_user(
            cls.env,
            login=f"fs_manager_b_{suffix}",
            groups="fire_safety_management.group_fire_safety_manager",
            company_id=cls.company_b.id,
            company_ids=[(6, 0, [cls.company_b.id])],
        )
        cls.today = fields.Date.context_today(cls.env.user)
        cls.now = fields.Datetime.now()

    def _inspection_vals(self, **extra):
        vals = {
            "inspection_type": "fire_inspection",
            "scheduled_date": self.today,
            "property_id": self.property.id,
            "building_id": self.building.id,
            "area_id": self.area.id,
            "assigned_user_id": self.manager.id,
            "checklist_template_id": self.template.id,
            "company_id": self.company.id,
        }
        vals.update(extra)
        return vals
