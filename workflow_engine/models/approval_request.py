# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.workflow_engine.services.approval_service import WorkflowApprovalService

APPROVAL_STATES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class WorkflowEngineApprovalRequest(models.Model):
    _name = 'workflow.engine.approval.request'
    _description = 'Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'workflow.engine.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    execution_id = fields.Many2one(
        'workflow.engine.execution',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_id = fields.Many2one(
        'workflow.engine.execution.step',
        ondelete='set null',
        index=True,
    )
    hierarchy_id = fields.Many2one(
        'workflow.engine.approval.hierarchy',
        ondelete='restrict',
        index=True,
    )
    level_id = fields.Many2one(
        'workflow.engine.approval.level',
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        related='execution_id.company_id',
        store=True,
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Approver', index=True)
    group_id = fields.Many2one('res.groups', index=True)
    state = fields.Selection(
        APPROVAL_STATES,
        default='pending',
        required=True,
        index=True,
        tracking=True,
    )
    date_requested = fields.Datetime(default=fields.Datetime.now, index=True)
    date_decided = fields.Datetime()
    comment = fields.Text()
    decided_by = fields.Many2one('res.users', index=True)

    def action_approve(self, comment=None):
        service = WorkflowApprovalService(self.env)
        for rec in self:
            service.approve(rec, comment=comment)
        return True

    def action_reject(self, comment=None):
        service = WorkflowApprovalService(self.env)
        for rec in self:
            service.reject(rec, comment=comment)
        return True
