# -*- coding: utf-8 -*-
from odoo import fields, models

from .dm_mixin import APPROVAL_STEP_STATES


class DocumentManagementApprovalStep(models.Model):
    _name = 'document.management.approval.step'
    _description = 'Document Approval Step'
    _inherit = ['document.management.mixin']
    _order = 'sequence, id'
    _check_company_auto = True

    request_id = fields.Many2one(
        'document.management.approval.request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(required=True, default=10)
    name = fields.Char(required=True)
    approver_id = fields.Many2one(
        'res.users',
        required=True,
        index=True,
        ondelete='restrict',
    )
    state = fields.Selection(
        APPROVAL_STEP_STATES,
        required=True,
        default='waiting',
        index=True,
    )
    comment = fields.Text()
    decided_at = fields.Datetime()
    decided_by = fields.Many2one('res.users', ondelete='set null')
    company_id = fields.Many2one(
        related='request_id.company_id',
        store=True,
        index=True,
    )
