# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, new_test_user


class IntegrationIotCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(
            cls.env,
            login="iot_admin",
            groups="integration_iot_management.group_integration_admin",
        )
        cls.other = new_test_user(
            cls.env,
            login="iot_other",
            groups="base.group_user",
        )
        cls.property = cls.env["integration.iot.property"].create(
            {"name": "HQ Campus", "code": "HQ"}
        )
        cls.tower_a = cls.env["integration.iot.building"].create(
            {"name": "Tower A", "code": "A", "property_id": cls.property.id}
        )
        cls.lobby = cls.env["integration.iot.area"].create(
            {
                "name": "Lobby",
                "building_id": cls.tower_a.id,
                "area_kind": "area",
            }
        )
        cls.integration = cls.env["integration.iot.integration"].create(
            {
                "name": "Mock BMS",
                "system_kind": "mock",
                "state": "connected",
            }
        )
