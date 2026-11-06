# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.enterprise_integration.services.webhook_service import WebhookService


class EiWebhook(models.Model):
    _name = 'ei.webhook'
    _description = 'Webhook Endpoint'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True)
    integration_id = fields.Many2one(
        'ei.integration', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)
    direction = fields.Selection(
        [('incoming', 'Incoming'), ('outgoing', 'Outgoing')],
        required=True,
        default='outgoing',
        index=True,
    )
    code = fields.Char(required=True, index=True, help='Used in incoming URL /ei/webhook/<code>')
    url = fields.Char(string='Target URL', help='Required for outgoing webhooks')
    auth_type = fields.Selection(
        [
            ('none', 'None'),
            ('hmac', 'HMAC Signature'),
            ('bearer', 'Bearer Token'),
            ('api_key', 'API Key Header'),
        ],
        default='hmac',
        required=True,
    )
    secret = fields.Char(copy=False)
    secret_display = fields.Char(compute='_compute_secret_display')
    retry_max = fields.Integer(default=5)
    retry_backoff = fields.Integer(string='Backoff (seconds)', default=60)
    timeout = fields.Integer(string='Timeout (seconds)', default=30)
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [('active', 'Active'), ('inactive', 'Inactive')],
        default='inactive',
        required=True,
        index=True,
    )
    subscription_ids = fields.One2many(
        'ei.webhook.subscription', 'webhook_id', string='Subscriptions',
    )
    delivery_ids = fields.One2many('ei.webhook.delivery', 'webhook_id', string='Deliveries')
    pipeline_sync_job_id = fields.Many2one(
        'ei.sync.job',
        string='Pipeline Sync Job',
        ondelete='set null',
        index=True,
        help=(
            'Optional. When set, incoming webhook payloads continue through '
            'Validate → Transform → Sync → Log → Monitor using this job.'
        ),
        domain="[('integration_id', '=', integration_id)]",
    )
    company_id = fields.Many2one(
        related='integration_id.company_id', store=True, readonly=True, index=True,
    )

    _sql_constraints = [
        ('ei_webhook_code_uniq', 'unique(code)', 'Webhook code must be unique.'),
        ('ei_webhook_retry_max_positive', 'CHECK(retry_max >= 0)', 'Retry max must be >= 0.'),
        ('ei_webhook_timeout_positive', 'CHECK(timeout > 0)', 'Timeout must be positive.'),
    ]

    def _compute_secret_display(self):
        for rec in self:
            rec.secret_display = '••••••••' if rec.secret else ''

    @api.constrains('direction', 'url')
    def _check_outgoing_url(self):
        for rec in self:
            if rec.direction == 'outgoing' and rec.state == 'active' and not rec.url:
                raise ValidationError('Outgoing webhooks require a target URL when active.')

    def action_test_endpoint(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Webhook',
            'res_model': 'ei.connection.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_test_type': 'webhook',
                'default_webhook_id': self.id,
            },
        }

    def action_enqueue_outgoing(self):
        """Create a mock outgoing delivery for testing from the UI."""
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can enqueue webhook deliveries.')
        if self.direction != 'outgoing':
            from odoo.exceptions import UserError
            raise UserError('Only outgoing webhooks can enqueue deliveries.')
        from odoo.addons.enterprise_integration.services.workflow_service import WorkflowService
        delivery = WorkflowService(self.env).enqueue_webhook(
            self, {'event': 'manual_test', 'source': 'ui'}, event_type='manual_test',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Webhook Queued',
                'message': f'Delivery {delivery.id} queued (MOCK). Correlation: {delivery.correlation_id}',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_activate(self):
        self.check_access('write')
        for rec in self:
            if rec.direction == 'outgoing' and not rec.url:
                from odoo.exceptions import UserError
                raise UserError('Outgoing webhooks require a target URL before activation.')
            rec.write({'state': 'active', 'active': True})
            self.env['ei.log'].sudo().ei_log(
                name=f'Webhook activated {rec.name}',
                category='webhook',
                level='success',
                operation='webhook_activate',
                webhook_id=rec.id,
                integration_id=rec.integration_id.id,
            )

    def action_deactivate(self):
        self.check_access('write')
        for rec in self:
            rec.write({'state': 'inactive', 'active': False})
            self.env['ei.log'].sudo().ei_log(
                name=f'Webhook deactivated {rec.name}',
                category='webhook',
                level='warning',
                operation='webhook_deactivate',
                webhook_id=rec.id,
                integration_id=rec.integration_id.id,
            )

    @api.model
    def _cron_process_outgoing_deliveries(self):
        return WebhookService(self.env).process_pending_outgoing()
