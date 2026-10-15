# -*- coding: utf-8 -*-

import secrets

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import XMLID_GROUP_RESIDENT, XMLID_GROUP_SECURITY, XMLID_GROUP_STAFF


class MobileDigitalId(models.Model):
    _name = "mobile.digital.id"
    _description = "Mobile Digital ID"
    _rec_name = "user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    token = fields.Char(required=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    last_verified_at = fields.Datetime(readonly=True)
    verification_count = fields.Integer(default=0, readonly=True)

    _user_uniq = models.Constraint("unique(user_id)", "Each user has one digital ID.")
    _token_uniq = models.Constraint("unique(token)", "Digital ID token must be unique.")

    @api.model
    def _generate_token(self):
        return secrets.token_urlsafe(32)

    @api.model
    def get_or_create_for_user(self, user=None):
        user = user or self.env.user
        record = self.search([("user_id", "=", user.id)], limit=1)
        if not record:
            record = self.create({"user_id": user.id, "token": self._generate_token()})
        elif not record.active:
            record.write({"active": True, "token": self._generate_token()})
        return record

    def _check_view_access(self):
        if self.user_id == self.env.user:
            return
        if self.env.user.has_group(XMLID_GROUP_SECURITY) or self.env.user.has_group(XMLID_GROUP_STAFF):
            return
        raise AccessError(_("You cannot view this digital ID."))

    def get_payload(self):
        self.ensure_one()
        self._check_view_access()
        profile = self.env["mobile.application.profile"].get_or_create_for_user(self.user_id)
        role = self.env["mobile.application.profile"]._role_for_user(self.user_id)
        return {
            "name": self.user_id.name,
            "role": role,
            "email": self.user_id.email,
            "building": profile.building_label or "",
            "unit": profile.unit_label or "",
            "id_number": f"FMS-{self.user_id.id:06d}",
            "active": self.active,
            "token": self.token,
            "avatar_url": f"/web/image/res.users/{self.user_id.id}/avatar_128",
        }

    @api.model
    def verify_token(self, token):
        if not self.env.user.has_group(XMLID_GROUP_SECURITY) and not self.env.user.has_group(XMLID_GROUP_STAFF):
            raise AccessError(_("You are not allowed to verify digital IDs."))
        record = self.search([("token", "=", token), ("active", "=", True)], limit=1)
        if not record:
            raise UserError(_("Invalid or inactive digital ID."))
        record.write({
            "last_verified_at": fields.Datetime.now(),
            "verification_count": record.verification_count + 1,
        })
        payload = record.get_payload()
        payload.pop("token", None)
        payload["verified"] = True
        return payload
