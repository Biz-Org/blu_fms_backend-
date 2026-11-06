# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request

from odoo.addons.enterprise_integration.services.exceptions import (
    EiAuthenticationError,
    EiValidationError,
)
from odoo.addons.enterprise_integration.services.webhook_service import WebhookService


class EiWebhookController(http.Controller):

    @http.route(
        ['/ei/webhook/<string:code>'],
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def ei_webhook_incoming(self, code, **kwargs):
        webhook = request.env['ei.webhook'].sudo().search([
            ('code', '=', code),
            ('direction', '=', 'incoming'),
            ('state', '=', 'active'),
        ], limit=1)
        if not webhook:
            return request.make_json_response(
                {'ok': False, 'error': 'not_found'},
                status=404,
            )
        try:
            raw = request.httprequest.get_data(as_text=True) or '{}'
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return request.make_json_response({'ok': False, 'error': 'invalid_json'}, status=400)

        auth_error = self._authenticate_incoming(webhook, request)
        if auth_error:
            return auth_error

        idempotency_key = request.httprequest.headers.get('Idempotency-Key')
        try:
            result = WebhookService(request.env).receive_incoming(
                webhook, payload, idempotency_key=idempotency_key,
            )
            return request.make_json_response(result, status=200)
        except EiAuthenticationError:
            return request.make_json_response(
                {'ok': False, 'error': 'unauthorized'}, status=401,
            )
        except EiValidationError as exc:
            return request.make_json_response(
                {'ok': False, 'error': 'invalid_request', 'message': str(exc)}, status=400,
            )

    @staticmethod
    def _authenticate_incoming(webhook, req):
        """Validate incoming webhook auth without echoing secrets in responses."""
        auth_type = webhook.auth_type or 'none'
        if auth_type == 'none':
            return None
        if auth_type == 'bearer':
            auth = req.httprequest.headers.get('Authorization', '')
            if not webhook.secret or auth != f'Bearer {webhook.secret}':
                return req.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)
            return None
        if auth_type == 'api_key':
            provided = (
                req.httprequest.headers.get('X-API-Key')
                or req.httprequest.headers.get('X-Webhook-Key')
            )
            if not webhook.secret or provided != webhook.secret:
                return req.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)
            return None
        if auth_type == 'hmac':
            signature = (
                req.httprequest.headers.get('X-Hub-Signature-256')
                or req.httprequest.headers.get('X-Signature')
                or req.httprequest.headers.get('X-EI-Signature')
            )
            if not webhook.secret or not signature:
                return req.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)
            # MOCK/DEMO: accept plain secret or sha256=<secret>; never echo secret values
            allowed = {webhook.secret, f'sha256={webhook.secret}'}
            if signature not in allowed:
                return req.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)
            return None
        return req.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)
