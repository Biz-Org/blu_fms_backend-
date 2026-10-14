# -*- coding: utf-8 -*-

from odoo import fields, models

from .constants import AREA_KINDS


class IntegrationIotProperty(models.Model):
    """INTEGRATION PLACEHOLDER for FMS Property Management (#2)."""

    _name = "integration.iot.property"
    _description = "IoT Property (Integration Placeholder)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    building_ids = fields.One2many("integration.iot.building", "property_id")
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Property code must be unique per company.",
    )


class IntegrationIotBuilding(models.Model):
    """INTEGRATION PLACEHOLDER for property → building/tower."""

    _name = "integration.iot.building"
    _description = "IoT Building (Integration Placeholder)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    property_id = fields.Many2one(
        "integration.iot.property",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="property_id.company_id",
        store=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    area_ids = fields.One2many("integration.iot.area", "building_id")
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )


class IntegrationIotArea(models.Model):
    """INTEGRATION PLACEHOLDER for building → floor/zone/room/area."""

    _name = "integration.iot.area"
    _description = "IoT Area (Integration Placeholder)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    building_id = fields.Many2one(
        "integration.iot.building",
        required=True,
        ondelete="cascade",
        index=True,
    )
    property_id = fields.Many2one(
        related="building_id.property_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="building_id.company_id",
        store=True,
        index=True,
    )
    area_kind = fields.Selection(AREA_KINDS, default="area", required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )
