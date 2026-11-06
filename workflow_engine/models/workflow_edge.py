# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WorkflowEngineEdge(models.Model):
    _name = 'workflow.engine.edge'
    _description = 'Workflow Edge'
    _inherit = ['workflow.engine.version.locked.mixin']
    _order = 'version_id, sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Label')
    version_id = fields.Many2one(
        'workflow.engine.version',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='version_id.company_id',
        store=True,
        index=True,
    )
    source_node_id = fields.Many2one(
        'workflow.engine.node',
        required=True,
        ondelete='cascade',
        index=True,
    )
    target_node_id = fields.Many2one(
        'workflow.engine.node',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    is_default = fields.Boolean(string='Default Branch')
    condition_json = fields.Json(string='Branch Condition')
    rule_id = fields.Many2one(
        'workflow.engine.condition.rule',
        ondelete='set null',
        index=True,
    )

    @api.constrains('source_node_id', 'target_node_id', 'version_id')
    def _check_same_version_and_no_loop(self):
        for rec in self:
            if rec.source_node_id == rec.target_node_id:
                raise ValidationError('Workflow edges cannot form a self-loop.')
            if rec.source_node_id.version_id != rec.version_id:
                raise ValidationError('Edge source node must belong to the same workflow version.')
            if rec.target_node_id.version_id != rec.version_id:
                raise ValidationError('Edge target node must belong to the same workflow version.')
