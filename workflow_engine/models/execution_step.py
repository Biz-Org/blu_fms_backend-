# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

STEP_STATES = [
    ('pending', 'Pending'),
    ('running', 'Running'),
    ('waiting', 'Waiting'),
    ('done', 'Done'),
    ('failed', 'Failed'),
    ('skipped', 'Skipped'),
]


class WorkflowEngineExecutionStep(models.Model):
    _name = 'workflow.engine.execution.step'
    _description = 'Execution Step'
    _inherit = ['workflow.engine.mixin']
    _order = 'execution_id, sequence, id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    execution_id = fields.Many2one(
        'workflow.engine.execution',
        required=True,
        ondelete='cascade',
        index=True,
    )
    node_id = fields.Many2one(
        'workflow.engine.node',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        related='execution_id.company_id',
        store=True,
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    state = fields.Selection(STEP_STATES, default='pending', required=True, index=True)
    date_start = fields.Datetime()
    date_end = fields.Datetime()
    input_json = fields.Json(string='Input')
    output_json = fields.Json(string='Output')
    error_message = fields.Text()
    retry_count = fields.Integer(default=0)

    @api.depends('node_id.name', 'sequence')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.node_id.name or ('Step %s' % rec.sequence)

    @api.constrains('node_id', 'execution_id')
    def _check_node_version(self):
        for rec in self:
            if rec.node_id.version_id != rec.execution_id.version_id:
                raise ValidationError('Execution step node must belong to the execution workflow version.')

    def action_retry(self):
        self._we_require_manager()
        for rec in self:
            if rec.state != 'failed':
                raise UserError('Only failed steps can be retried.')
            rec.write({'retry_count': rec.retry_count + 1})
            if rec.execution_id.state == 'failed':
                rec.execution_id.write({'state': 'running', 'error_message': False})
            rec.env['workflow.engine.execution.step'].create({
                'execution_id': rec.execution_id.id,
                'node_id': rec.node_id.id,
                'sequence': rec.sequence,
                'state': 'pending',
                'input_json': rec.input_json,
            })
            rec.execution_id._we_audit('retry', execution=rec.execution_id)
        return True
