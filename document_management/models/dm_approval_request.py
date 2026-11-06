# -*- coding: utf-8 -*-
from odoo import fields, models

from .dm_mixin import APPROVAL_REQUEST_STATES


class DocumentManagementApprovalRequest(models.Model):
    _name = 'document.management.approval.request'
    _description = 'Document Approval Request'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'document.management.document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    version_id = fields.Many2one(
        'document.management.version',
        ondelete='restrict',
        index=True,
    )
    requester_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
    )
    state = fields.Selection(
        APPROVAL_REQUEST_STATES,
        required=True,
        default='pending',
        index=True,
    )
    submitted_at = fields.Datetime(default=fields.Datetime.now, index=True)
    decided_at = fields.Datetime()
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )
    step_ids = fields.One2many('document.management.approval.step', 'request_id')
