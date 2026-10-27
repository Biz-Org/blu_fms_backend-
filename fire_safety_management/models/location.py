# -*- coding: utf-8 -*-

from odoo import fields, models


class FireSafetyProperty(models.Model):
    """INTEGRATION PLACEHOLDER for FMS Property Management (#2).

    Do not treat this as a Property Management system. Fields are the
    minimum needed so Fire & Safety transactional records can be scoped
    until module #2 provides the canonical property entity.
    """

    _name = "fire.safety.property"
    _description = "Fire & Safety Property (Integration Placeholder)"
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
    building_ids = fields.One2many("fire.safety.building", "property_id")
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )

    _sql_constraints = [
        (
            "code_company_uniq",
            "unique(code, company_id)",
            "Property code must be unique per company.",
        ),
    ]

class FireSafetyBuilding(models.Model):
    """INTEGRATION PLACEHOLDER for property → building/tower."""

    _name = "fire.safety.building"
    _description = "Fire & Safety Building (Integration Placeholder)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    property_id = fields.Many2one(
        "fire.safety.property",
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
    area_ids = fields.One2many("fire.safety.area", "building_id")
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )


class FireSafetyArea(models.Model):
    """INTEGRATION PLACEHOLDER for building → floor/zone/area."""

    _name = "fire.safety.area"
    _description = "Fire & Safety Area (Integration Placeholder)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    building_id = fields.Many2one(
        "fire.safety.building",
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
    area_kind = fields.Selection(
        [
            ("floor", "Floor"),
            ("zone", "Zone"),
            ("area", "Area"),
        ],
        default="area",
        required=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(
        default="INTEGRATION PLACEHOLDER — retarget to FMS Property Management (#2).",
    )
