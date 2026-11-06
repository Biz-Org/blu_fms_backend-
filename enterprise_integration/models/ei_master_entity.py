# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EiMasterEntity(models.Model):
    _name = 'ei.master.entity'
    _description = 'Master Data Entity Type'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Selection(
        [
            ('customer', 'Customer'),
            ('supplier', 'Supplier'),
            ('product', 'Product / Item'),
            ('employee', 'Employee'),
            ('account', 'Chart / Account'),
            ('site_location', 'Site / Location'),
            ('department', 'Department'),
        ],
        required=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text()
    external_ref = fields.Char(string='External Reference', index=True)
    mapping_ids = fields.One2many('ei.master.mapping', 'entity_id', string='Mappings')
    mapping_count = fields.Integer(compute='_compute_mapping_count')

    _sql_constraints = [
        ('ei_master_entity_code_uniq', 'unique(code)', 'Master entity code must be unique.'),
    ]

    @api.depends('mapping_ids')
    def _compute_mapping_count(self):
        for rec in self:
            rec.mapping_count = len(rec.mapping_ids)
