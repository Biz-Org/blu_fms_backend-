# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class WorkflowEngineMixin(models.AbstractModel):
    _name = 'workflow.engine.mixin'
    _description = 'Workflow Engine Access Helpers'

    def _we_require_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _we_require_admin(self):
        self._we_require_group(
            'workflow_engine.group_we_admin',
            'Only Workflow Engine Administrators can perform this action.',
        )

    def _we_require_manager(self):
        self._we_require_group(
            'workflow_engine.group_we_manager',
            'Only Workflow Engine Managers can perform this action.',
        )

    def _we_audit(self, action, execution=None, details=None):
        self.ensure_one()
        self.env['workflow.engine.audit.event'].sudo().create({
            'name': action,
            'action': action,
            'user_id': self.env.user.id,
            'model': self._name,
            'res_id': self.id,
            'execution_id': execution.id if execution else False,
            'details': details or '',
            'company_id': getattr(self, 'company_id', self.env.company).id,
        })


class WorkflowEngineVersionLockedMixin(models.AbstractModel):
    _name = 'workflow.engine.version.locked.mixin'
    _description = 'Immutable published version graph records'

    @api.model_create_multi
    def create(self, vals_list):
        Version = self.env['workflow.engine.version']
        for vals in vals_list:
            if vals.get('version_id'):
                Version.browse(vals['version_id'])._assert_draft()
        return super().create(vals_list)

    def write(self, vals):
        self.mapped('version_id')._assert_draft()
        if vals.get('version_id'):
            self.env['workflow.engine.version'].browse(vals['version_id'])._assert_draft()
        return super().write(vals)

    def unlink(self):
        self.mapped('version_id')._assert_draft()
        return super().unlink()

