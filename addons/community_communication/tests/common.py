# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class CommunityCommunicationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.community = cls.env["community.communication.community"].create({
            "name": "Riverside",
            "code": "RIV",
        })
        cls.building_a = cls.env["community.communication.building"].create({
            "name": "Tower A",
            "community_id": cls.community.id,
        })
        cls.building_b = cls.env["community.communication.building"].create({
            "name": "Tower B",
            "community_id": cls.community.id,
        })
        cls.unit_a = cls.env["community.communication.unit"].create({
            "name": "101",
            "building_id": cls.building_a.id,
        })
        cls.unit_b = cls.env["community.communication.unit"].create({
            "name": "202",
            "building_id": cls.building_b.id,
        })
        cls.officer = new_test_user(
            cls.env,
            login="cc_officer",
            groups="community_communication.group_community_officer",
        )
        cls.portal_user = new_test_user(
            cls.env,
            login="cc_resident",
            groups="community_communication.group_community_resident",
        )
        cls.portal_user_b = new_test_user(
            cls.env,
            login="cc_resident_b",
            groups="community_communication.group_community_resident",
        )
        cls.resident = cls.env["community.communication.resident"].create({
            "partner_id": cls.portal_user.partner_id.id,
            "user_id": cls.portal_user.id,
            "community_id": cls.community.id,
            "unit_id": cls.unit_a.id,
        })
        cls.resident_b = cls.env["community.communication.resident"].create({
            "partner_id": cls.portal_user_b.partner_id.id,
            "user_id": cls.portal_user_b.id,
            "community_id": cls.community.id,
            "unit_id": cls.unit_b.id,
        })
        cls.other_community = cls.env["community.communication.community"].create({
            "name": "Lakeside",
            "code": "LAK",
        })
