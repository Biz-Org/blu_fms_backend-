# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

NODE_TYPES = [
    ('start', 'Start'),
    ('end', 'End'),
    ('action', 'Action'),
    ('approval', 'Approval'),
    ('task', 'Task'),
    ('notification', 'Notification'),
    ('conditional', 'Conditional'),
]


class WorkflowEngineNode(models.Model):
    _name = 'workflow.engine.node'
    _description = 'Workflow Node'
    _inherit = ['workflow.engine.version.locked.mixin']
    _order = 'version_id, sequence, id'
    _check_company_auto = True

    name = fields.Char(required=True)
    technical_key = fields.Char(required=True, index=True)
    version_id = fields.Many2one(
        'workflow.engine.version',
        required=True,
        ondelete='cascade',
        index=True,
    )
    definition_id = fields.Many2one(
        related='version_id.definition_id',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='version_id.company_id',
        store=True,
        index=True,
    )
    node_type = fields.Selection(NODE_TYPES, required=True, index=True)
    sequence = fields.Integer(default=10, index=True)
    pos_x = fields.Float(string='Canvas X', default=80.0)
    pos_y = fields.Float(string='Canvas Y', default=80.0)
    active = fields.Boolean(default=True)
    config_json = fields.Json(string='Configuration')
    input_mapping = fields.Json(string='Input Mapping')
    output_mapping = fields.Json(string='Output Mapping')
    hierarchy_id = fields.Many2one(
        'workflow.engine.approval.hierarchy',
        ondelete='set null',
        index=True,
    )
    rule_id = fields.Many2one(
        'workflow.engine.condition.rule',
        ondelete='set null',
        index=True,
    )
    mail_template_id = fields.Many2one('mail.template', ondelete='set null')
    outgoing_edge_ids = fields.One2many(
        'workflow.engine.edge',
        'source_node_id',
        string='Outgoing Edges',
    )
    incoming_edge_ids = fields.One2many(
        'workflow.engine.edge',
        'target_node_id',
        string='Incoming Edges',
    )

    _sql_constraints = [
        (
            'we_node_version_key_uniq',
            'unique(version_id, technical_key)',
            'Node technical key must be unique within a workflow version.',
        ),
    ]

    @api.constrains('node_type')
    def _check_node_type(self):
        allowed = {item[0] for item in NODE_TYPES}
        for rec in self:
            if rec.node_type not in allowed:
                raise ValidationError('Unsupported workflow node type.')
