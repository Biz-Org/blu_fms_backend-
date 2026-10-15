# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import NOTIFICATION_TYPES


class MobileApplicationNotification(models.Model):
    _name = "mobile.application.notification"
    _description = "Mobile Application Notification"
    _order = "create_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    title = fields.Char(required=True)
    message = fields.Text()
    notification_type = fields.Selection(NOTIFICATION_TYPES, default="system", required=True, index=True)
    priority = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High")],
        default="normal",
        required=True,
    )
    is_read = fields.Boolean(default=False, index=True)
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    action_route = fields.Char(help="Mobile shell route for deep linking.")
    create_date = fields.Datetime(readonly=True)

    def action_mark_read(self):
        self.write({"is_read": True})

    @api.model
    def mark_all_read(self, user=None):
        user = user or self.env.user
        pending = self.search([("user_id", "=", user.id), ("is_read", "=", False)])
        pending.write({"is_read": True})
        return len(pending)
