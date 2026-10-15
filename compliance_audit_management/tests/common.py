# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, new_test_user


class ComplianceCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env,
            login="ca_manager",
            groups="compliance_audit_management.group_compliance_manager",
        )
        cls.auditor = new_test_user(
            cls.env,
            login="ca_auditor",
            groups="compliance_audit_management.group_compliance_auditor",
        )
        cls.property = cls.env["compliance.property"].create(
            {"name": "HQ Campus", "code": "HQ"}
        )
        cls.building = cls.env["compliance.building"].create(
            {"name": "Tower A", "code": "A", "property_id": cls.property.id}
        )
        cls.area = cls.env["compliance.area"].create(
            {"name": "Ground Floor", "building_id": cls.building.id}
        )
        cls.requirement = cls.env["compliance.requirement"].create(
            {
                "name": "Annual Fire Safety",
                "code": "FIRE-001",
                "category": "fire_life_safety",
            }
        )
        cls.template = cls.env["compliance.checklist.template"].create(
            {
                "name": "Standard Fire Walkthrough",
                "category": "fire_life_safety",
                "requirement_ids": [(6, 0, cls.requirement.ids)],
                "item_ids": [
                    (0, 0, {"name": "Extinguishers inspected", "sequence": 10}),
                    (0, 0, {"name": "Exits clear", "sequence": 20}),
                ],
            }
        )
