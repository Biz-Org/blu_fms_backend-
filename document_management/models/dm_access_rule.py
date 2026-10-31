# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .dm_mixin import ACCESS_ORIGINS, ACCESS_PARTNER_TYPES, ACCESS_ROLES, ACCESS_RULE_STATES, ROLE_PERMISSIONS


class DocumentManagementAccessRule(models.Model):
    _name = 'document.management.access.rule'
    _description = 'Document Access Rule'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'document.management.document',
        ondelete='cascade',
        index=True,
    )
    folder_id = fields.Many2one(
        'document.management.folder',
        ondelete='cascade',
        index=True,
    )
    partner_type = fields.Selection(
        ACCESS_PARTNER_TYPES,
        required=True,
        default='user',
    )
    user_id = fields.Many2one('res.users', ondelete='cascade', index=True)
    group_id = fields.Many2one(
        'document.management.access.group',
        ondelete='cascade',
        index=True,
    )
    role = fields.Selection(ACCESS_ROLES, required=True, default='viewer')
    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=False)
    perm_download = fields.Boolean(default=True)
    perm_share = fields.Boolean(default=False)
    origin = fields.Selection(ACCESS_ORIGINS, required=True, default='direct')
    state = fields.Selection(
        ACCESS_RULE_STATES,
        required=True,
        default='active',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        compute='_compute_company_id',
        store=True,
        index=True,
    )

    @api.depends('document_id.company_id', 'folder_id.company_id')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.document_id.company_id or rec.folder_id.company_id

    @api.constrains('document_id', 'folder_id')
    def _check_target(self):
        for rec in self:
            if bool(rec.document_id) == bool(rec.folder_id):
                raise ValidationError('An access rule must target exactly one document or folder.')

    @api.constrains('partner_type', 'user_id', 'group_id')
    def _check_partner(self):
        for rec in self:
            if rec.partner_type == 'user' and not rec.user_id:
                raise ValidationError('A user access rule requires a user.')
            if rec.partner_type == 'group' and not rec.group_id:
                raise ValidationError('A group access rule requires an access group.')

    def _apply_role_permissions(self, vals):
        role = vals.get('role')
        if role in ROLE_PERMISSIONS:
            vals.update(ROLE_PERMISSIONS[role])
        elif not self.env.context.get('dm_lifecycle'):
            for key in ('perm_read', 'perm_write', 'perm_download', 'perm_share'):
                vals.pop(key, None)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            vals.setdefault('role', 'viewer')
            prepared.append(self._apply_role_permissions(vals))
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if 'state' in vals and set(vals) <= {'state'}:
            return super().write(vals)
        vals = self._apply_role_permissions(vals)
        return super().write(vals)

    @api.onchange('role')
    def _onchange_role(self):
        for rec in self:
            perms = ROLE_PERMISSIONS.get(rec.role)
            if perms:
                rec.update(perms)
