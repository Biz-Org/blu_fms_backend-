# -*- coding: utf-8 -*-
from odoo import fields, models

EVENT_STATES = [
    ('triggered', 'Triggered'),
    ('notified', 'Notified'),
    ('failed', 'Failed'),
]


class WorkflowEngineEscalationEvent(models.Model):
    _name = 'workflow.engine.escalation.event'
    _description = 'Escalation Event'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    execution_id = fields.Many2one(
        'workflow.engine.execution',
        required=True,
        ondelete='cascade',
        index=True,
    )
    task_id = fields.Many2one('workflow.engine.task', ondelete='set null', index=True)
    approval_id = fields.Many2one(
        'workflow.engine.approval.request',
        ondelete='set null',
        index=True,
    )
    rule_id = fields.Many2one(
        'workflow.engine.escalation.rule',
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one(
        related='execution_id.company_id',
        store=True,
        index=True,
    )
    level = fields.Integer(default=1)
    date_triggered = fields.Datetime(default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', string='Recipient User', index=True)
    group_id = fields.Many2one('res.groups', string='Recipient Group')
    automatic = fields.Boolean(default=True)
    state = fields.Selection(EVENT_STATES, default='triggered', required=True, index=True)
    note = fields.Text()
