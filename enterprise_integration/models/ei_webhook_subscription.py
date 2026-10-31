# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EiWebhookSubscription(models.Model):
    _name = 'ei.webhook.subscription'
    _description = 'Webhook Event Subscription'
    _order = 'event_type'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    webhook_id = fields.Many2one('ei.webhook', required=True, ondelete='cascade', index=True)
    event_type = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    payload_template = fields.Text(
        help='Optional payload template. Keep free of secrets.',
    )
    filter_expr = fields.Char(string='Filter Expression')
    external_ref = fields.Char(string='External Reference', index=True)
    company_id = fields.Many2one(
        related='webhook_id.company_id', store=True, readonly=True, index=True,
    )

    _sql_constraints = [
        (
            'ei_webhook_subscription_event_uniq',
            'unique(webhook_id, event_type)',
            'Event type must be unique per webhook.',
        ),
    ]

    @api.depends('webhook_id.name', 'event_type')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.webhook_id.name or ""} / {rec.event_type or ""}'

    @api.constrains('payload_template')
    def _check_payload_no_secrets(self):
        tokens = ('password', 'client_secret', 'private_key', 'api_key')
        for rec in self:
            text = (rec.payload_template or '').lower()
            if any(t in text for t in tokens):
                raise ValidationError(
                    'Payload template must not contain secret-like placeholders or values.'
                )
