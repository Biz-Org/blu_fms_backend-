# -*- coding: utf-8 -*-
"""Deterministic mock/stub connector — NOT a live external connection."""
from .base import BaseConnectorAdapter
from ..exceptions import EiDuplicateError


class MockAdapter(BaseConnectorAdapter):
    """
    Development/test mock adapter.

    Supported scenarios (connector.settings_json.mock_scenario or scenario=):
      success | auth_failure | timeout | connection_failure |
      server_error | invalid_response | empty | duplicate_event
    """

    key = 'mock'
    category = 'mock'
    is_mock = True

    def authenticate(self):
        self._apply_scenario()
        return {'ok': True, 'mode': 'mock', 'message': 'Mock authenticated'}

    def test_connection(self):
        scenario = self._apply_scenario()
        if scenario in ('failed_connection', 'connection_failure'):
            return {'ok': False, 'mode': 'mock', 'message': 'Mock connection failed'}
        return {
            'ok': True,
            'mode': 'mock',
            'message': 'Mock connection successful (stub — not live).',
        }

    def fetch(self, entity, params=None):
        scenario = self._apply_scenario()
        if scenario == 'empty':
            return {'ok': True, 'mode': 'mock', 'entity': entity, 'records': []}
        if scenario == 'duplicate_event':
            raise EiDuplicateError('Mock duplicate event', details={'entity': entity})
        record_id = (params or {}).get('external_id') or f'mock-{entity}-1'
        return {
            'ok': True,
            'mode': 'mock',
            'entity': entity,
            'records': [
                {
                    'id': record_id,
                    'external_id': record_id,
                    'name': f'Mock {entity}',
                    'code': 'MOCK001',
                    'status': 'active',
                }
            ],
        }

    def push(self, entity, payload):
        self._apply_scenario()
        return {
            'ok': True,
            'mode': 'mock',
            'entity': entity,
            'accepted': True,
            'external_id': (payload or {}).get('external_id') or (payload or {}).get('id'),
        }

    def health(self):
        return self.health_check()
