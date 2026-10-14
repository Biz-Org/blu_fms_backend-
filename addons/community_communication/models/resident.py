# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CommunityCommunicationResident(models.Model):
    """Member profile. Authentication remains res.users / res.partner."""

    _name = "community.communication.resident"
    _description = "Community Resident Profile"
    _order = "name"
    _rec_name = "name"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="restrict",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        ondelete="set null",
        index=True,
    )
    name = fields.Char(related="partner_id.name", store=True)
    email = fields.Char(related="partner_id.email")
    phone = fields.Char(related="partner_id.phone")
    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        index=True,
        ondelete="restrict",
    )
    unit_id = fields.Many2one(
        "community.communication.unit",
        domain="[('community_id', '=', community_id)]",
        ondelete="restrict",
    )
    building_id = fields.Many2one(
        related="unit_id.building_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="community_id.company_id",
        store=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    _user_community_uniq = models.Constraint(
        "unique(user_id, community_id)",
        "A user can have only one resident profile per community.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        home = self.env.ref("community_communication.action_community_dashboard", raise_if_not_found=False)
        for record in records:
            user = record.user_id
            if user and home and not user._cc_is_community_officer() and not user.action_id:
                user.sudo().write({"action_id": home.id})
        return records

    @api.model
    def _cc_sync_shared_access(self):
        from odoo.addons.community_communication.hooks import post_init_hook
        post_init_hook(self.env)

    @api.onchange("unit_id")
    def _onchange_unit_id(self):
        if self.unit_id:
            self.community_id = self.unit_id.community_id
