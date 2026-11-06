# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DocumentManagementFolder(models.Model):
    _name = 'document.management.folder'
    _description = 'Document Folder'
    _inherit = ['document.management.mixin']
    _order = 'name, id'
    _parent_name = 'parent_id'
    _parent_store = True
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    parent_id = fields.Many2one(
        'document.management.folder',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    parent_path = fields.Char(index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    access_rule_ids = fields.One2many('document.management.access.rule', 'folder_id')

    _sql_constraints = [
        (
            'name_parent_company_uniq',
            'unique(company_id, parent_id, name)',
            'Folder name must be unique within the same parent and company.',
        ),
    ]

    @api.constrains('parent_id')
    def _check_parent_cycle(self):
        for rec in self:
            parent = rec.parent_id
            while parent:
                if parent == rec:
                    raise ValidationError('Folder hierarchy cannot be recursive.')
                parent = parent.parent_id
