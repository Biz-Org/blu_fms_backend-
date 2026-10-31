# -*- coding: utf-8 -*-
from odoo import fields, models


class WorkflowEngineApprovalHierarchy(models.Model):
    _name = 'workflow.engine.approval.hierarchy'
    _description = 'Approval Hierarchy'
    _inherit = ['workflow.engine.mixin']
    _order = 'priority, name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10, index=True)
    source_module = fields.Char(
        string='Applicable Module',
        help='Optional source-module context. Not a dependency on a future FMS addon.',
        index=True,
    )
    definition_id = fields.Many2one(
        'workflow.engine.definition',
        ondelete='set null',
        index=True,
    )
    date_from = fields.Datetime(string='Effective From')
    date_to = fields.Datetime(string='Effective To')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
    level_ids = fields.One2many(
        'workflow.engine.approval.level',
        'hierarchy_id',
        string='Approval Levels',
    )

    def action_activate(self):
        self._we_require_manager()
        self.write({'active': True})
        return True

    def action_deactivate(self):
        self._we_require_manager()
        self.write({'active': False})
        return True
