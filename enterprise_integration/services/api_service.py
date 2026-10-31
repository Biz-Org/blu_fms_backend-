# -*- coding: utf-8 -*-
import uuid

from odoo import fields

from .exceptions import (
    EiAuthenticationError,
    EiAuthorizationError,
    EiRateLimitError,
    EiValidationError,
)
from .idempotency import IdempotencyService, RateLimitService
from .logging_service import LoggingService


class ApiService:
    """Open API service layer — never exposes credentials."""

    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)
        self.idempotency = IdempotencyService(env)
        self.rate_limit = RateLimitService(env)

    def authenticate_api_key(self, api_key):
        if not api_key:
            return self.env['ei.api.credential'].browse()
        cred = self.env['ei.api.credential'].sudo().verify_key(api_key)
        if cred:
            cred.sudo().write({'last_used_at': fields.Datetime.now()})
        return cred

    def authorize_endpoint(self, endpoint, user=None):
        if endpoint.state not in ('active', 'restricted'):
            return False
        if not endpoint.permission_group_ids:
            return True
        user = user or self.env.user
        return bool(user.groups_id & endpoint.permission_group_ids)

    def handle_request(self, endpoint, method, payload=None, api_key=None, idempotency_key=None):
        correlation_id = str(uuid.uuid4())
        logger = self.logs.with_correlation(correlation_id)

        if idempotency_key and self.idempotency.seen_log_idempotency(idempotency_key):
            existing = self.env['ei.log'].sudo().search([
                ('category', '=', 'api'),
                ('request_summary', '=', f'idempotency:{idempotency_key}'),
            ], limit=1)
            return {
                'ok': True,
                'idempotent_replay': True,
                'correlation_id': existing.correlation_id or correlation_id,
            }

        try:
            cred = False
            if endpoint.auth_type in ('api_key', 'both'):
                cred = self.authenticate_api_key(api_key)
                if not cred:
                    raise EiAuthenticationError('Invalid or missing API key')
            elif endpoint.auth_type == 'oauth':
                # Extensible: OAuth validation hook (not fully implemented without provider)
                if not api_key:
                    raise EiAuthenticationError('OAuth bearer token required')
            elif endpoint.auth_type == 'public':
                cred = False
            else:
                cred = self.authenticate_api_key(api_key)
                if not cred:
                    raise EiAuthenticationError('Authentication required')

            if not self.rate_limit.allow(endpoint, cred):
                raise EiRateLimitError('Rate limit exceeded')

            if not self.authorize_endpoint(endpoint):
                raise EiAuthorizationError('Forbidden for this endpoint')

            if method in ('POST', 'PUT', 'PATCH') and payload is not None and not isinstance(payload, dict):
                raise EiValidationError('JSON object payload required')

            result = {
                'ok': True,
                'path': endpoint.path,
                'method': method,
                'version': endpoint.version,
                'correlation_id': correlation_id,
                'data': payload or {},
                'mode': 'service',
            }
            endpoint.sudo().write({
                'usage_count': (endpoint.usage_count or 0) + 1,
                'last_called_at': fields.Datetime.now(),
            })
            logger.log(
                name=f'API {method} {endpoint.path}',
                category='api',
                level='success',
                operation='api_request',
                endpoint_id=endpoint.id,
                integration_id=endpoint.integration_id.id,
                request_summary=f'idempotency:{idempotency_key}' if idempotency_key else 'ok',
                response_summary='accepted',
            )
            # Continue canonical pipeline when write methods carry a payload
            if method in ('POST', 'PUT', 'PATCH') and payload is not None:
                from .workflow_service import WorkflowService
                pipeline = WorkflowService(self.env).process_inbound(
                    payload,
                    correlation_id=correlation_id,
                    source='api',
                    integration=endpoint.integration_id,
                    endpoint=endpoint,
                )
                result['pipeline'] = pipeline
                if not pipeline.get('ok'):
                    result['ok'] = False
                    result['error'] = pipeline.get('error') or 'pipeline_failed'
                    result['message'] = pipeline.get('message') or 'Pipeline failed'
            return result

        except (EiAuthenticationError, EiAuthorizationError, EiRateLimitError, EiValidationError) as exc:
            level = 'rejected'
            error_code = {
                'AuthenticationError': 'unauthorized',
                'AuthorizationError': 'forbidden',
                'RateLimitError': 'rate_limited',
                'ValidationError': 'invalid_request',
            }.get(exc.error_class, 'error')
            logger.log(
                name=f'API {method} {endpoint.path} failed',
                category='api',
                level=level,
                operation='api_request',
                endpoint_id=endpoint.id,
                integration_id=endpoint.integration_id.id,
                error_class=exc.error_class,
                error_message=str(exc),
                retryable=exc.retryable,
            )
            return {
                'ok': False,
                'error': error_code,
                'message': str(exc),
                'correlation_id': correlation_id,
            }
