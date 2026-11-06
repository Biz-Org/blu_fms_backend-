# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .dm_mixin import VERSION_PROTECTED_FIELDS


class DocumentManagementVersion(models.Model):
    _name = 'document.management.version'
    _description = 'Document Version'
    _inherit = ['document.management.mixin']
    _order = 'major desc, minor desc, id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'document.management.document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(required=True)
    major = fields.Integer(required=True, default=1)
    minor = fields.Integer(required=True, default=0)
    note = fields.Text()
    is_current = fields.Boolean(default=True, index=True)
    author_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        required=True,
        ondelete='restrict',
        index=True,
    )
    file_name = fields.Char()
    file_size = fields.Integer()
    mimetype = fields.Char()
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            'attachment_uniq',
            'unique(attachment_id)',
            'A version can have only one attachment.',
        ),
    ]

    def write(self, vals):
        if not self.env.context.get('dm_lifecycle'):
            raise UserError('Document versions are immutable.')
        self._dm_guard_lifecycle_fields(
            vals,
            VERSION_PROTECTED_FIELDS,
            'Document versions are immutable.',
        )
        return super().write(vals)

    @api.constrains('is_current', 'document_id')
    def _check_one_current(self):
        for rec in self:
            if not rec.document_id:
                continue
            currents = rec.document_id.version_ids.filtered('is_current')
            if len(currents) > 1:
                raise ValidationError('A document must have exactly one current version.')
