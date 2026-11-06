# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmsResident(models.Model):
    _name = "fms.resident"
    _description = "FMS Resident"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Contact", ondelete="restrict")
    user_id = fields.Many2one("res.users", string="Portal User", ondelete="set null")
    property_id = fields.Many2one("fms.property", string="Property", ondelete="set null")
    unit = fields.Char(string="Unit / Flat")
    phone = fields.Char()
    email = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        residents = super().create(vals_list)
        residents._fbm_sync_user_property_link()
        return residents

    def write(self, vals):
        users_before = self.mapped("user_id")
        res = super().write(vals)
        if {"property_id", "user_id", "partner_id"} & set(vals):
            self._fbm_sync_user_property_link()
            (users_before | self.mapped("user_id"))._compute_fbm_resident_property_id()
        return res

    def _fbm_sync_user_property_link(self):
        for resident in self:
            if resident.user_id:
                resident.user_id._compute_fbm_resident_property_id()

    @api.model
    def get_resident_for_current_user(self):
        """Return the resident linked to the current user, if any."""
        resident = self.search([("user_id", "=", self.env.uid)], limit=1)
        if resident:
            return resident
        return self.search([("partner_id", "=", self.env.user.partner_id.id)], limit=1)


class ResUsers(models.Model):
    _inherit = "res.users"

    fbm_resident_property_id = fields.Many2one(
        "fms.property",
        compute="_compute_fbm_resident_property_id",
        store=True,
        string="Resident Property",
    )

    @api.depends("partner_id")
    def _compute_fbm_resident_property_id(self):
        Resident = self.env["fms.resident"]
        for user in self:
            resident = Resident.search([("user_id", "=", user.id)], limit=1)
            if not resident and user.partner_id:
                resident = Resident.search([("partner_id", "=", user.partner_id.id)], limit=1)
            user.fbm_resident_property_id = resident.property_id if resident else False
