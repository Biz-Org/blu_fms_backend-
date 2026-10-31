# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.workflow_engine.services.escalation_service import WorkflowEscalationService
from odoo.addons.workflow_engine.services.task_service import WorkflowTaskService

TASK_STATES = [
    ('open', 'Open'),
    ('in_progress', 'In Progress'),
    ('done', 'Done'),
    ('escalated', 'Escalated'),
]

TASK_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Normal'),
    ('2', 'High'),
    ('3', 'Urgent'),
]


class WorkflowEngineTask(models.Model):
    _name = 'workflow.engine.task'
    _description = 'Workflow Task'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'workflow.engine.mixin']
    _order = 'date_deadline, id'
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
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
    node_id = fields.Many2one(
        'workflow.engine.node',
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        related='execution_id.company_id',
        store=True,
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Assignee', index=True, tracking=True)
    group_id = fields.Many2one('res.groups', string='Assigned Group', index=True)
    priority = fields.Selection(TASK_PRIORITIES, default='1', required=True, index=True)
    date_deadline = fields.Datetime(string='Due Date', index=True)
    sla_deadline = fields.Datetime(index=True)
    state = fields.Selection(
        TASK_STATES,
        default='open',
        required=True,
        index=True,
        tracking=True,
    )

    def action_assign(self, user_id=False, group_id=False):
        return WorkflowTaskService(self.env).assign(self, user_id=user_id, group_id=group_id)

    def action_reassign(self, user_id=False, group_id=False):
        return WorkflowTaskService(self.env).reassign(self, user_id=user_id, group_id=group_id)

    def action_start(self):
        return WorkflowTaskService(self.env).start(self)

    def action_complete(self):
        return WorkflowTaskService(self.env).complete(self)

    def action_escalate(self):
        self._we_require_manager()
        service = WorkflowEscalationService(self.env)
        for rec in self:
            service.escalate(task=rec, automatic=False)
        return True
