# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EiLog(models.Model):
    _name = 'ei.log'
    _description = 'Integration Log'
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    category = fields.Selection(
        [
            ('api', 'API'),
            ('webhook', 'Webhook'),
            ('connector', 'Connector'),
            ('sync', 'Synchronization'),
            ('master_data', 'Master Data'),
            ('system', 'System'),
        ],
        required=True,
        index=True,
    )
    level = fields.Selection(
        [
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('warning', 'Warning'),
            ('retrying', 'Retrying'),
            ('timeout', 'Timeout'),
            ('rejected', 'Rejected'),
        ],
        required=True,
        index=True,
    )
    operation = fields.Char(string='Operation', index=True)
    source_system = fields.Char(string='Source')
    destination_system = fields.Char(string='Destination')
    status = fields.Char(
        string='Status',
        compute='_compute_status',
        store=True,
        index=True,
    )
    correlation_id = fields.Char(index=True)
    external_ref = fields.Char(string='External Reference', index=True)
    duration_ms = fields.Integer(string='Duration / Response Time (ms)')
    bytes_transferred = fields.Integer()
    request_summary = fields.Text()
    response_summary = fields.Text()
    error_message = fields.Text()
    error_class = fields.Char()
    retryable = fields.Boolean(default=False, index=True)
    integration_id = fields.Many2one('ei.integration', ondelete='set null', index=True)
    endpoint_id = fields.Many2one('ei.api.endpoint', ondelete='set null', index=True)
    webhook_id = fields.Many2one('ei.webhook', ondelete='set null', index=True)
    connector_id = fields.Many2one('ei.connector', ondelete='set null', index=True)
    sync_run_id = fields.Many2one('ei.sync.run', ondelete='set null', index=True)
    master_mapping_id = fields.Many2one('ei.master.mapping', ondelete='set null', index=True)
    company_id = fields.Many2one('res.company', index=True)

    SECRET_TOKENS = (
        'password', 'secret', 'token', 'authorization', 'api_key', 'apikey',
        'api-key', 'client_secret', 'private_key', 'access_token', 'refresh_token',
        'bearer ',
    )

    @api.depends('level')
    def _compute_status(self):
        for rec in self:
            rec.status = rec.level

    @api.model
    def ei_log(self, **kwargs):
        """Safe logging entrypoint — never store credentials/secrets."""
        scrub_keys = (
            'request_summary', 'response_summary', 'name', 'error_message',
            'operation', 'source_system', 'destination_system',
        )
        for key in scrub_keys:
            if kwargs.get(key):
                kwargs[key] = self._scrub(kwargs[key])
        # Hard-drop any accidental secret kwargs
        for banned in ('password', 'secret', 'token', 'client_secret', 'api_key', 'private_key'):
            kwargs.pop(banned, None)
        return self.create(kwargs)

    @api.model
    def _scrub(self, text):
        if not text:
            return text
        lowered = str(text).lower()
        if any(token in lowered for token in self.SECRET_TOKENS):
            return '[scrubbed: potentially sensitive content omitted]'
        return text

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for key in ('request_summary', 'response_summary', 'error_message', 'name'):
                if vals.get(key):
                    vals[key] = self._scrub(vals[key])
            for banned in ('password', 'secret', 'token', 'client_secret', 'api_key', 'private_key'):
                vals.pop(banned, None)
        return super().create(vals_list)

    def action_retry(self):
        self.check_access('write')
        for rec in self.filtered('retryable'):
            if rec.sync_run_id:
                rec.sync_run_id.action_retry()
            elif rec.webhook_id:
                deliveries = self.env['ei.webhook.delivery'].search([
                    ('webhook_id', '=', rec.webhook_id.id),
                    ('status', 'in', ('failed', 'retrying')),
                ], limit=1)
                deliveries.action_retry()
        return True

    def action_export_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Logs',
            'res_model': 'ei.log.export.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
