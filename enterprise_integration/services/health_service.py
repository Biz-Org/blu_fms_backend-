# -*- coding: utf-8 -*-
"""Connector health checks via adapters + ei.connector / ei.log updates."""
from odoo import fields

from .connectors.registry import get_adapter
from .logging_service import LoggingService


class HealthService:
    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)

    def check_connector(self, connector, correlation_id=None):
        adapter = get_adapter(self.env, connector)
        result = adapter.health_check()
        vals = {
            'last_health_at': fields.Datetime.now(),
            'health_state': 'healthy' if result.get('ok') else 'down',
        }
        if result.get('ok'):
            vals['last_error'] = False
            if connector.state in ('connecting', 'pending_configuration', 'error', 'disconnected'):
                if connector.is_mock:
                    vals['state'] = 'connected'
        else:
            err = (result.get('error') or {}).get('message') or result.get('message')
            vals['last_error'] = err
            vals['state'] = 'error'
        connector.sudo().write(vals)

        # Reflect on integration hub
        if connector.integration_id:
            connector.integration_id.sudo().write({
                'health_state': vals['health_state'],
                'last_health_at': vals['last_health_at'],
            })

        self.logs.log(
            name=f'Health check {connector.name}',
            category='connector',
            level='success' if result.get('ok') else 'failed',
            operation='health_check',
            integration_id=connector.integration_id.id,
            connector_id=connector.id,
            correlation_id=correlation_id,
            duration_ms=result.get('response_time_ms'),
            response_summary=result.get('message') or str(result.get('health')),
            error_class=(result.get('error') or {}).get('error_class'),
            error_message=(result.get('error') or {}).get('message'),
            retryable=not result.get('ok'),
        )
        return result

    def check_all_active(self):
        connectors = self.env['ei.connector'].sudo().search([
            ('active', '=', True),
            ('state', 'not in', ('disabled',)),
        ])
        results = []
        for connector in connectors:
            results.append(self.check_connector(connector))
        return results
