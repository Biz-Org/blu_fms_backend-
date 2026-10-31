# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentManagementDocumentType(models.Model):
    _name = 'document.management.document.type'
    _description = 'Document Type'
    _inherit = ['document.management.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    requires_approval = fields.Boolean(default=True)
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
            'Document type name must be unique per company.',
        ),
    ]
