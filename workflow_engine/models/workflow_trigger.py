# -*- coding: utf-8 -*-
from odoo import fields, models


class WorkflowEngineTrigger(models.Model):
    _name = 'workflow.engine.trigger'
    _description = 'Workflow Trigger'
    _inherit = ['workflow.engine.version.locked.mixin']
    _order = 'version_id, id'
    _check_company_auto = True

    name = fields.Char(required=True)
    description = fields.Text()
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
    source_module = fields.Char(required=True, index=True)
    source_model = fields.Char(required=True, index=True)
    event_code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    domain_json = fields.Json(string='Optional Domain / Conditions')
