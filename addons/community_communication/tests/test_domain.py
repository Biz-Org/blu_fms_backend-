# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import CommunityCommunicationCase


@tagged("post_install", "-at_install")
class TestAnnouncementWorkflow(CommunityCommunicationCase):
    def test_publish_and_acknowledge(self):
        announcement = self.env["community.communication.announcement"].with_user(self.officer).create({
            "title": "Water outage",
            "body": "<p>Tower B</p>",
            "community_id": self.community.id,
            "category": "maintenance",
        })
        announcement.action_publish()
        self.assertEqual(announcement.state, "published")
        announcement.with_user(self.portal_user).action_acknowledge()
        self.assertEqual(announcement.ack_count, 1)
        announcement.with_user(self.portal_user).action_acknowledge()
        self.assertEqual(announcement.ack_count, 1)

    def test_resident_can_search_read_announcements(self):
        announcement = self.env["community.communication.announcement"].with_user(self.officer).create({
            "title": "Resident readable",
            "body": "<p>Hello</p>",
            "community_id": self.community.id,
            "audience_type": "users",
            "audience_user_ids": [(6, 0, [self.portal_user.id, self.officer.id])],
        })
        announcement.action_publish()
        rows = self.env["community.communication.announcement"].with_user(self.portal_user).search_read(
            [("id", "=", announcement.id)],
            ["title", "author_name", "reach_count", "ack_rate", "audience_type"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Resident readable")
        self.assertTrue(rows[0]["author_name"])
        self.assertEqual(rows[0]["reach_count"], 2)

    def test_invalid_transition(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Draft only",
            "community_id": self.community.id,
        })
        with self.assertRaises(UserError):
            announcement.action_expire()

    def test_schedule_requires_future_date(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Later",
            "body": "<p>Later details</p>",
            "community_id": self.community.id,
            "date_publish": fields.Datetime.now() - timedelta(hours=1),
        })
        with self.assertRaises(UserError):
            announcement.action_schedule()

    def test_cron_publishes_scheduled(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Auto",
            "body": "<p>Auto publish</p>",
            "community_id": self.community.id,
            "date_publish": fields.Datetime.now() + timedelta(days=1),
        })
        announcement.action_schedule()
        announcement.date_publish = fields.Datetime.now() - timedelta(minutes=1)
        self.env["community.communication.announcement"]._cron_publish_and_expire()
        self.assertEqual(announcement.state, "published")

    def test_resident_cannot_see_draft(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Secret",
            "community_id": self.community.id,
        })
        hidden = self.env["community.communication.announcement"].with_user(self.portal_user).search([
            ("id", "=", announcement.id),
        ])
        self.assertFalse(hidden)


@tagged("post_install", "-at_install")
class TestPollAndEvent(CommunityCommunicationCase):
    def test_poll_vote_and_duplicate(self):
        poll = self.env["community.communication.poll"].create({
            "question": "Picnic time?",
            "community_id": self.community.id,
            "option_ids": [
                (0, 0, {"name": "Morning"}),
                (0, 0, {"name": "Afternoon"}),
            ],
        })
        poll.action_open()
        option = poll.option_ids[0]
        poll.with_user(self.portal_user).action_vote(option.ids)
        self.assertEqual(poll.participant_count, 1)
        with self.assertRaises(UserError):
            poll.with_user(self.portal_user).action_vote(option.ids)

    def test_one_vote_per_unit(self):
        housemate = new_test_user(
            self.env,
            login="cc_housemate",
            groups="community_communication.group_community_resident",
        )
        self.env["community.communication.resident"].create({
            "partner_id": housemate.partner_id.id,
            "user_id": housemate.id,
            "community_id": self.community.id,
            "unit_id": self.unit_a.id,
        })
        poll = self.env["community.communication.poll"].create({
            "question": "Gym hours",
            "community_id": self.community.id,
            "one_per_unit": True,
            "option_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
        })
        poll.action_open()
        poll.with_user(self.portal_user).action_vote(poll.option_ids[0].ids)
        with self.assertRaises(UserError):
            poll.with_user(housemate).action_vote(poll.option_ids[1].ids)

    def test_event_waitlist_and_promote(self):
        event = self.env["community.communication.event"].create({
            "name": "Yoga",
            "community_id": self.community.id,
            "date_start": fields.Datetime.now() + timedelta(days=2),
            "date_end": fields.Datetime.now() + timedelta(days=2, hours=1),
            "capacity": 1,
            "require_registration": True,
        })
        event.action_publish()
        first = event.with_user(self.portal_user).action_register()
        self.assertEqual(first.state, "confirmed")
        second = event.with_user(self.portal_user_b).action_register()
        self.assertEqual(second.state, "waitlisted")
        first.action_cancel()
        self.assertEqual(second.state, "confirmed")


@tagged("post_install", "-at_install")
class TestFeedbackGroupSecurity(CommunityCommunicationCase):
    def test_feedback_sequence_and_anonymous(self):
        feedback = self.env["community.communication.feedback"].with_user(self.portal_user).create({
            "subject": "Quiet hours",
            "community_id": self.community.id,
            "anonymous": True,
            "description": "<p>Too loud</p>",
        })
        self.assertTrue(feedback.name.startswith("FB-"))
        self.assertFalse(feedback.resident_id)

    def test_group_join_and_invite_only(self):
        public = self.env["community.communication.group"].create({
            "name": "Gardeners",
            "community_id": self.community.id,
            "visibility": "public",
        })
        public.with_user(self.portal_user).action_join()
        self.assertEqual(public.member_count, 1)
        invite = self.env["community.communication.group"].create({
            "name": "Board",
            "community_id": self.community.id,
            "visibility": "invite",
        })
        with self.assertRaises(UserError):
            invite.with_user(self.portal_user).action_join()
        with self.assertRaises(UserError):
            self.env["community.communication.group.member"].with_user(self.portal_user).create({
                "group_id": invite.id,
                "resident_id": self.resident.id,
                "state": "member",
                "role": "administrator",
            })

    def test_other_community_hidden(self):
        notice = self.env["community.communication.notice"].create({
            "title": "Other site",
            "body": "<p>Hidden</p>",
            "community_id": self.other_community.id,
        })
        notice.action_publish()
        seen = self.env["community.communication.notice"].with_user(self.portal_user).search([
            ("id", "=", notice.id),
        ])
        self.assertFalse(seen)

    def test_officer_can_read_internal_notes(self):
        feedback = self.env["community.communication.feedback"].create({
            "subject": "Pool",
            "community_id": self.community.id,
            "resident_id": self.resident.id,
        })
        note = self.env["community.communication.feedback.note"].create({
            "feedback_id": feedback.id,
            "body": "Assign vendor",
        })
        self.assertTrue(
            self.env["community.communication.feedback.note"].with_user(self.officer).browse(note.id).body
        )
        with self.assertRaises(AccessError):
            self.env["community.communication.feedback.note"].with_user(self.portal_user).browse(note.id).read(["body"])


@tagged("post_install", "-at_install")
class TestSharedRoleAccess(CommunityCommunicationCase):
    def test_resident_cannot_create_announcement_or_event(self):
        Announcement = self.env["community.communication.announcement"].with_user(self.portal_user)
        with self.assertRaises(AccessError):
            Announcement.create({
                "title": "Nope",
                "body": "<p>Nope</p>",
                "community_id": self.community.id,
            })
        Event = self.env["community.communication.event"].with_user(self.portal_user)
        with self.assertRaises(AccessError):
            Event.create({
                "name": "Nope Event",
                "community_id": self.community.id,
                "date_start": fields.Datetime.now() + timedelta(days=1),
                "date_end": fields.Datetime.now() + timedelta(days=1, hours=1),
            })
        event = self.env["community.communication.event"].create({
            "name": "Staff Event",
            "community_id": self.community.id,
            "date_start": fields.Datetime.now() + timedelta(days=1),
            "date_end": fields.Datetime.now() + timedelta(days=1, hours=1),
        })
        with self.assertRaises(AccessError):
            event.with_user(self.portal_user).action_publish()
        announcement = self.env["community.communication.announcement"].create({
            "title": "Staff only publish",
            "body": "<p>Body</p>",
            "community_id": self.community.id,
        })
        with self.assertRaises(AccessError):
            announcement.with_user(self.portal_user).action_publish()

    def test_resident_cannot_create_poll(self):
        with self.assertRaises(AccessError):
            self.env["community.communication.poll"].with_user(self.portal_user).create({
                "question": "Nope?",
                "community_id": self.community.id,
                "option_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
            })
        poll = self.env["community.communication.poll"].create({
            "question": "Staff poll?",
            "community_id": self.community.id,
            "option_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
        })
        poll.action_open()
        poll.with_user(self.portal_user).action_vote(poll.option_ids[0].ids)
        self.assertEqual(poll.participant_count, 1)
        with self.assertRaises(AccessError):
            poll.with_user(self.portal_user).write({"question": "Hacked"})
        with self.assertRaises(AccessError):
            poll.with_user(self.portal_user).action_close()

    def test_audience_buildings_hide_from_other_tower(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Tower A only",
            "body": "<p>A</p>",
            "community_id": self.community.id,
            "audience_type": "buildings",
            "building_ids": [(6, 0, self.building_a.ids)],
        })
        announcement.action_publish()
        seen = self.env["community.communication.announcement"].with_user(self.portal_user).search([
            ("id", "=", announcement.id),
        ])
        hidden = self.env["community.communication.announcement"].with_user(self.portal_user_b).search([
            ("id", "=", announcement.id),
        ])
        self.assertTrue(seen)
        self.assertFalse(hidden)

    def test_audience_community_visible_to_all_residents(self):
        announcement = self.env["community.communication.announcement"].create({
            "title": "Everyone",
            "body": "<p>Hi</p>",
            "community_id": self.community.id,
            "audience_type": "community",
        })
        announcement.action_publish()
        self.assertTrue(self.env["community.communication.announcement"].with_user(self.portal_user).search([("id", "=", announcement.id)]))
        self.assertTrue(self.env["community.communication.announcement"].with_user(self.portal_user_b).search([("id", "=", announcement.id)]))

    def test_registration_visible_to_admin_on_same_event(self):
        event = self.env["community.communication.event"].create({
            "name": "Annual Community Sports Day",
            "community_id": self.community.id,
            "date_start": fields.Datetime.now() + timedelta(days=3),
            "date_end": fields.Datetime.now() + timedelta(days=3, hours=2),
            "require_registration": True,
        })
        event.action_publish()
        registration = event.with_user(self.portal_user).action_register()
        self.assertEqual(registration.event_id, event)
        self.assertEqual(registration.resident_id, self.resident)
        seen = event.with_user(self.officer).registration_ids.filtered(lambda r: r.state != "cancelled")
        self.assertIn(registration, seen)
        mine = event.with_user(self.portal_user).get_my_registration()
        self.assertEqual(mine.get("id"), registration.id)
        event.with_user(self.portal_user).action_unregister()
        self.assertEqual(registration.state, "cancelled")

    def test_resident_cannot_write_or_staff_registration_actions(self):
        event = self.env["community.communication.event"].create({
            "name": "Staff Managed Event",
            "community_id": self.community.id,
            "date_start": fields.Datetime.now() + timedelta(days=4),
            "date_end": fields.Datetime.now() + timedelta(days=4, hours=2),
            "require_registration": True,
        })
        event.action_publish()
        registration = event.with_user(self.portal_user).action_register()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).write({"state": "attended"})
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_confirm()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_attended()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_reject()
        other = event.with_user(self.portal_user_b).action_register()
        with self.assertRaises(AccessError):
            other.with_user(self.portal_user).write({"state": "cancelled"})
        registration.with_user(self.officer).action_waitlist()
        registration.with_user(self.officer).action_confirm()
        self.assertEqual(registration.state, "confirmed")
        registration.with_user(self.officer).action_attended()
        self.assertEqual(registration.state, "attended")
        other.with_user(self.officer).action_waitlist()
        other.with_user(self.officer).action_reject()
        self.assertEqual(other.state, "rejected")

    def test_resident_cannot_create_notice_or_group(self):
        with self.assertRaises(AccessError):
            self.env["community.communication.notice"].with_user(self.portal_user).create({
                "title": "Nope",
                "body": "<p>Nope</p>",
                "community_id": self.community.id,
            })
        with self.assertRaises(AccessError):
            self.env["community.communication.group"].with_user(self.portal_user).create({
                "name": "Rogue Group",
                "community_id": self.community.id,
            })

    def test_resident_cannot_process_feedback(self):
        feedback = self.env["community.communication.feedback"].with_user(self.portal_user).create({
            "subject": "Gate issue",
            "description": "<p>Stuck</p>",
            "community_id": self.community.id,
        })
        with self.assertRaises(AccessError):
            feedback.with_user(self.portal_user).action_resolve()
        with self.assertRaises(AccessError):
            feedback.with_user(self.portal_user).write({"state": "resolved"})
        feedback.with_user(self.officer).action_in_progress()
        self.assertEqual(feedback.state, "in_progress")
        feedback.with_user(self.officer).action_resolve()
        self.assertEqual(feedback.state, "resolved")

    def test_resident_can_discuss_but_not_moderate(self):
        discussion = self.env["community.communication.discussion"].with_user(self.portal_user).create({
            "title": "Lobby plants",
            "body": "<p>Can we add some?</p>",
            "community_id": self.community.id,
            "is_pinned": True,
        })
        self.assertFalse(discussion.is_pinned)
        self.assertEqual(discussion.state, "active")
        comment_id = discussion.with_user(self.portal_user).action_post_comment("<p>I can help water them.</p>")
        self.assertTrue(comment_id)
        with self.assertRaises(AccessError):
            discussion.with_user(self.portal_user).action_pin()
        with self.assertRaises(AccessError):
            discussion.with_user(self.portal_user).action_lock()

    def test_resident_cannot_access_analytics(self):
        with self.assertRaises(AccessError):
            self.env["community.communication.dashboard"].with_user(self.portal_user).get_analytics_data(30, False)

    def test_resident_uses_shared_community_menu(self):
        self.assertTrue(self.portal_user.share)
        self.assertTrue(self.portal_user.has_group("base.group_portal"))
        self.assertFalse(self.portal_user.has_group("base.group_user"))
        self.assertTrue(self.portal_user.has_group("community_communication.group_community_resident"))
        self.assertFalse(self.portal_user.has_group("community_communication.group_community_officer"))
        root = self.env.ref("community_communication.menu_community_communication_root")
        visible = self.env["ir.ui.menu"].with_user(self.portal_user)._visible_menu_ids()
        self.assertIn(root.id, visible)
        mail_root = self.env.ref("mail.menu_root", raise_if_not_found=False)
        if mail_root:
            self.assertNotIn(mail_root.id, visible)
        self.assertFalse(self.officer.share)
        self.assertTrue(self.officer.has_group("base.group_user"))
