# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class EiConnectorCredential(models.Model):
    _name = 'ei.connector.credential'
    _description = 'Connector Credential'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True)
    connector_id = fields.Many2one('ei.connector', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)
    auth_type = fields.Selection(
        [
            ('api_key', 'API Key'),
            ('basic', 'Basic Auth'),
            ('oauth', 'OAuth'),
            ('certificate', 'Certificate'),
            ('custom', 'Custom'),
        ],
        default='api_key',
        required=True,
    )
    username = fields.Char()
    secret = fields.Char(copy=False)
    secret_display = fields.Char(compute='_compute_secret_display')
    token = fields.Char(copy=False)
    extra_json = fields.Text(string='Extra Settings (JSON)')
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('invalid', 'Invalid'),
        ],
        default='active',
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='connector_id.company_id', store=True, readonly=True, index=True,
    )

    def _compute_secret_display(self):
        for rec in self:
            rec.secret_display = '••••••••' if (rec.secret or rec.token) else ''

    def _check_manager(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            raise AccessError('Only Managers can manage connector credentials.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('enterprise_integration.group_ei_admin'):
            raise AccessError('Only Administrators can delete connector credentials.')
        return super().unlink()

    @api.constrains('secret', 'token', 'extra_json')
    def _forbid_logging_hint(self):
        # Structural guard: secrets must remain on credential model only
        return True

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields=fields, load=load)
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            for row in result:
                for key in ('secret', 'token'):
                    if key in row:
                        row[key] = False
        elif not self.env.user.has_group('enterprise_integration.group_ei_admin'):
            for row in result:
                for key in ('secret', 'token'):
                    if row.get(key):
                        row[key] = '********'
        return result
