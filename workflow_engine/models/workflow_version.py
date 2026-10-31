# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

VERSION_STATES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('superseded', 'Superseded'),
]


class WorkflowEngineVersion(models.Model):
    _name = 'workflow.engine.version'
    _description = 'Workflow Version'
    _inherit = ['workflow.engine.mixin']
    _order = 'definition_id, version desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    definition_id = fields.Many2one(
        'workflow.engine.definition',
        required=True,
        ondelete='cascade',
        index=True,
    )
    version = fields.Integer(required=True, default=1, index=True)
    state = fields.Selection(
        VERSION_STATES,
        default='draft',
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='definition_id.company_id',
        store=True,
        index=True,
    )
    date_from = fields.Datetime(string='Effective From')
    date_to = fields.Datetime(string='Effective To')
    published_at = fields.Datetime(readonly=True)
    activated_at = fields.Datetime(readonly=True)
    validation_ok = fields.Boolean(string='Last Validation OK', readonly=True)
    validation_message = fields.Text(readonly=True)
    node_ids = fields.One2many('workflow.engine.node', 'version_id', string='Nodes')
    edge_ids = fields.One2many('workflow.engine.edge', 'version_id', string='Edges')
    trigger_ids = fields.One2many('workflow.engine.trigger', 'version_id', string='Triggers')
    execution_ids = fields.One2many('workflow.engine.execution', 'version_id', string='Executions')

    _sql_constraints = [
        (
            'we_version_definition_number_uniq',
            'unique(definition_id, version)',
            'Version number must be unique per workflow definition.',
        ),
    ]

    @api.depends('definition_id.name', 'version', 'state')
    def _compute_name(self):
        for rec in self:
            defn = rec.definition_id.name or 'Workflow'
            rec.name = '%s v%s (%s)' % (defn, rec.version, rec.state)

    @api.constrains('definition_id', 'state')
    def _check_one_draft_per_definition(self):
        for rec in self:
            if rec.state != 'draft' or not rec.definition_id:
                continue
            drafts = self.search_count([
                ('definition_id', '=', rec.definition_id.id),
                ('state', '=', 'draft'),
                ('id', '!=', rec.id),
            ])
            if drafts:
                raise ValidationError('Only one draft version is allowed per workflow definition.')

    def _assert_draft(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(
                    'Published versions are immutable. Create a new draft version to make changes.'
                )

    def write(self, vals):
        if not self.env.context.get('we_version_transition'):
            self._assert_draft()
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda v: v.state != 'draft') and not self.env.context.get('we_version_transition'):
            raise ValidationError('Only draft versions can be deleted.')
        return super().unlink()

    def action_validate(self):
        """Validate graph structure for Builder. Does not mutate published versions."""
        self.ensure_one()
        errors = []
        warnings = []
        starts = self.node_ids.filtered(lambda n: n.node_type == 'start')
        ends = self.node_ids.filtered(lambda n: n.node_type == 'end')
        if len(starts) != 1:
            errors.append('Workflow must have exactly one Start node.')
        if not ends:
            errors.append('Workflow must have at least one End node.')
        if not self.node_ids:
            errors.append('Workflow has no nodes.')
        node_ids = set(self.node_ids.ids)
        for edge in self.edge_ids:
            if edge.source_node_id.id not in node_ids or edge.target_node_id.id not in node_ids:
                errors.append('Edge "%s" references a node outside this version.' % (edge.name or edge.id))
            if edge.source_node_id.version_id != self or edge.target_node_id.version_id != self:
                errors.append('Cross-version edge detected on edge %s.' % edge.id)
        for node in self.node_ids.filtered(lambda n: n.node_type != 'end'):
            if not node.outgoing_edge_ids:
                warnings.append('Node "%s" has no outgoing edges.' % node.name)
        for node in self.node_ids.filtered(lambda n: n.node_type == 'approval'):
            if not node.hierarchy_id:
                errors.append('Approval node "%s" has no hierarchy configured.' % node.name)
        for node in self.node_ids.filtered(lambda n: n.node_type == 'conditional'):
            if len(node.outgoing_edge_ids) < 2:
                warnings.append('Conditional node "%s" should have at least two branches.' % node.name)
        if not self.trigger_ids:
            warnings.append('No triggers configured for this version.')
        ok = not errors
        message = '\n'.join(errors + warnings) or 'Validation passed.'
        if self.state == 'draft':
            self.with_context(we_version_transition=True).write({
                'validation_ok': ok,
                'validation_message': message,
            })
        return {
            'ok': ok,
            'errors': errors,
            'warnings': warnings,
            'message': message,
        }

    def action_publish(self):
        self._we_require_admin()
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only a draft version can be published.')
            result = rec.action_validate()
            if not result.get('ok'):
                raise UserError(result.get('message') or 'Validation failed.')
            rec.with_context(we_version_transition=True).write({
                'state': 'published',
                'published_at': fields.Datetime.now(),
                'validation_ok': True,
                'validation_message': result.get('message') or False,
            })
            if rec.definition_id.state == 'draft':
                rec.definition_id.write({'state': 'published'})
            rec.definition_id._we_audit('publish', details='version %s' % rec.version)
        return True

    def action_activate(self):
        self._we_require_admin()
        for rec in self:
            if rec.state not in ('published', 'inactive'):
                raise UserError('Only published or inactive versions can be activated.')
            others = rec.definition_id.version_ids.filtered(
                lambda v: v.id != rec.id and v.state == 'active'
            )
            if others:
                others.with_context(we_version_transition=True).write({'state': 'superseded'})
            rec.with_context(we_version_transition=True).write({
                'state': 'active',
                'activated_at': fields.Datetime.now(),
            })
            rec.definition_id.write({
                'state': 'active',
                'active': True,
                'active_version_id': rec.id,
            })
            rec.definition_id._we_audit('activate', details='version %s' % rec.version)
        return True

    def action_deactivate(self):
        self._we_require_admin()
        for rec in self:
            if rec.state != 'active':
                raise UserError('Only an active version can be deactivated.')
            rec.with_context(we_version_transition=True).write({'state': 'inactive'})
            vals = {'state': 'inactive', 'active': False}
            if rec.definition_id.active_version_id == rec:
                vals['active_version_id'] = False
            rec.definition_id.write(vals)
            rec.definition_id._we_audit('deactivate', details='version %s' % rec.version)
        return True
