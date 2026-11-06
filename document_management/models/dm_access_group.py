# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentManagementAccessGroup(models.Model):
    _name = 'document.management.access.group'
    _description = 'Document Access Group'
    _inherit = ['document.management.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    member_ids = fields.Many2many(
        'res.users',
        'document_management_access_group_user_rel',
        'group_id',
        'user_id',
    )
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
            'Access group name must be unique per company.',
        ),
    ]
