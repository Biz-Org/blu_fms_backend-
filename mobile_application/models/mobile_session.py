# -*- coding: utf-8 -*-

from odoo import fields, models


class MobileApplicationSession(models.Model):
    _name = "mobile.application.session"
    _description = "Mobile Application Sync Session"
    _order = "last_sync_at desc, id desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    last_sync_at = fields.Datetime()
    device_label = fields.Char()
    unread_count = fields.Integer(default=0)
    capabilities_snapshot = fields.Json()
