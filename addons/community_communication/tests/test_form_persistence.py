# -*- coding: utf-8 -*-

import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CommunityCommunicationCase


@tagged("post_install", "-at_install")
class TestFormPersistence(CommunityCommunicationCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env["community.communication.group"].create({
            "name": "Garden Club",
            "community_id": cls.community.id,
            "visibility": "public",
        })

    def _pdf_attachment(self, name="plan.pdf"):
        return self.env["ir.attachment"].create({
            "name": name,
            "datas": base64.b64encode(b"%PDF-1.4 test-bytes"),
            "mimetype": "application/pdf",
        })

    def test_announcement_entire_community_roundtrip(self):
        rec = self.env["community.communication.announcement"].create({
            "title": "All residents",
            "body": "<p>Hello everyone</p>",
            "community_id": self.community.id,
            "audience_type": "community",
        })
        rec.invalidate_recordset()
        self.assertEqual(rec.audience_type, "community")
        self.assertFalse(rec.building_ids)
        self.assertFalse(rec.audience_group_ids)

    def test_announcement_buildings_roundtrip_and_switch(self):
        rec = self.env["community.communication.announcement"].create({
            "title": "Towers",
            "body": "<p>Tower notice</p>",
            "community_id": self.community.id,
            "audience_type": "buildings",
            "building_ids": [(6, 0, [self.building_a.id, self.building_b.id])],
        })
        rec.invalidate_recordset()
        self.assertEqual(set(rec.building_ids.ids), {self.building_a.id, self.building_b.id})
        rec.write({
            "audience_type": "community",
            "building_ids": [(6, 0, [])],
            "audience_group_ids": [(6, 0, [])],
        })
        rec.invalidate_recordset()
        self.assertEqual(rec.audience_type, "community")
        self.assertFalse(rec.building_ids)

    def test_announcement_groups_roundtrip(self):
        rec = self.env["community.communication.announcement"].create({
            "title": "Club only",
            "body": "<p>Members</p>",
            "community_id": self.community.id,
            "audience_type": "groups",
            "audience_group_ids": [(6, 0, [self.group.id])],
        })
        rec.invalidate_recordset()
        self.assertEqual(rec.audience_group_ids, self.group)
        rec.write({
            "audience_type": "buildings",
            "building_ids": [(6, 0, [self.building_a.id])],
            "audience_group_ids": [(6, 0, [])],
        })
        rec.invalidate_recordset()
        self.assertEqual(rec.audience_type, "buildings")
        self.assertEqual(rec.building_ids, self.building_a)
        self.assertFalse(rec.audience_group_ids)

    def test_announcement_attachment_persist_and_download(self):
        attachment = self._pdf_attachment()
        rec = self.env["community.communication.announcement"].create({
            "title": "With file",
            "body": "<p>See attachment</p>",
            "community_id": self.community.id,
        })
        rec.action_set_attachments([attachment.id])
        rec.invalidate_recordset()
        self.assertIn(attachment, rec.attachment_ids)
        self.assertEqual(attachment.res_model, rec._name)
        self.assertEqual(attachment.res_id, rec.id)
        rec.action_set_attachments([])
        rec.invalidate_recordset()
        self.assertFalse(rec.attachment_ids)

    def test_buildings_audience_requires_selection(self):
        with self.assertRaises(ValidationError):
            self.env["community.communication.announcement"].create({
                "title": "Missing buildings",
                "body": "<p>Oops</p>",
                "community_id": self.community.id,
                "audience_type": "buildings",
            })

    def test_publish_requires_content(self):
        rec = self.env["community.communication.announcement"].create({
            "title": "Empty body",
            "community_id": self.community.id,
        })
        with self.assertRaises(UserError):
            rec.action_publish()

    def test_poll_audience_persists(self):
        poll = self.env["community.communication.poll"].create({
            "question": "Gym hours?",
            "community_id": self.community.id,
            "audience_type": "buildings",
            "building_ids": [(6, 0, [self.building_a.id])],
            "option_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
        })
        poll.invalidate_recordset()
        self.assertEqual(poll.building_ids, self.building_a)

    def test_notice_audience_and_attachment(self):
        attachment = self._pdf_attachment("rules.pdf")
        notice = self.env["community.communication.notice"].create({
            "title": "Rules",
            "body": "<p>Quiet hours</p>",
            "community_id": self.community.id,
            "audience_type": "groups",
            "audience_group_ids": [(6, 0, [self.group.id])],
        })
        notice.action_set_attachments([attachment.id])
        notice.invalidate_recordset()
        self.assertEqual(notice.audience_group_ids, self.group)
        self.assertIn(attachment, notice.attachment_ids)

    def test_group_officer_adds_member(self):
        group = self.env["community.communication.group"].with_user(self.officer).create({
            "name": "Yoga",
            "community_id": self.community.id,
        })
        member = group.with_user(self.officer).action_add_member(self.resident.id)
        self.assertEqual(member.state, "member")
        self.assertEqual(group.member_count, 1)

    def test_discussion_report_requires_reason(self):
        discussion = self.env["community.communication.discussion"].create({
            "title": "Noise",
            "body": "<p>Too loud</p>",
            "community_id": self.community.id,
        })
        with self.assertRaises(UserError):
            discussion.action_report("  ")
        report_id = discussion.with_user(self.portal_user).action_report("Offensive")
        report = self.env["community.communication.report"].browse(report_id)
        self.assertEqual(report.state, "pending")
        self.assertEqual(report.reporter_id, self.portal_user)

    def test_announcement_pin_persists(self):
        pinned = self.env["community.communication.announcement"].create({
            "title": "Pinned note",
            "body": "<p>Keep this up</p>",
            "community_id": self.community.id,
            "is_pinned": True,
        })
        unpinned = self.env["community.communication.announcement"].create({
            "title": "Regular note",
            "body": "<p>Normal</p>",
            "community_id": self.community.id,
            "is_pinned": False,
        })
        pinned.invalidate_recordset()
        unpinned.invalidate_recordset()
        self.assertTrue(pinned.is_pinned)
        self.assertFalse(unpinned.is_pinned)

    def test_notice_expiry_persists(self):
        expiry = fields.Datetime.now() + timedelta(days=5)
        notice = self.env["community.communication.notice"].create({
            "title": "Pool hours",
            "body": "<p>Updated hours</p>",
            "community_id": self.community.id,
            "date_expiry": expiry,
        })
        notice.invalidate_recordset()
        self.assertEqual(notice.date_expiry, expiry)
        notice.write({"date_expiry": False})
        notice.invalidate_recordset()
        self.assertFalse(notice.date_expiry)
