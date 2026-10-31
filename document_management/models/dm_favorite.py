# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class DocumentManagementFavorite(models.Model):
    _name = 'document.management.favorite'
    _description = 'Document Favorite'
    _inherit = ['document.management.mixin']
    _check_company_auto = True

    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='cascade',
    )
    document_id = fields.Many2one(
        'document.management.document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            'user_document_uniq',
            'unique(user_id, document_id)',
            'A document can be favorited only once per user.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not self.env.su:
                vals['user_id'] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(rec.user_id != self.env.user for rec in self):
            raise AccessError('Users can only manage their own favorites.')
        if not self.env.su:
            vals = dict(vals)
            vals['user_id'] = self.env.user.id
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(rec.user_id != self.env.user for rec in self):
            raise AccessError('Users can only manage their own favorites.')
        return super().unlink()
