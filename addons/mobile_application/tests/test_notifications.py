# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import MobileApplicationCase


@tagged("post_install", "-at_install")
class TestMobileNotifications(MobileApplicationCase):
    def test_notification_read(self):
        note = self.env["mobile.application.notification"].create({
            "user_id": self.resident.id,
            "title": "Test",
            "message": "Hello",
        })
        data = self.api.with_user(self.resident).get_notifications()
        self.assertEqual(data["unread"], 1)
        self.api.with_user(self.resident).mark_notification_read(note.id)
        data = self.api.with_user(self.resident).get_notifications()
        self.assertEqual(data["unread"], 0)
