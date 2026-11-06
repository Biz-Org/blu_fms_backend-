# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

DEFINITION_STATES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('archived', 'Archived'),
]


class WorkflowEngineDefinition(models.Model):
    _name = 'workflow.engine.definition'
    _description = 'Workflow Definition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'workflow.engine.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(required=True, index=True, copy=False)
    description = fields.Text()
    active = fields.Boolean(default=True)
    state = fields.Selection(
        DEFINITION_STATES,
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )
    owner_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
    site_ref = fields.Char(
        string='Site / Property Reference',
        help='Future-compatible site/property identifier. No Property module dependency.',
        index=True,
    )
    template_id = fields.Many2one(
        'workflow.engine.template',
        string='Source Template',
        ondelete='set null',
        index=True,
    )
    active_version_id = fields.Many2one(
        'workflow.engine.version',
        string='Active Version',
        ondelete='restrict',
        index=True,
        copy=False,
    )
    version_ids = fields.One2many('workflow.engine.version', 'definition_id', string='Versions')
    trigger_ids = fields.One2many('workflow.engine.trigger', 'definition_id', string='Triggers')
    execution_ids = fields.One2many('workflow.engine.execution', 'definition_id', string='Executions')
    version_count = fields.Integer(compute='_compute_version_count')

    _sql_constraints = [
        ('we_definition_code_uniq', 'unique(code)', 'Workflow definition code must be unique.'),
    ]

    @api.depends('version_ids')
    def _compute_version_count(self):
        for rec in self:
            rec.version_count = len(rec.version_ids)

    @api.constrains('active_version_id', 'version_ids')
    def _check_active_version_belongs(self):
        for rec in self:
            if rec.active_version_id and rec.active_version_id.definition_id != rec:
                raise ValidationError('Active version must belong to this workflow definition.')

    def action_publish(self):
        self._we_require_admin()
        for rec in self:
            drafts = rec.version_ids.filtered(lambda v: v.state == 'draft')
            if not drafts:
                raise UserError('Publish a draft version before publishing this workflow.')
            drafts.action_publish()
        return True

    def action_activate(self):
        self._we_require_admin()
        for rec in self:
            version = rec.active_version_id or rec.version_ids.filtered(
                lambda v: v.state in ('published', 'inactive')
            )[:1]
            if not version:
                raise UserError('A published version is required before activation.')
            version.action_activate()
        return True

    def action_deactivate(self):
        self._we_require_admin()
        for rec in self:
            if rec.active_version_id:
                rec.active_version_id.action_deactivate()
            else:
                rec.write({'state': 'inactive', 'active': False})
                rec._we_audit('deactivate')
        return True

    def action_archive(self):
        self._we_require_admin()
        for rec in self:
            if rec.active_version_id and rec.active_version_id.state == 'active':
                rec.active_version_id.with_context(we_version_transition=True).write({
                    'state': 'inactive',
                })
            rec.write({'state': 'archived', 'active': False, 'active_version_id': False})
            rec._we_audit('deactivate', details='archived')
        return True
