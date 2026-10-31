# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

TEMPLATE_STATES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]


class WorkflowEngineTemplate(models.Model):
    _name = 'workflow.engine.template'
    _description = 'Workflow Template'
    _inherit = ['mail.thread', 'workflow.engine.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True, tracking=True)
    description = fields.Text()
    category = fields.Char(index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        TEMPLATE_STATES,
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )
    version = fields.Char(string='Template Version', default='1')
    required_modules = fields.Char(
        help='Comma-separated technical module names required to use this template.',
    )
    usage_count = fields.Integer(default=0, readonly=True)
    payload_json = fields.Json(string='Template Payload')
    owner_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)

    def action_activate(self):
        self._we_require_manager()
        self.write({'state': 'active', 'active': True})
        for rec in self:
            rec._we_audit('activate')
        return True

    def action_deactivate(self):
        self._we_require_manager()
        self.write({'state': 'inactive', 'active': False})
        for rec in self:
            rec._we_audit('deactivate')
        return True

    def action_duplicate(self):
        self._we_require_manager()
        self.ensure_one()
        copy = self.copy({
            'name': '%s (Copy)' % self.name,
            'state': 'draft',
            'usage_count': 0,
        })
        copy._we_audit('create', details='duplicated from %s' % self.id)
        return copy

    def action_create_workflow(self, vals=None):
        """Create a draft workflow definition/version from template payload."""
        self._we_require_manager()
        self.ensure_one()
        if self.state != 'active':
            raise UserError('Only active templates can create workflows.')
        vals = vals or {}
        payload = self.payload_json if isinstance(self.payload_json, dict) else {}
        name = vals.get('name') or payload.get('name') or self.name
        code = vals.get('code') or ('TPL_%s_%s' % (self.id, fields.Datetime.now().strftime('%Y%m%d%H%M%S')))
        ui = self.env['workflow.engine.ui.api']
        graph = ui.create_workflow({
            'name': name,
            'code': code,
            'description': vals.get('description') or self.description or False,
        })
        # Optionally apply template nodes if payload contains a graph
        graph_payload = payload.get('graph') if isinstance(payload, dict) else None
        if graph_payload and graph.get('version'):
            ui.save_builder_graph(
                graph['definition']['id'],
                graph['version']['id'],
                {
                    'definition': {'name': name, 'description': self.description or False},
                    'nodes': graph_payload.get('nodes') or [],
                    'edges': graph_payload.get('edges') or [],
                    'triggers': graph_payload.get('triggers') or [],
                },
            )
            graph = ui.load_builder_graph(graph['definition']['id'], graph['version']['id'])
        self.write({'usage_count': self.usage_count + 1})
        self._we_audit('create', details='workflow from template')
        return graph
