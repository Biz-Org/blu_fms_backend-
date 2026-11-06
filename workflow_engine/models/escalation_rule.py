# -*- coding: utf-8 -*-
from odoo import api, fields, models

ESCALATION_TARGETS = [
    ('task', 'Task'),
    ('approval', 'Approval'),
]

ESCALATION_MODES = [
    ('automatic', 'Automatic'),
    ('manual', 'Manual'),
]


class WorkflowEngineEscalationRule(models.Model):
    _name = 'workflow.engine.escalation.rule'
    _description = 'Escalation Rule'
    _inherit = ['workflow.engine.mixin']
    _order = 'priority, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10, index=True)
    definition_id = fields.Many2one('workflow.engine.definition', ondelete='cascade', index=True)
    node_id = fields.Many2one('workflow.engine.node', ondelete='set null', index=True)
    target_type = fields.Selection(ESCALATION_TARGETS, required=True, default='task')
    mode = fields.Selection(ESCALATION_MODES, required=True, default='automatic')
    delay_minutes = fields.Integer(string='Timer (minutes)', default=60)
    level = fields.Integer(string='Escalation Level', default=1)
    user_id = fields.Many2one('res.users', string='Recipient User', index=True)
    group_id = fields.Many2one('res.groups', string='Recipient Group', index=True)
    notify = fields.Boolean(default=True)
    config_json = fields.Json(string='Configuration')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)

    @api.model
    def _cron_process_escalations(self):
        from odoo.addons.workflow_engine.services.escalation_service import WorkflowEscalationService
        return WorkflowEscalationService(self.env).process()
