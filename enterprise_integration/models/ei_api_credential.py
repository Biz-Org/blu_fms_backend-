# -*- coding: utf-8 -*-
import hashlib
import secrets

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class EiApiCredential(models.Model):
    _name = 'ei.api.credential'
    _description = 'API Credential / Key'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True)
    endpoint_id = fields.Many2one('ei.api.endpoint', ondelete='cascade', index=True)
    integration_id = fields.Many2one('ei.integration', ondelete='cascade', index=True)
    active = fields.Boolean(default=True)
    key_prefix = fields.Char(readonly=True, copy=False, index=True)
    key_hash = fields.Char(readonly=True, copy=False, index=True)
    secret_display = fields.Char(
        string='Secret (masked)',
        compute='_compute_secret_display',
    )
    plaintext_key = fields.Char(string='New Key (write-only)', copy=False)
    expiry_date = fields.Date()
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('expired', 'Expired'),
            ('revoked', 'Revoked'),
        ],
        default='active',
        required=True,
        index=True,
    )
    last_used_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one(
        'res.company', compute='_compute_company', store=True, readonly=True, index=True,
    )

    @api.depends('endpoint_id.company_id', 'integration_id.company_id')
    def _compute_company(self):
        for rec in self:
            rec.company_id = rec.endpoint_id.company_id or rec.integration_id.company_id

    def _compute_secret_display(self):
        for rec in self:
            rec.secret_display = f'{rec.key_prefix}••••••••' if rec.key_prefix else '••••••••'

    def _check_credential_access(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            raise AccessError(
                'Only Enterprise Integration Managers or Administrators can manage API credentials.'
            )

    @staticmethod
    def _hash_key(plaintext):
        return hashlib.sha256(plaintext.encode()).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        self._check_credential_access()
        for vals in vals_list:
            plaintext = vals.pop('plaintext_key', None) or secrets.token_urlsafe(32)
            vals['key_prefix'] = plaintext[:8]
            vals['key_hash'] = self._hash_key(plaintext)
        return super().create(vals_list)

    def write(self, vals):
        self._check_credential_access()
        plaintext = vals.pop('plaintext_key', None)
        if plaintext:
            vals['key_prefix'] = plaintext[:8]
            vals['key_hash'] = self._hash_key(plaintext)
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_admin'):
            raise AccessError('Only Administrators can delete API credentials.')
        return super().unlink()

    @api.constrains('endpoint_id', 'integration_id')
    def _check_link(self):
        for rec in self:
            if not rec.endpoint_id and not rec.integration_id:
                raise ValidationError('API credential must link to an endpoint or integration.')

    def action_revoke(self):
        self._check_credential_access()
        self.write({'state': 'revoked', 'active': False})

    def verify_key(self, plaintext):
        if not plaintext:
            return self.browse()
        digest = self._hash_key(plaintext)
        return self.search([('key_hash', '=', digest), ('state', '=', 'active')], limit=1)

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields=fields, load=load)
        if fields is None or (fields and 'key_hash' in fields):
            if not self.env.user.has_group('enterprise_integration.group_ei_admin'):
                for row in result:
                    if 'key_hash' in row:
                        row['key_hash'] = False
        return result
