# -*- coding: utf-8 -*-
from odoo import fields, models

from .dm_mixin import NOTIFICATION_KINDS


class DocumentManagementNotification(models.Model):
    _name = 'document.management.notification'
    _description = 'Document Notification'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    user_id = fields.Many2one(
        'res.users',
        required=True,
        index=True,
        ondelete='cascade',
    )
    document_id = fields.Many2one(
        'document.management.document',
        ondelete='cascade',
        index=True,
    )
    kind = fields.Selection(NOTIFICATION_KINDS, required=True, index=True)
    body = fields.Text()
    is_read = fields.Boolean(default=False)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
