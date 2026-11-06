# -*- coding: utf-8 -*-
from odoo import fields, models

AUDIT_ACTIONS = [
    ('create', 'Create'),
    ('update', 'Update'),
    ('publish', 'Publish'),
    ('activate', 'Activate'),
    ('deactivate', 'Deactivate'),
    ('approve', 'Approve'),
    ('reject', 'Reject'),
    ('assign', 'Assign'),
    ('reassign', 'Reassign'),
    ('complete', 'Complete'),
    ('retry', 'Retry'),
    ('escalate', 'Escalate'),
    ('failure', 'Failure'),
]


class WorkflowEngineAuditEvent(models.Model):
    _name = 'workflow.engine.audit.event'
    _description = 'Workflow Audit Event'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    action = fields.Selection(AUDIT_ACTIONS, required=True, index=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, index=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, index=True)
    model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    execution_id = fields.Many2one(
        'workflow.engine.execution',
        ondelete='set null',
        index=True,
    )
    details = fields.Text()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
