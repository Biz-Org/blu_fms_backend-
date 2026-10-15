# -*- coding: utf-8 -*-

from odoo import fields, models


class FireSafetyContact(models.Model):
    _name = "fire.safety.contact"
    _description = "Fire & Safety Emergency Contact"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True)
    role = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    property_id = fields.Many2one(
        "fire.safety.property",
        ondelete="set null",
        help="INTEGRATION PLACEHOLDER: retarget to FMS Property Management.",
    )
    notes = fields.Text()
    active = fields.Boolean(default=True)
