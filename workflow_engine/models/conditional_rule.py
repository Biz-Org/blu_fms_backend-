# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

RULE_TYPES = [
    ('approval_routing', 'Approval Routing'),
    ('assignment', 'Assignment'),
    ('branch', 'Branch'),
]

CRITERIA = [
    ('department', 'Department'),
    ('role', 'Role'),
    ('value', 'Value'),
    ('property', 'Property'),
    ('site', 'Site'),
    ('module', 'Module'),
]

OPERATORS = [
    ('=', '='),
    ('!=', '!='),
    ('in', 'in'),
    ('<', '<'),
    ('<=', '<='),
    ('>', '>'),
    ('>=', '>='),
]


class WorkflowEngineConditionRule(models.Model):
    _name = 'workflow.engine.condition.rule'
    _description = 'Conditional Rule'
    _inherit = ['workflow.engine.mixin']
    _order = 'priority, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    rule_type = fields.Selection(RULE_TYPES, required=True, index=True)
    criterion = fields.Selection(CRITERIA, required=True, index=True)
    operator = fields.Selection(OPERATORS, required=True, default='=')
    value = fields.Char(
        string='Comparison Value',
        required=True,
        help='Literal value or identifier. Property/site/department are stored as references, not FMS models.',
    )
    priority = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)
    date_from = fields.Datetime(string='Effective From')
    date_to = fields.Datetime(string='Effective To')
    definition_id = fields.Many2one('workflow.engine.definition', ondelete='cascade', index=True)
    version_id = fields.Many2one('workflow.engine.version', ondelete='cascade', index=True)
    hierarchy_id = fields.Many2one(
        'workflow.engine.approval.hierarchy',
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)

    @api.constrains('version_id', 'definition_id')
    def _check_version_definition(self):
        for rec in self:
            if rec.version_id and rec.definition_id and rec.version_id.definition_id != rec.definition_id:
                raise ValidationError('Conditional rule version must belong to the selected workflow definition.')

    @api.constrains('rule_type')
    def _check_rule_type(self):
        allowed = {item[0] for item in RULE_TYPES}
        for rec in self:
            if rec.rule_type not in allowed:
                raise ValidationError('Unsupported conditional rule type.')

    @api.constrains('operator')
    def _check_operator(self):
        allowed = {item[0] for item in OPERATORS}
        for rec in self:
            if rec.operator not in allowed:
                raise ValidationError('Unsupported conditional operator.')
