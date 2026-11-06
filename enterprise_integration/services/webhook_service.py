# -*- coding: utf-8 -*-
import json
import uuid

from odoo import fields

from .exceptions import EiValidationError
from .idempotency import IdempotencyService
from .logging_service import LoggingService
from .retry_service import RetryService


class WebhookService:
    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)
        self.idempotency = IdempotencyService(env)

    def receive_incoming(self, webhook, payload, idempotency_key=None, headers=None):
        correlation_id = str(uuid.uuid4())
        logger = self.logs.with_correlation(correlation_id)

        if webhook.state != 'active':
            raise EiValidationError('Webhook is not active')

        if idempotency_key and self.idempotency.seen(
            'ei.webhook.delivery', 'idempotency_key', idempotency_key,
        ):
            existing = self.env['ei.webhook.delivery'].sudo().search([
                ('idempotency_key', '=', idempotency_key),
            ], limit=1)
            return {
                'ok': True,
                'idempotent_replay': True,
                'delivery_id': existing.id,
                'correlation_id': existing.correlation_id or correlation_id,
            }

        if not isinstance(payload, dict):
            raise EiValidationError('Webhook payload must be a JSON object')

        delivery = self.env['ei.webhook.delivery'].sudo().create({
            'webhook_id': webhook.id,
            'status': 'delivered',
            'attempt': 1,
            'http_status': 200,
            'correlation_id': correlation_id,
            'idempotency_key': idempotency_key or self.idempotency.new_key(),
            'payload_summary': self._safe_summary(payload),
            'response_summary': 'accepted',
            'delivered_at': fields.Datetime.now(),
        })
        logger.log(
            name=f'Incoming webhook {webhook.code}',
            category='webhook',
            level='success',
            operation='webhook_incoming',
            webhook_id=webhook.id,
            integration_id=webhook.integration_id.id,
            request_summary=delivery.payload_summary,
        )
        from .workflow_service import WorkflowService
        pipeline = WorkflowService(self.env).process_inbound(
            payload,
            correlation_id=correlation_id,
            source='webhook',
            integration=webhook.integration_id,
            webhook=webhook,
        )
        return {
            'ok': bool(pipeline.get('ok')),
            'delivery_id': delivery.id,
            'correlation_id': correlation_id,
            'pipeline': pipeline,
            'error': pipeline.get('error'),
            'message': pipeline.get('message'),
        }

    def enqueue_outgoing(self, webhook, payload, event_type=None):
        correlation_id = str(uuid.uuid4())
        delivery = self.env['ei.webhook.delivery'].sudo().create({
            'webhook_id': webhook.id,
            'status': 'pending',
            'attempt': 0,
            'correlation_id': correlation_id,
            'idempotency_key': self.idempotency.new_key(),
            'payload_summary': self._safe_summary(payload),
            'external_ref': event_type,
            'next_retry_at': fields.Datetime.now(),
        })
        self.logs.log(
            name=f'Enqueue outgoing webhook {webhook.name}',
            category='webhook',
            level='warning',
            operation='webhook_enqueue',
            webhook_id=webhook.id,
            integration_id=webhook.integration_id.id,
            correlation_id=correlation_id,
            retryable=True,
        )
        return delivery

    def process_pending_outgoing(self):
        """ir.cron worker — mock HTTP delivery (no live calls)."""
        now = fields.Datetime.now()
        pending = self.env['ei.webhook.delivery'].sudo().search([
            ('status', 'in', ('pending', 'retrying')),
            '|', ('next_retry_at', '=', False), ('next_retry_at', '<=', now),
        ], limit=50)
        for delivery in pending:
            self._deliver_one(delivery)
        return True

    def _deliver_one(self, delivery):
        webhook = delivery.webhook_id
        attempt = (delivery.attempt or 0) + 1
        retry = RetryService(
            max_attempts=webhook.retry_max or 5,
            backoff_seconds=webhook.retry_backoff or 60,
        )
        fail = (webhook.url or '').rstrip('/').endswith('/fail')
        try:
            if fail:
                raise EiValidationError('Mock outbound delivery failure')
            delivery.write({
                'status': 'delivered',
                'attempt': attempt,
                'http_status': 200,
                'response_summary': 'mock_delivered',
                'error_message': False,
                'delivered_at': fields.Datetime.now(),
                'next_retry_at': False,
            })
            self.logs.log(
                name=f'Mock delivered webhook {webhook.name}',
                category='webhook',
                level='success',
                operation='webhook_deliver',
                webhook_id=webhook.id,
                integration_id=webhook.integration_id.id,
                correlation_id=delivery.correlation_id,
                response_summary='mock_delivered',
            )
        except Exception as exc:  # noqa: BLE001
            plan = retry.plan(attempt, retryable=True)
            vals = {
                'attempt': attempt,
                'http_status': 500,
                'error_message': str(exc),
                'status': plan['status'],
            }
            if plan['status'] == 'retrying' and plan.get('next_retry_at'):
                vals['next_retry_at'] = plan['next_retry_at']
            delivery.write(vals)
            self.logs.log(
                name=f'Webhook delivery failed {webhook.name}',
                category='webhook',
                level='retrying' if plan['status'] == 'retrying' else 'failed',
                operation='webhook_deliver',
                webhook_id=webhook.id,
                integration_id=webhook.integration_id.id,
                correlation_id=delivery.correlation_id,
                error_class=type(exc).__name__,
                error_message=str(exc),
                retryable=plan['status'] == 'retrying',
            )

    @staticmethod
    def _safe_summary(payload):
        """Serialize payload for storage without retaining obvious secrets."""
        if isinstance(payload, dict):
            scrubbed = {}
            for key, value in payload.items():
                lowered = str(key).lower()
                if any(tok in lowered for tok in (
                    'password', 'secret', 'token', 'api_key', 'apikey',
                    'authorization', 'private_key', 'client_secret',
                    'access_token', 'refresh_token',
                )):
                    scrubbed[key] = '[redacted]'
                else:
                    scrubbed[key] = value
            payload = scrubbed
        try:
            text = json.dumps(payload)[:2000]
        except (TypeError, ValueError):
            text = str(payload)[:2000]
        if not isinstance(payload, dict):
            lowered = text.lower()
            for tok in ('password', 'api_key', 'access_token', 'client_secret', 'private_key'):
                if tok in lowered:
                    return '[scrubbed: potentially sensitive content omitted]'
        return text

