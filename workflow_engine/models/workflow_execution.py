# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.workflow_engine.services.execution_service import WorkflowExecutionService
from odoo.addons.workflow_engine.services.trigger_service import WorkflowTriggerService

EXECUTION_STATES = [
    ('running', 'Running'),
    ('waiting_approval', 'Waiting Approval'),
    ('waiting_task', 'Waiting Task'),
    ('escalated', 'Escalated'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
]


class WorkflowEngineExecution(models.Model):
    _name = 'workflow.engine.execution'
    _description = 'Workflow Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'workflow.engine.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, index=True, copy=False, default='New')
    definition_id = fields.Many2one(
        'workflow.engine.definition',
        required=True,
        ondelete='restrict',
        index=True,
    )
    version_id = fields.Many2one(
        'workflow.engine.version',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
    site_ref = fields.Char(index=True)
    source_module = fields.Char(index=True)
    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(string='Source Record ID', index=True)
    event_code = fields.Char(index=True)
    payload_json = fields.Json(string='Payload')
    state = fields.Selection(
        EXECUTION_STATES,
        default='running',
        required=True,
        index=True,
        tracking=True,
    )
    current_node_id = fields.Many2one('workflow.engine.node', ondelete='set null', index=True)
    current_step_id = fields.Many2one(
        'workflow.engine.execution.step',
        ondelete='set null',
        index=True,
    )
    date_start = fields.Datetime(default=fields.Datetime.now, index=True)
    date_end = fields.Datetime()
    sla_deadline = fields.Datetime()
    error_message = fields.Text()
    step_ids = fields.One2many('workflow.engine.execution.step', 'execution_id', string='Steps')
    task_ids = fields.One2many('workflow.engine.task', 'execution_id', string='Tasks')
    approval_request_ids = fields.One2many(
        'workflow.engine.approval.request',
        'execution_id',
        string='Approval Requests',
    )

    @api.constrains('version_id', 'definition_id')
    def _check_version_bound_to_definition(self):
        for rec in self:
            if rec.version_id.definition_id != rec.definition_id:
                raise ValidationError(
                    'An execution must stay bound to a version of its workflow definition.'
                )

    @api.constrains('current_node_id', 'version_id')
    def _check_current_node_version(self):
        for rec in self:
            if rec.current_node_id and rec.current_node_id.version_id != rec.version_id:
                raise ValidationError(
                    'Current node must belong to the execution workflow version.'
                )

    def write(self, vals):
        if 'version_id' in vals:
            for rec in self:
                if rec.version_id and vals['version_id'] != rec.version_id.id:
                    raise ValidationError(
                        'An execution cannot be retargeted to another workflow version.'
                    )
        if 'state' in vals:
            allowed = {item[0] for item in EXECUTION_STATES}
            if vals['state'] not in allowed:
                raise ValidationError('Unsupported execution state: %s' % vals['state'])
        return super().write(vals)

    def action_start(self):
        service = WorkflowExecutionService(self.env)
        for rec in self:
            service.start(rec)
        return True

    def action_advance(self):
        service = WorkflowExecutionService(self.env)
        for rec in self:
            service.advance(rec)
        return True

    def action_retry(self):
        self._we_require_manager()
        service = WorkflowExecutionService(self.env)
        for rec in self:
            service.retry(rec)
        return True

    @api.model
    def trigger_workflow(self, source_module, source_model, event_code, record=None, payload=None):
        return WorkflowTriggerService(self.env).trigger(
            source_module, source_model, event_code, record=record, payload=payload,
        )
