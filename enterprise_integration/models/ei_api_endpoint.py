# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EiApiEndpoint(models.Model):
    _name = 'ei.api.endpoint'
    _description = 'Open API Endpoint'
    _order = 'path, method'
    _check_company_auto = True

    name = fields.Char(required=True)
    integration_id = fields.Many2one(
        'ei.integration', required=True, ondelete='cascade', index=True,
    )
    path = fields.Char(required=True, index=True, help='Path under /ei/api/v1/...')
    method = fields.Selection(
        [
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
        ],
        required=True,
        default='GET',
        index=True,
    )
    version = fields.Char(default='v1', required=True, index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('deprecated', 'Deprecated'),
            ('restricted', 'Restricted'),
        ],
        default='inactive',
        required=True,
        index=True,
    )
    auth_type = fields.Selection(
        [
            ('api_key', 'API Key'),
            ('oauth', 'OAuth'),
            ('both', 'API Key or OAuth'),
            ('public', 'Public (not recommended)'),
        ],
        default='api_key',
        required=True,
    )
    rate_limit = fields.Integer(
        string='Rate Limit (req/min)',
        default=60,
        help='Maximum requests per minute per credential.',
    )
    permission_group_ids = fields.Many2many(
        'res.groups',
        'ei_api_endpoint_group_rel',
        'endpoint_id',
        'group_id',
        string='Permission Groups',
    )
    request_schema = fields.Text(string='Request Schema / Notes')
    response_schema = fields.Text(string='Response Schema / Notes')
    doc_notes = fields.Html(string='API Documentation')
    external_ref = fields.Char(string='External Reference', index=True)
    usage_count = fields.Integer(string='Usage Count', default=0, readonly=True)
    last_called_at = fields.Datetime(string='Last Called At', readonly=True)
    last_test_result = fields.Text(readonly=True)
    last_test_at = fields.Datetime(readonly=True)
    credential_ids = fields.One2many('ei.api.credential', 'endpoint_id', string='API Keys')
    pipeline_sync_job_id = fields.Many2one(
        'ei.sync.job',
        string='Pipeline Sync Job',
        ondelete='set null',
        index=True,
        help=(
            'Optional. When set, inbound API payloads continue through '
            'Validate → Transform → Sync → Log → Monitor using this job.'
        ),
        domain="[('integration_id', '=', integration_id)]",
    )
    company_id = fields.Many2one(
        related='integration_id.company_id', store=True, readonly=True, index=True,
    )

    _sql_constraints = [
        (
            'ei_api_endpoint_path_method_uniq',
            'unique(integration_id, path, method, version)',
            'Endpoint path+method+version must be unique per integration.',
        ),
        (
            'ei_api_endpoint_rate_limit_positive',
            'CHECK(rate_limit >= 0)',
            'Rate limit must be zero or positive.',
        ),
    ]

    @api.constrains('path')
    def _check_path(self):
        for rec in self:
            if rec.path and (rec.path.startswith('/') or ' ' in rec.path):
                raise ValidationError(
                    'API path should be relative without a leading slash (e.g. partners).'
                )

    def _validate_for_activation(self):
        self.ensure_one()
        if not self.path or not self.method:
            raise UserError('Path and method are required before activation.')
        if self.auth_type in ('api_key', 'both') and not self.credential_ids.filtered(
            lambda c: c.state == 'active'
        ):
            # Allow activation but warn via log — credentials can be added after
            self.env['ei.log'].sudo().ei_log(
                name=f'API activate without credentials {self.path}',
                category='api',
                level='warning',
                operation='api_activate',
                endpoint_id=self.id,
                integration_id=self.integration_id.id,
                response_summary='Activated without active API keys',
            )

    def action_activate(self):
        self.check_access('write')
        for rec in self:
            rec._validate_for_activation()
            rec.write({'state': 'active', 'active': True})
            self.env['ei.log'].sudo().ei_log(
                name=f'API activated {rec.method} {rec.path}',
                category='api',
                level='success',
                operation='api_activate',
                endpoint_id=rec.id,
                integration_id=rec.integration_id.id,
            )

    def action_deactivate(self):
        self.check_access('write')
        for rec in self:
            rec.write({'state': 'inactive', 'active': False})
            self.env['ei.log'].sudo().ei_log(
                name=f'API deactivated {rec.method} {rec.path}',
                category='api',
                level='warning',
                operation='api_deactivate',
                endpoint_id=rec.id,
                integration_id=rec.integration_id.id,
            )

    def action_test_endpoint(self):
        """Manager-only safe API configuration/auth test."""
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            raise AccessError('Only Managers can test API endpoints.')
        from odoo.addons.enterprise_integration.services.workflow_service import WorkflowService
        result = WorkflowService(self.env).test_api_endpoint(self)
        self.write({
            'last_test_at': fields.Datetime.now(),
            'last_test_result': str(result)[:2000],
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API Test',
                'message': result.get('message') or ('OK' if result.get('ok') else 'Failed'),
                'type': 'success' if result.get('ok') else 'danger',
                'sticky': False,
            },
        }
