# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EiConnector(models.Model):
    _name = 'ei.connector'
    _description = 'Enterprise Connector'
    _order = 'category, name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    integration_id = fields.Many2one(
        'ei.integration', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)
    category = fields.Selection(
        [
            ('erp', 'ERP'),
            ('crm', 'CRM'),
            ('bank', 'Banking'),
            ('whatsapp', 'WhatsApp'),
            ('legacy', 'Legacy'),
        ],
        required=True,
        index=True,
    )
    provider_code = fields.Char(required=True, index=True, help='Logical provider code, e.g. mock_erp')
    adapter_key = fields.Char(
        required=True,
        default='mock',
        index=True,
        help='Registry key for connector adapter (mock/erp/crm/bank/whatsapp/legacy).',
    )
    direction = fields.Selection(
        [
            ('inbound', 'Inbound'),
            ('outbound', 'Outbound'),
            ('bidirectional', 'Bidirectional'),
        ],
        default='bidirectional',
        required=True,
    )
    version = fields.Char(default='1.0')
    base_url = fields.Char(string='Connection Base URL')
    auth_method = fields.Selection(
        [
            ('none', 'None'),
            ('api_key', 'API Key'),
            ('oauth', 'OAuth'),
            ('basic', 'Basic'),
            ('certificate', 'Certificate'),
            ('custom', 'Custom'),
        ],
        default='api_key',
        required=True,
    )
    state = fields.Selection(
        [
            ('pending_configuration', 'Pending Configuration'),
            ('connecting', 'Connecting'),
            ('connected', 'Connected'),
            ('disconnected', 'Disconnected'),
            ('error', 'Error'),
            ('disabled', 'Disabled'),
        ],
        default='pending_configuration',
        required=True,
        index=True,
    )
    health_state = fields.Selection(
        [
            ('unknown', 'Unknown'),
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='unknown',
        required=True,
        index=True,
    )
    sync_frequency = fields.Selection(
        [
            ('manual', 'Manual'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('realtime', 'Real-time / Event'),
        ],
        default='manual',
    )
    last_health_at = fields.Datetime()
    last_error = fields.Text()
    external_ref = fields.Char(string='External Reference', index=True)
    site_ref = fields.Char(string='Site / Property Reference', index=True)
    is_mock = fields.Boolean(
        string='Mock / Stub Connector',
        default=True,
        help='True when using mock adapters. Not a live external connection.',
    )
    settings_json = fields.Text(string='Connector Settings (JSON)')
    credential_ids = fields.One2many('ei.connector.credential', 'connector_id', string='Credentials')
    mapping_ids = fields.One2many('ei.connector.mapping', 'connector_id', string='Field Mappings')
    company_id = fields.Many2one(
        related='integration_id.company_id', store=True, readonly=True, index=True,
    )

    _sql_constraints = [
        (
            'ei_connector_code_integration_uniq',
            'unique(integration_id, provider_code, category)',
            'Provider code must be unique per integration and category.',
        ),
    ]

    @api.constrains('adapter_key', 'is_mock')
    def _check_mock_consistency(self):
        for rec in self:
            if rec.adapter_key == 'mock' and not rec.is_mock:
                raise ValidationError('adapter_key "mock" requires is_mock to be True.')

    @api.constrains('base_url')
    def _check_base_url(self):
        for rec in self:
            if rec.base_url and not (
                rec.base_url.startswith('http://') or rec.base_url.startswith('https://')
            ):
                raise ValidationError('Connection Base URL must start with http:// or https://.')

    def action_test_connection(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Connection',
            'res_model': 'ei.connection.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_test_type': 'connector',
                'default_connector_id': self.id,
            },
        }

    def action_enable(self):
        self.check_access('write')
        for rec in self:
            rec.write({
                'state': 'connected' if rec.is_mock else 'connecting',
                'active': True,
            })
            self.env['ei.log'].sudo().ei_log(
                name=f'Connector activated {rec.name}',
                category='connector',
                level='success',
                operation='connector_activate',
                connector_id=rec.id,
                integration_id=rec.integration_id.id,
                response_summary='MOCK / DEMO activate' if rec.is_mock else 'activate',
            )

    def action_disable(self):
        self.check_access('write')
        for rec in self:
            rec.write({'state': 'disabled', 'active': False})
            self.env['ei.log'].sudo().ei_log(
                name=f'Connector deactivated {rec.name}',
                category='connector',
                level='warning',
                operation='connector_deactivate',
                connector_id=rec.id,
                integration_id=rec.integration_id.id,
                response_summary='MOCK / DEMO deactivate' if rec.is_mock else 'deactivate',
            )

    def action_reconnect(self):
        self.check_access('write')
        self.write({'state': 'connecting'})
        from odoo.addons.enterprise_integration.services.health_service import HealthService
        health = HealthService(self.env)
        for rec in self:
            result = health.check_connector(rec)
            if result.get('ok') and rec.is_mock:
                rec.write({
                    'state': 'connected',
                    'health_state': 'healthy',
                    'last_health_at': fields.Datetime.now(),
                    'last_error': False,
                })
            elif not result.get('ok'):
                rec.write({'state': 'error'})
            self.env['ei.log'].sudo().ei_log(
                name=f'Reconnect {rec.name}',
                category='connector',
                level='success' if result.get('ok') else 'failed',
                operation='connector_reconnect',
                connector_id=rec.id,
                integration_id=rec.integration_id.id,
                response_summary='MOCK reconnect' if rec.is_mock else 'reconnect',
                retryable=not result.get('ok'),
            )

    def action_health_check(self):
        self.check_access('write')
        from odoo.addons.enterprise_integration.services.health_service import HealthService
        service = HealthService(self.env)
        for rec in self:
            service.check_connector(rec)
        return True

    @api.model
    def _cron_health_checks(self):
        from odoo.addons.enterprise_integration.services.health_service import HealthService
        HealthService(self.env).check_all_active()
        return True
