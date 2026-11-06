# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .selections import MANAGER_GROUP, SCOPE_DIMENSIONS


class UtilityAccessScope(models.Model):
    _name = 'utility.management.access.scope'
    _description = 'Utility Access Scope'
    _inherit = ['utility.management.mixin']
    _order = 'dimension, ref_code, id'
    _check_company_auto = True

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade')
    dimension = fields.Selection(SCOPE_DIMENSIONS, required=True, index=True)
    ref_code = fields.Char(required=True, index=True)
    label = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'scope_unique',
            'unique(user_id, company_id, dimension, ref_code)',
            'This scope is already assigned to the user.',
        ),
    ]

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError('Only a Facility Manager can change access scope.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        records = super().create(vals_list)
        for company in records.mapped('company_id'):
            records._utility_resync_company(company)
        return records

    def write(self, vals):
        self._check_manager()
        result = super().write(vals)
        for company in self.mapped('company_id'):
            self._utility_resync_company(company)
        return result

    def unlink(self):
        raise UserError('Scope rows are deactivated instead of deleted.')
