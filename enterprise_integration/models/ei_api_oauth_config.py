# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class EiApiOauthConfig(models.Model):
    _name = 'ei.api.oauth.config'
    _description = 'API OAuth Configuration'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True)
    integration_id = fields.Many2one(
        'ei.integration', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)
    client_id = fields.Char(required=True, index=True)
    client_secret = fields.Char(string='Client Secret', copy=False)
    client_secret_display = fields.Char(compute='_compute_secret_display')
    grant_type = fields.Selection(
        [
            ('client_credentials', 'Client Credentials'),
            ('authorization_code', 'Authorization Code'),
        ],
        default='client_credentials',
        required=True,
    )
    scopes = fields.Char(help='Space-separated scopes')
    redirect_uris = fields.Text()
    token_url = fields.Char(string='Token URL')
    auth_url = fields.Char(string='Authorization URL')
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [('active', 'Active'), ('inactive', 'Inactive')],
        default='active',
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='integration_id.company_id', store=True, readonly=True, index=True,
    )

    def _compute_secret_display(self):
        for rec in self:
            rec.client_secret_display = '••••••••' if rec.client_secret else ''

    def _check_manager(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            raise AccessError('Only Managers can configure OAuth.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_admin'):
            raise AccessError('Only Administrators can delete OAuth configurations.')
        return super().unlink()

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields=fields, load=load)
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            for row in result:
                if 'client_secret' in row:
                    row['client_secret'] = False
        elif not self.env.user.has_group('enterprise_integration.group_ei_admin'):
            for row in result:
                if row.get('client_secret'):
                    row['client_secret'] = '********'
        return result
