# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EiIntegration(models.Model):
    _name = 'ei.integration'
    _description = 'Enterprise Integration Instance'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    integration_type = fields.Selection(
        [
            ('api', 'Open API'),
            ('webhook', 'Webhook'),
            ('connector', 'Connector'),
            ('hybrid', 'Hybrid'),
        ],
        string='Integration Type',
        default='hybrid',
        required=True,
        index=True,
    )
    provider_system = fields.Char(
        string='Provider / System',
        help='External system name (e.g. Mock ERP, Legacy Finance).',
        index=True,
    )
    primary_connector_id = fields.Many2one(
        'ei.connector',
        string='Primary Connector',
        ondelete='set null',
        index=True,
        help='Optional primary connector reference for this integration.',
    )
    environment = fields.Selection(
        [
            ('development', 'Development'),
            ('staging', 'Staging'),
            ('production', 'Production'),
        ],
        default='development',
        required=True,
        index=True,
    )
    base_url = fields.Char(string='Base URL')
    auth_method = fields.Selection(
        [
            ('none', 'None'),
            ('api_key', 'API Key'),
            ('oauth', 'OAuth'),
            ('basic', 'Basic'),
            ('certificate', 'Certificate'),
            ('custom', 'Custom'),
        ],
        string='Authentication Method',
        default='api_key',
        required=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('paused', 'Paused'),
        ],
        default='draft',
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
    last_health_at = fields.Datetime(string='Last Health Check')
    external_ref = fields.Char(string='External Reference', index=True)
    site_ref = fields.Char(
        string='Site / Property Reference',
        help='Future-compatible site/property reference. No Property module dependency.',
        index=True,
    )
    company_id = fields.Many2one('res.company', string='Company', index=True)

    endpoint_ids = fields.One2many('ei.api.endpoint', 'integration_id', string='API Endpoints')
    oauth_config_ids = fields.One2many('ei.api.oauth.config', 'integration_id', string='OAuth Configurations')
    webhook_ids = fields.One2many('ei.webhook', 'integration_id', string='Webhooks')
    connector_ids = fields.One2many('ei.connector', 'integration_id', string='Connectors')
    sync_job_ids = fields.One2many('ei.sync.job', 'integration_id', string='Sync Jobs')
    log_ids = fields.One2many('ei.log', 'integration_id', string='Logs')

    endpoint_count = fields.Integer(compute='_compute_counts')
    webhook_count = fields.Integer(compute='_compute_counts')
    connector_count = fields.Integer(compute='_compute_counts')
    sync_job_count = fields.Integer(compute='_compute_counts')
    connected_connector_count = fields.Integer(compute='_compute_counts')
    failed_log_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('ei_integration_code_uniq', 'unique(code)', 'Integration code must be unique.'),
    ]

    @api.depends(
        'endpoint_ids', 'webhook_ids', 'connector_ids', 'sync_job_ids',
        'connector_ids.state', 'log_ids.level',
    )
    def _compute_counts(self):
        for rec in self:
            rec.endpoint_count = len(rec.endpoint_ids)
            rec.webhook_count = len(rec.webhook_ids)
            rec.connector_count = len(rec.connector_ids)
            rec.sync_job_count = len(rec.sync_job_ids)
            rec.connected_connector_count = len(
                rec.connector_ids.filtered(lambda c: c.state == 'connected')
            )
            rec.failed_log_count = len(
                rec.log_ids.filtered(lambda l: l.level in ('failed', 'timeout', 'rejected'))
            )

    @api.constrains('base_url')
    def _check_base_url(self):
        for rec in self:
            if rec.base_url and not (
                rec.base_url.startswith('http://') or rec.base_url.startswith('https://')
            ):
                raise ValidationError('Base URL must start with http:// or https://.')

    @api.constrains('primary_connector_id', 'connector_ids')
    def _check_primary_connector(self):
        for rec in self:
            if rec.primary_connector_id and rec.primary_connector_id.integration_id != rec:
                raise ValidationError('Primary connector must belong to this integration.')

    def action_activate(self):
        self.check_access('write')
        self.write({'state': 'active', 'active': True})

    def action_deactivate(self):
        self.check_access('write')
        self.write({'state': 'inactive', 'active': False})

    def action_pause(self):
        self.check_access('write')
        self.write({'state': 'paused'})

    def action_mark_healthy(self):
        self.check_access('write')
        self.write({'health_state': 'healthy', 'last_health_at': fields.Datetime.now()})
