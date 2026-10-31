# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request

from odoo.addons.enterprise_integration.services.api_service import ApiService


class EiApiController(http.Controller):

    @http.route(
        ['/ei/api/v1/<path:path>'],
        type='http',
        auth='public',
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        csrf=False,
        save_session=False,
    )
    def ei_api_v1(self, path, **kwargs):
        method = request.httprequest.method
        endpoint = request.env['ei.api.endpoint'].sudo().search([
            ('path', '=', path),
            ('method', '=', method),
            ('version', '=', 'v1'),
            ('state', 'in', ('active', 'restricted')),
        ], limit=1)
        if not endpoint:
            return request.make_json_response(
                {'ok': False, 'error': 'not_found', 'message': 'Endpoint not found'},
                status=404,
            )
        api_key = request.httprequest.headers.get('X-API-Key')
        # Never accept API keys via query string — secrets must not appear in URLs/logs.
        idempotency_key = request.httprequest.headers.get('Idempotency-Key')
        payload = {}
        if method in ('POST', 'PUT', 'PATCH'):
            try:
                raw = request.httprequest.get_data(as_text=True) or '{}'
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return request.make_json_response(
                    {'ok': False, 'error': 'invalid_json'},
                    status=400,
                )
        result = ApiService(request.env).handle_request(
            endpoint, method, payload=payload, api_key=api_key, idempotency_key=idempotency_key,
        )
        status = 200 if result.get('ok') else (
            401 if result.get('error') == 'unauthorized' else
            403 if result.get('error') == 'forbidden' else
            429 if result.get('error') == 'rate_limited' else 400
        )
        return request.make_json_response(result, status=status)
