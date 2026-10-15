# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDrillCommunityAnnouncement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.community = cls.env["community.communication.community"].create({
            "name": "Bridge Community",
            "code": "BRG",
        })
        cls.officer = new_test_user(
            cls.env,
            login="fs_cc_officer",
            groups=(
                "fire_safety_management.group_fire_safety_manager,"
                "community_communication.group_community_officer"
            ),
        )
        cls.user_a = new_test_user(
            cls.env,
            login="fs_user_a",
            groups="base.group_user,fire_safety_management.group_fire_safety_security",
        )
        cls.user_b = new_test_user(
            cls.env,
            login="fs_user_b",
            groups="base.group_user,fire_safety_management.group_fire_safety_guard",
        )
        cls.user_c = new_test_user(
            cls.env,
            login="fs_user_c",
            groups="base.group_user,fire_safety_management.group_fire_safety_facility",
        )

    def test_create_drill_targets_selected_users_without_residents(self):
        drill = self.env["fire.safety.drill"].with_user(self.officer).create({
            "name": "Evacuation Drill Q1",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": fields.Datetime.now() + timedelta(days=2),
            "conducted_by": "Safety Team",
            "participant_ids": [(6, 0, [self.user_a.id, self.user_b.id])],
        })
        self.assertTrue(drill.cc_announcement_id)
        announcement = drill.cc_announcement_id
        self.assertEqual(announcement.state, "published")
        self.assertEqual(announcement.audience_type, "users")
        self.assertEqual(set(announcement.audience_user_ids.ids), {self.user_a.id, self.user_b.id})
        self.assertIn("Evacuation Drill Q1", announcement.title)
        self.assertIn("mock drill has been scheduled for you", announcement.body.lower())

        visible_a = announcement.with_user(self.user_a).search([("id", "=", announcement.id)])
        visible_b = announcement.with_user(self.user_b).search([("id", "=", announcement.id)])
        hidden_c = announcement.with_user(self.user_c).search([("id", "=", announcement.id)])
        self.assertEqual(visible_a, announcement)
        self.assertEqual(visible_b, announcement)
        self.assertFalse(hidden_c)

    def test_notify_updates_same_announcement(self):
        drill = self.env["fire.safety.drill"].with_user(self.officer).create({
            "name": "Notify Drill",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": fields.Datetime.now() + timedelta(days=1),
            "conducted_by": "Safety Team",
            "participant_ids": [(6, 0, [self.user_a.id])],
        })
        first_id = drill.sudo().cc_announcement_id.id
        self.assertTrue(drill.sudo().cc_announcement_notified)

        # Same audience as Schedule Drill → already notified
        result = drill.with_user(self.officer).action_notify_participants()
        self.assertEqual(result.get("status"), "already_notified")
        self.assertEqual(drill.sudo().cc_announcement_id.id, first_id)

        # Audience change → update same announcement and notify again
        drill.with_user(self.officer).write({
            "participant_ids": [(6, 0, [self.user_a.id, self.user_b.id])],
        })
        self.assertFalse(drill.sudo().cc_announcement_notified)
        result = drill.with_user(self.officer).action_notify_participants()
        self.assertEqual(result.get("status"), "notified")
        self.assertEqual(drill.sudo().cc_announcement_id.id, first_id)
        self.assertTrue(drill.sudo().cc_announcement_notified)
        self.assertEqual(
            set(drill.sudo().cc_announcement_id.audience_user_ids.ids),
            {self.user_a.id, self.user_b.id},
        )

    def test_notify_without_community_acl(self):
        """Safety Manager without Community officer rights can still notify."""
        manager = new_test_user(
            self.env,
            login="fs_manager_only",
            groups="fire_safety_management.group_fire_safety_manager,base.group_user",
        )
        drill = self.env["fire.safety.drill"].with_user(manager).create({
            "name": "ACL Drill",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": fields.Datetime.now() + timedelta(days=1),
            "conducted_by": "Safety Team",
            "participant_ids": [(6, 0, [self.user_a.id])],
        })
        self.assertTrue(drill.sudo().cc_announcement_id)
        result = drill.with_user(manager).action_notify_participants()
        self.assertEqual(result.get("status"), "already_notified")
        # Second notify still no AccessError
        result = drill.with_user(manager).action_notify_participants()
        self.assertEqual(result.get("status"), "already_notified")


    def test_create_without_participants_skips_announcement(self):
        drill = self.env["fire.safety.drill"].with_user(self.officer).create({
            "name": "Silent Drill",
            "drill_type": "fire_evacuation",
            "scheduled_datetime": fields.Datetime.now() + timedelta(days=1),
            "conducted_by": "Safety Team",
        })
        self.assertFalse(drill.cc_announcement_id)
