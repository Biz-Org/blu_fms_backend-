# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import (
    XMLID_GROUP_RESIDENT,
    XMLID_GROUP_SECURITY,
    XMLID_GROUP_STAFF,
)


class MobileApplicationProfile(models.Model):
    _name = "mobile.application.profile"
    _description = "Mobile Application User Profile"
    _rec_name = "user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    building_label = fields.Char()
    unit_label = fields.Char()
    notification_prefs = fields.Json(default=dict)
    push_provider = fields.Char(help="Configured push provider identifier, if any.")
    push_enabled = fields.Boolean(default=False)

    _sql_constraints = [
        (
            "user_uniq",
            "unique(user_id)",
            "Each user can have only one mobile profile.",
        ),
    ]
    @api.model
    def _role_for_user(self, user):
        user = user or self.env.user
        if user.has_group(XMLID_GROUP_SECURITY):
            return "security"
        if user.has_group(XMLID_GROUP_STAFF):
            return "staff"
        if user.has_group(XMLID_GROUP_RESIDENT):
            return "resident"
        return "none"

    @api.model
    def get_or_create_for_user(self, user=None):
        user = user or self.env.user
        profile = self.search([("user_id", "=", user.id)], limit=1)
        if not profile:
            profile = self.create({"user_id": user.id})
        return profile
