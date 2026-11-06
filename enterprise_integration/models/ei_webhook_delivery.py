# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EiWebhookDelivery(models.Model):
    _name = 'ei.webhook.delivery'
    _description = 'Webhook Delivery Attempt'
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    webhook_id = fields.Many2one('ei.webhook', required=True, ondelete='cascade', index=True)
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('retrying', 'Retrying'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    attempt = fields.Integer(default=0)
    http_status = fields.Integer()
    correlation_id = fields.Char(index=True)
    idempotency_key = fields.Char(index=True)
    external_ref = fields.Char(string='External Reference', index=True)
    payload_summary = fields.Text()
    response_summary = fields.Text()
    error_message = fields.Text()
    next_retry_at = fields.Datetime(index=True)
    delivered_at = fields.Datetime()
    company_id = fields.Many2one(
        related='webhook_id.company_id', store=True, readonly=True, index=True,
    )

    @api.depends('webhook_id.name', 'status', 'attempt')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.webhook_id.name or "Webhook"} [{rec.status}] #{rec.attempt}'

    def action_retry(self):
        self.check_access('write')
        from odoo.addons.enterprise_integration.services.webhook_service import WebhookService
        service = WebhookService(self.env)
        for rec in self:
            if rec.attempt >= (rec.webhook_id.retry_max or 5):
                rec.write({'status': 'failed', 'error_message': 'Maximum retry attempts reached'})
                self.env['ei.log'].sudo().ei_log(
                    category='webhook',
                    level='failed',
                    name=f'Webhook retry exhausted {rec.id}',
                    operation='webhook_retry_exhausted',
                    integration_id=rec.webhook_id.integration_id.id,
                    webhook_id=rec.webhook_id.id,
                    correlation_id=rec.correlation_id,
                    retryable=False,
                )
                continue
            rec.write({'status': 'retrying', 'next_retry_at': fields.Datetime.now()})
            self.env['ei.log'].sudo().ei_log(
                category='webhook',
                level='retrying',
                name=f'Retry webhook delivery {rec.id}',
                operation='webhook_retry',
                integration_id=rec.webhook_id.integration_id.id,
                webhook_id=rec.webhook_id.id,
                correlation_id=rec.correlation_id,
                retryable=True,
            )
            service._deliver_one(rec)
        return True
