# -*- coding: utf-8 -*-

from odoo import fields, models


class CommunityCommunicationCommunity(models.Model):
    """INTEGRATION PLACEHOLDER: future Property FMS community/property model."""

    _name = "community.communication.community"
    _description = "Community (FMS placeholder)"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    building_ids = fields.One2many(
        "community.communication.building",
        "community_id",
        string="Buildings",
    )
    resident_ids = fields.One2many(
        "community.communication.resident",
        "community_id",
        string="Residents",
    )
    venue_ids = fields.One2many(
        "community.communication.venue",
        "community_id",
        string="Venues",
    )

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Community code must be unique per company.",
    )


class CommunityCommunicationBuilding(models.Model):
    """INTEGRATION PLACEHOLDER: future Property FMS building/tower model."""

    _name = "community.communication.building"
    _description = "Building / Tower (FMS placeholder)"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="community_id.company_id",
        store=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    unit_ids = fields.One2many(
        "community.communication.unit",
        "building_id",
        string="Units",
    )


class CommunityCommunicationUnit(models.Model):
    """INTEGRATION PLACEHOLDER: future Property FMS unit/apartment model."""

    _name = "community.communication.unit"
    _description = "Unit (FMS placeholder)"
    _order = "name"

    name = fields.Char(required=True)
    building_id = fields.Many2one(
        "community.communication.building",
        required=True,
        index=True,
        ondelete="restrict",
    )
    community_id = fields.Many2one(
        related="building_id.community_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="building_id.company_id",
        store=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    _unit_building_uniq = models.Constraint(
        "unique(name, building_id)",
        "Unit name must be unique in a building.",
    )


class CommunityCommunicationVenue(models.Model):
    """INTEGRATION PLACEHOLDER: future Facility/asset venue catalog."""

    _name = "community.communication.venue"
    _description = "Venue (FMS placeholder)"
    _order = "name"

    name = fields.Char(required=True)
    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="community_id.company_id",
        store=True,
        index=True,
    )
    address = fields.Char()
    active = fields.Boolean(default=True)
