# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    cc_resident_ids = fields.One2many(
        "community.communication.resident",
        "user_id",
        string="Community Resident Profiles",
    )
    cc_community_ids = fields.Many2many(
        "community.communication.community",
        compute="_compute_cc_scope",
        string="Communities",
    )
    cc_building_ids = fields.Many2many(
        "community.communication.building",
        compute="_compute_cc_scope",
        string="Resident Buildings",
    )
    cc_member_group_ids = fields.Many2many(
        "community.communication.group",
        compute="_compute_cc_scope",
        string="Resident Groups",
    )

    @api.depends("cc_resident_ids.community_id", "cc_resident_ids.building_id", "cc_resident_ids.unit_id")
    def _compute_cc_scope(self):
        Member = self.env["community.communication.group.member"]
        for user in self:
            residents = user.cc_resident_ids
            user.cc_community_ids = residents.community_id
            user.cc_building_ids = residents.mapped("building_id")
            user.cc_member_group_ids = Member.search([
                ("resident_id", "in", residents.ids),
                ("state", "=", "member"),
            ]).group_id

    def _cc_is_community_officer(self):
        self.ensure_one()
        return self.has_group("community_communication.group_community_officer")

    def _cc_is_community_webclient_resident(self):
        """Portal community resident: same OWL app, not an Internal User."""
        self.ensure_one()
        return (
            self.has_group("community_communication.group_community_resident")
            and not self.has_group("base.group_user")
        )

    def _cc_webclient_company_session(self):
        """Company payload the OWL webclient expects for non-internal residents."""
        self.ensure_one()
        company = self.company_id.sudo()
        return {
            "user_companies": {
                "current_company": company.id,
                "allowed_companies": {
                    company.id: {
                        "id": company.id,
                        "name": company.name,
                        "sequence": company.sequence,
                        "child_ids": [],
                        "parent_id": company.parent_id.id,
                        "currency_id": company.currency_id.id,
                    }
                },
                "disallowed_ancestor_companies": {},
            },
            "show_effect": True,
        }
