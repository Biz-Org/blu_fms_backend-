# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentManagementCategory(models.Model):
    _name = 'document.management.category'
    _description = 'Document Category'
    _inherit = ['document.management.mixin']
    _order = 'sequence, name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    _sql_constraints = [
        (
            'name_company_uniq',
            'unique(company_id, name)',
            'Category name must be unique per company.',
        ),
    ]
