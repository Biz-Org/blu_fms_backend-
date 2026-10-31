# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DocumentManagementComment(models.Model):
    _name = 'document.management.comment'
    _description = 'Document Comment'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'document.management.document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
    )
    body = fields.Text(required=True)
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        from ..services.access_service import DocumentAccessService
        access = DocumentAccessService(self.env)
        for vals in vals_list:
            if not (vals.get('body') or '').strip():
                raise ValidationError('Comment body is required.')
            if vals.get('document_id') and not self.env.su:
                document = self.env['document.management.document'].browse(vals['document_id'])
                access.require(document, 'read')
                vals['user_id'] = self.env.user.id
        return super().create(vals_list)
