# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase, JsonRpcException, new_test_user

from .common import CommunityCommunicationCase


@tagged("post_install", "-at_install")
class TestCommunityUiLayer(CommunityCommunicationCase):
    def test_dashboard_kpis(self):
        self.env["community.communication.announcement"].create({
            "title": "KPI",
            "body": "<p>Published</p>",
            "community_id": self.community.id,
        }).action_publish()
        data = self.env["community.communication.dashboard"].get_dashboard_data()
        self.assertGreaterEqual(data["kpis"]["announcements"], 1)
        self.assertIn("upcoming_events", data)
        cards = self.env["community.communication.dashboard"].get_list_kpis(
            "community.communication.announcement"
        )
        self.assertTrue(any(card["key"] == "published" for card in cards))

    def test_analytics_payload(self):
        data = self.env["community.communication.dashboard"].get_analytics_data(30, False)
        self.assertIn("trend", data)
        self.assertIn("announcements", data)
        self.assertIn("insights", data)

    def test_mail_templates_exist(self):
        self.env.ref("community_communication.mail_template_announcement_published")
        self.env.ref("community_communication.mail_template_poll_opened")
        self.env.ref("community_communication.mail_template_event_confirm")
        self.env.ref("community_communication.mail_template_event_reminder")

    def test_group_list_kpis(self):
        cards = self.env["community.communication.dashboard"].get_list_kpis(
            "community.communication.group"
        )
        self.assertTrue(any(card["key"] == "members" for card in cards))

    def test_analytics_action(self):
        action = self.env.ref("community_communication.action_community_analytics")
        self.assertEqual(action.tag, "community_communication.action_analytics")

    def test_thread_and_vote_payloads(self):
        discussion = self.env["community.communication.discussion"].create({
            "title": "Hours",
            "community_id": self.community.id,
            "body": "<p>Extend hours</p>",
        })
        discussion.action_post_comment("<p>I agree</p>")
        payload = discussion.get_thread_payload()
        self.assertEqual(len(payload["comments"]), 1)
        poll = self.env["community.communication.poll"].create({
            "question": "Picnic?",
            "community_id": self.community.id,
            "option_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
        })
        poll.action_open()
        vote = poll.with_user(self.portal_user).get_vote_payload()
        self.assertFalse(vote["has_voted"])
        poll.with_user(self.portal_user).action_vote(poll.option_ids[0].ids)
        self.assertTrue(poll.with_user(self.portal_user).get_vote_payload()["has_voted"])
        admin_payload = poll.get_vote_payload()
        self.assertEqual(admin_payload["participant_count"], 1)
        self.assertEqual(admin_payload["options"][0]["vote_count"], 1)
        self.assertGreater(admin_payload["options"][0]["vote_percent"], 0)


@tagged("post_install", "-at_install")
class TestSharedCommunityUi(HttpCase):
    def test_resident_opens_shared_community_app(self):
        community = self.env["community.communication.community"].create({
            "name": "Portal Park",
            "code": "PPK",
        })
        user = new_test_user(
            self.env,
            login="cc_resident_http",
            password="resident",
            groups="community_communication.group_community_resident",
        )
        self.env["community.communication.resident"].create({
            "partner_id": user.partner_id.id,
            "user_id": user.id,
            "community_id": community.id,
        })
        self.assertTrue(user.share)
        self.assertFalse(user.has_group("base.group_user"))
        self.assertTrue(user.has_group("base.group_portal"))
        root = self.env.ref("community_communication.menu_community_communication_root")
        analytics = self.env.ref("community_communication.menu_cc_analytics")
        visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
        self.assertIn(root.id, visible)
        self.assertNotIn(analytics.id, visible)
        self.authenticate("cc_resident_http", "resident")
        response = self.url_open("/odoo")
        self.assertEqual(response.status_code, 200)
        body = response.content or b""
        self.assertIn(b"o_web_client", body)
        self.assertNotIn(b"o_cc_portal_nav", body)
        my_home = self.url_open("/my", allow_redirects=False)
        self.assertIn(my_home.status_code, (301, 302, 303, 307, 308))
        self.assertIn("/odoo", my_home.headers.get("Location", ""))
        dashboard = self.env.ref("community_communication.action_community_dashboard")
        loaded = self.make_jsonrpc_request("/web/action/load", {"action_id": dashboard.id})
        self.assertEqual(loaded.get("tag"), "community_communication.action_dashboard")
        analytics = self.env.ref("community_communication.action_community_analytics")
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/web/action/load", {"action_id": analytics.id})


@tagged("post_install", "-at_install")
class TestMustFixUiGaps(CommunityCommunicationCase):
    def test_expiring_soon_kpi_excludes_past_and_far_future(self):
        now = fields.Datetime.now()
        Announcement = self.env["community.communication.announcement"]
        soon = Announcement.create({
            "title": "Expires in two days",
            "body": "<p>Soon</p>",
            "community_id": self.community.id,
            "date_expiry": now + timedelta(days=2),
        })
        soon.action_publish()
        later = Announcement.create({
            "title": "Expires in ten days",
            "body": "<p>Later</p>",
            "community_id": self.community.id,
            "date_expiry": now + timedelta(days=10),
        })
        later.action_publish()
        already_expired = Announcement.create({
            "title": "Expiry already passed",
            "body": "<p>Past</p>",
            "community_id": self.community.id,
            "date_publish": now - timedelta(days=3),
            "date_expiry": now - timedelta(hours=1),
        })
        already_expired.action_publish()
        expired_state = Announcement.create({
            "title": "Expired status",
            "body": "<p>Expired</p>",
            "community_id": self.community.id,
            "date_expiry": now + timedelta(days=1),
        })
        expired_state.action_publish()
        expired_state.action_expire()

        domain = self.env["community.communication.dashboard"].announcement_expiring_soon_domain()
        found = Announcement.search(domain)
        self.assertIn(soon, found)
        self.assertNotIn(later, found)
        self.assertNotIn(already_expired, found)
        self.assertNotIn(expired_state, found)

        cards = self.env["community.communication.dashboard"].get_list_kpis(
            "community.communication.announcement"
        )
        expiring = next(card for card in cards if card["filter"] == "expiring_soon")
        self.assertEqual(expiring["value"], Announcement.search_count(domain))

    def test_reported_tab_uses_pending_reports(self):
        reported = self.env["community.communication.discussion"].create({
            "title": "Reported thread",
            "body": "<p>Please review</p>",
            "community_id": self.community.id,
        })
        clean = self.env["community.communication.discussion"].create({
            "title": "Clean thread",
            "body": "<p>All good</p>",
            "community_id": self.community.id,
        })
        dismissed = self.env["community.communication.discussion"].create({
            "title": "Dismissed report thread",
            "body": "<p>Old report</p>",
            "community_id": self.community.id,
        })
        reported.with_user(self.portal_user).action_report("Spam")
        report_id = dismissed.with_user(self.portal_user).action_report("Off-topic")
        self.env["community.communication.report"].browse(report_id).sudo().write({"state": "dismissed"})

        reports = self.env["community.communication.report"].search([
            ("state", "=", "pending"),
            ("res_model", "=", "community.communication.discussion"),
        ])
        found = self.env["community.communication.discussion"].search([
            ("id", "in", reports.mapped("res_id") or [0]),
            ("state", "!=", "removed"),
        ])
        self.assertIn(reported, found)
        self.assertNotIn(clean, found)
        self.assertNotIn(dismissed, found)

    def test_event_search_and_category_domain(self):
        yoga = self.env["community.communication.event"].create({
            "name": "Morning Yoga",
            "community_id": self.community.id,
            "category": "activities",
            "date_start": fields.Datetime.now() + timedelta(days=2),
            "date_end": fields.Datetime.now() + timedelta(days=2, hours=1),
        })
        meeting = self.env["community.communication.event"].create({
            "name": "HOA Meeting",
            "community_id": self.community.id,
            "category": "meetings",
            "date_start": fields.Datetime.now() + timedelta(days=3),
            "date_end": fields.Datetime.now() + timedelta(days=3, hours=1),
        })
        by_name = self.env["community.communication.event"].search([("name", "ilike", "Yoga")])
        self.assertIn(yoga, by_name)
        self.assertNotIn(meeting, by_name)
        by_both = self.env["community.communication.event"].search([
            ("name", "ilike", "Morning"),
            ("category", "=", "activities"),
        ])
        self.assertIn(yoga, by_both)
        self.assertNotIn(meeting, by_both)
        cleared = self.env["community.communication.event"].search([
            ("id", "in", [yoga.id, meeting.id]),
        ])
        self.assertEqual(set(cleared.ids), {yoga.id, meeting.id})

    def test_group_search_with_category_and_visibility(self):
        garden = self.env["community.communication.group"].create({
            "name": "Garden Club",
            "community_id": self.community.id,
            "category": "hobby",
            "visibility": "public",
        })
        private = self.env["community.communication.group"].create({
            "name": "Garden Committee",
            "community_id": self.community.id,
            "category": "other",
            "visibility": "invite",
        })
        by_name = self.env["community.communication.group"].search([
            ("name", "ilike", "Garden"),
            ("state", "=", "active"),
        ])
        self.assertIn(garden, by_name)
        self.assertIn(private, by_name)
        by_category = self.env["community.communication.group"].search([
            ("name", "ilike", "Garden"),
            ("state", "=", "active"),
            ("category", "=", "hobby"),
        ])
        self.assertIn(garden, by_category)
        self.assertNotIn(private, by_category)
        by_visibility = self.env["community.communication.group"].search([
            ("name", "ilike", "Garden"),
            ("state", "=", "active"),
            ("visibility", "=", "invite"),
        ])
        self.assertIn(private, by_visibility)
        self.assertNotIn(garden, by_visibility)
