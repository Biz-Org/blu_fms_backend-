# -*- coding: utf-8 -*-
from odoo import fields, models


class FacilityType(models.Model):
    _name = "facility.type"
    _description = "Facility Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
