# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.common import DECISION_CTX, REQUEST_CTX, guard_state, set_state


class ProcurementApprovalMatrix(models.Model):
    _name = 'procurement.management.approval.matrix'
    _description = 'Procurement Approval Matrix'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    min_value = fields.Monetary(currency_field='currency_id', default=0.0)
    max_value = fields.Monetary(
        currency_field='currency_id',
        help='Zero means no upper limit.',
    )
    department = fields.Char(index=True)
    property_location = fields.Char(index=True)
    category = fields.Char(index=True)
    sequence = fields.Integer(default=10, index=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('review', 'Review'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        required=True,
        default='draft',
        index=True,
    )
    level_ids = fields.One2many('procurement.management.approval.level', 'matrix_id')

    @api.constrains('min_value', 'max_value')
    def _check_band(self):
        for matrix in self:
            if matrix.min_value < 0:
                raise ValidationError('The minimum value cannot be negative.')
            if matrix.max_value and matrix.max_value < matrix.min_value:
                raise ValidationError('The maximum value cannot be below the minimum.')

    def write(self, vals):
        guard_state(self, vals)
        return super().write(vals)

    def unlink(self):
        for matrix in self:
            if matrix.state != 'draft':
                raise UserError('Only a draft matrix can be deleted.')
            if self.env['procurement.management.approval.request'].search_count([
                ('matrix_id', '=', matrix.id),
            ]):
                raise UserError('A matrix that has been used cannot be deleted.')
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def action_submit_review(self):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).submit_matrix_review(self)

    def action_activate(self):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).activate_matrix(self)

    def action_deactivate(self):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).deactivate_matrix(self)


class ProcurementApprovalLevel(models.Model):
    _name = 'procurement.management.approval.level'
    _description = 'Procurement Approval Level'
    _order = 'sequence, id'

    matrix_id = fields.Many2one(
        'procurement.management.approval.matrix', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='matrix_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    approver_group_id = fields.Many2one('res.groups', required=True)
    required_signoff = fields.Boolean(default=True)
    mode = fields.Selection(
        [('sequential', 'Sequential'), ('parallel', 'Parallel')],
        required=True,
        default='sequential',
    )
    escalation_hours = fields.Float(default=48.0)
    escalation_group_id = fields.Many2one('res.groups')

    @api.constrains('mode', 'matrix_id', 'escalation_hours')
    def _check_level(self):
        for level in self:
            if level.escalation_hours < 0:
                raise ValidationError('Escalation hours cannot be negative.')
            modes = set(level.matrix_id.level_ids.mapped('mode'))
            if len(modes) > 1:
                raise ValidationError('Every level in a matrix must use the same approval mode.')


class ProcurementApprovalRequest(models.Model):
    _name = 'procurement.management.approval.request'
    _description = 'Procurement Approval Request'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, default='Approval')
    company_id = fields.Many2one('res.company', required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    purpose = fields.Selection(
        [
            ('requisition', 'Requisition'),
            ('purchase_order', 'Purchase Order'),
            ('supplier_selection', 'Supplier Selection'),
        ],
        required=True,
    )
    amount = fields.Float()
    matrix_id = fields.Many2one('procurement.management.approval.matrix', required=True)
    current_level_id = fields.Many2one('procurement.management.approval.level')
    requester_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('returned', 'Returned'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='pending',
        index=True,
    )
    decision_ids = fields.One2many(
        'procurement.management.approval.decision', 'request_id',
    )

    @api.constrains('res_model', 'res_id', 'state')
    def _check_single_open_request(self):
        for request in self.filtered(lambda item: item.state == 'pending'):
            duplicate = self.search_count([
                ('id', '!=', request.id),
                ('res_model', '=', request.res_model),
                ('res_id', '=', request.res_id),
                ('purpose', '=', request.purpose),
                ('state', '=', 'pending'),
            ])
            if duplicate:
                raise ValidationError('This document already has an open approval request.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self.check_access('create')
        if not self.env.context.get(REQUEST_CTX):
            raise UserError('Approval requests are created by the procurement workflow.')
        return super().create(vals_list)

    def write(self, vals):
        guard_state(self, vals)
        if not self.env.context.get(REQUEST_CTX):
            raise UserError('Approval requests are updated by the procurement workflow.')
        return super().write(vals)

    def unlink(self):
        raise UserError('Approval requests cannot be deleted.')

    def _set_state(self, state):
        self.sudo().with_context(**{REQUEST_CTX: True, 'pm_state_write': True}).write({'state': state})

    def action_approve(self, comment=''):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).decide(self, 'approved', comment)

    def action_reject(self, comment=''):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).decide(self, 'rejected', comment)

    def action_return(self, comment=''):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).decide(self, 'returned', comment)


class ProcurementApprovalDecision(models.Model):
    _name = 'procurement.management.approval.decision'
    _description = 'Procurement Approval Decision'
    _order = 'id'

    request_id = fields.Many2one(
        'procurement.management.approval.request', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    level_id = fields.Many2one('procurement.management.approval.level', required=True)
    group_id = fields.Many2one('res.groups', required=True)
    user_id = fields.Many2one('res.users')
    decision = fields.Selection(
        [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('returned', 'Returned'),
            ('escalated', 'Escalated'),
            ('skipped', 'Skipped'),
        ],
        required=True,
        default='pending',
        index=True,
    )
    comment = fields.Text()
    decided_on = fields.Datetime()
    hop = fields.Integer(default=0)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self.check_access('create')
        if not self.env.context.get(DECISION_CTX):
            raise UserError('Approval decisions are created by the procurement workflow.')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(DECISION_CTX):
            raise UserError('Approval decisions cannot be edited directly.')
        return super().write(vals)

    def unlink(self):
        raise UserError('Approval decisions cannot be deleted.')

    @api.model
    def _cron_escalate(self):
        from ..services.approval_service import ApprovalService
        return ApprovalService(self.env).escalate_due()
