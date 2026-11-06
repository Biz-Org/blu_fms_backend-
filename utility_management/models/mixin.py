# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .selections import (
    LOCATION_FIELDS,
    LOCATION_REF_FIELDS,
    MANAGER_GROUP,
    SCOPE_DIMENSIONS,
    STAFF_GROUP,
)


def staff_link(relation, column):
    return fields.Many2many(
        'res.users',
        relation,
        column,
        'user_id',
        string='Allowed Staff',
    )


class UtilityManagementMixin(models.AbstractModel):
    _name = 'utility.management.mixin'
    _description = 'Utility Management Access Mixin'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    def _utility_is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    def _utility_require_staff(self):
        user = self.env.user
        if not user or user._is_public() or not user.has_group(STAFF_GROUP):
            raise UserError('Utility Management requires an authenticated utility user.')

    def _utility_location_from(self, source):
        values = {}
        for name in LOCATION_FIELDS:
            if name in source._fields:
                values[name] = source[name] or False
        return values

    def _utility_candidate_users(self):
        self.ensure_one()
        users = self.env['res.users']
        if self.create_uid:
            users |= self.create_uid
        for fname in ('assignee_id', 'user_id', 'owner_id', 'escalate_to_id'):
            if fname in self._fields and self[fname]:
                users |= self[fname]
        scope_model = self.env['utility.management.access.scope'].sudo()
        dimension_fields = {
            'property': 'property_ref',
            'site': 'site_ref',
            'department': 'department_ref',
        }
        matched = False
        for dimension, fname in dimension_fields.items():
            if fname not in self._fields or not self[fname]:
                continue
            matched = True
            users |= scope_model.search([
                ('company_id', '=', self.company_id.id),
                ('dimension', '=', dimension),
                ('ref_code', '=', self[fname]),
                ('active', '=', True),
            ]).mapped('user_id')
        if not matched and self._name == 'utility.management.report.definition':
            users |= self._utility_company_staff()
        return users

    def _utility_company_staff(self):
        self.ensure_one()
        group = self.env.ref(STAFF_GROUP)
        return group.users.filtered(lambda user: self.company_id in user.company_ids)

    def _utility_sync_staff(self):
        if 'allowed_staff_ids' not in self._fields:
            return
        for record in self:
            users = record._utility_candidate_users()
            record.sudo().with_context(utility_staff_sync=True).write({
                'allowed_staff_ids': [(6, 0, users.ids)],
            })

    def _utility_resync_company(self, company):
        if not company:
            return
        for model_name in (
            'utility.management.meter',
            'utility.management.reading',
            'utility.management.power.source',
            'utility.management.leak',
            'utility.management.alert',
            'utility.management.report.definition',
            'utility.management.audit.event',
        ):
            records = self.env[model_name].sudo().search([('company_id', '=', company.id)])
            records._utility_sync_staff()

    def unlink(self):
        raise UserError('Utility records are kept. Deactivate a meter or correct a reading instead of deleting it.')

    @api.model
    def _utility_scope_dimensions(self):
        return [item[0] for item in SCOPE_DIMENSIONS]
