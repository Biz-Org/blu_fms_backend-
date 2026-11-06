# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .dm_mixin import AUDIT_EVENT_TYPES


class DocumentManagementAuditEvent(models.Model):
    _name = 'document.management.audit.event'
    _description = 'Document Audit Event'
    _inherit = ['document.management.mixin']
    _order = 'timestamp desc, id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'document.management.document',
        ondelete='set null',
        index=True,
    )
    document_name = fields.Char()
    user_id = fields.Many2one('res.users', index=True, ondelete='set null')
    event_type = fields.Selection(AUDIT_EVENT_TYPES, required=True, index=True)
    timestamp = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    version_name = fields.Char()
    metadata = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    def write(self, vals):
        if not self.env.su:
            raise UserError('Audit events cannot be modified.')
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError('Audit events cannot be deleted.')
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('document_name') and vals.get('document_id'):
                document = self.env['document.management.document'].browse(vals['document_id'])
                vals['document_name'] = document.name
            if not vals.get('company_id') and vals.get('document_id'):
                document = self.env['document.management.document'].browse(vals['document_id'])
                vals['company_id'] = document.company_id.id or self.env.company.id
        return super().create(vals_list)
