# -*- coding: utf-8 -*-
"""Base connector contract for ERP/CRM/Bank/WhatsApp/Legacy adapters."""
from abc import ABC, abstractmethod
import time
import json

from ..exceptions import (
    EiAuthenticationError,
    EiConnectionError,
    EiIntegrationError,
    EiTimeoutError,
    EiServerError,
)


class BaseConnectorAdapter(ABC):
    """
    Clean connector interface.

    Concrete adapters must not hard-code credentials.
    Mock adapters are for development/testing only (is_mock=True).
    """

    key = 'base'
    category = None
    is_mock = True

    def __init__(self, env=None, connector=None, scenario=None):
        self.env = env
        self.connector = connector
        self.scenario = scenario or self._scenario_from_connector(connector)
        self._connected = False
        self._last_health = None

    @staticmethod
    def _scenario_from_connector(connector):
        if not connector:
            return 'success'
        settings = getattr(connector, 'settings_json', None) or ''
        if isinstance(settings, dict):
            return settings.get('mock_scenario') or 'success'
        try:
            data = json.loads(settings) if settings else {}
            return data.get('mock_scenario') or 'success'
        except (TypeError, ValueError, json.JSONDecodeError):
            return 'success'

    # ---- required contract ----
    @abstractmethod
    def authenticate(self):
        raise NotImplementedError

    @abstractmethod
    def test_connection(self):
        raise NotImplementedError

    def connect(self):
        self.authenticate()
        self._connected = True
        return {'ok': True, 'connected': True, 'mode': 'mock' if self.is_mock else 'live'}

    def disconnect(self):
        self._connected = False
        return {'ok': True, 'connected': False}

    def health_check(self):
        started = time.time()
        try:
            result = self.test_connection()
            elapsed = int((time.time() - started) * 1000)
            payload = {
                'ok': bool(result.get('ok')),
                'health': 'healthy' if result.get('ok') else 'down',
                'response_time_ms': elapsed,
                'mode': 'mock' if self.is_mock else 'live',
                'message': result.get('message'),
            }
            self._last_health = payload
            return payload
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.time() - started) * 1000)
            mapped = self.handle_error(exc)
            payload = {
                'ok': False,
                'health': 'down',
                'response_time_ms': elapsed,
                'mode': 'mock' if self.is_mock else 'live',
                'error': mapped,
            }
            self._last_health = payload
            return payload

    def send(self, entity, payload):
        return self.push(entity, payload)

    def receive(self, entity, params=None):
        return self.fetch(entity, params=params)

    def synchronize(self, entity, params=None):
        data = self.fetch(entity, params=params)
        return {
            'ok': data.get('ok', True),
            'entity': entity,
            'records': data.get('records') or [],
            'mode': 'mock' if self.is_mock else 'live',
        }

    @abstractmethod
    def fetch(self, entity, params=None):
        raise NotImplementedError

    @abstractmethod
    def push(self, entity, payload):
        raise NotImplementedError

    def handle_error(self, exc):
        if isinstance(exc, EiIntegrationError):
            return {
                'error_class': exc.error_class,
                'message': str(exc),
                'retryable': exc.retryable,
                'details': getattr(exc, 'details', {}) or {},
            }
        return {
            'error_class': type(exc).__name__,
            'message': str(exc),
            'retryable': True,
            'details': {},
        }

    def retry(self, operation, *args, max_attempts=3, **kwargs):
        """Execute operation with simple retry for retryable failures."""
        from ..retry_service import RetryService
        retry_svc = RetryService(max_attempts=max_attempts)
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                mapped = self.handle_error(exc)
                last_error = mapped
                plan = retry_svc.plan(attempt, retryable=mapped.get('retryable', True))
                if plan['status'] != 'retrying':
                    break
        raise EiServerError(
            last_error.get('message') if last_error else 'Retry exhausted',
            error_class=(last_error or {}).get('error_class', 'RetryExhausted'),
            retryable=False,
            details={'attempts': max_attempts, 'last_error': last_error},
        )

    def _apply_scenario(self):
        """Shared mock failure injection."""
        scenario = (self.scenario or 'success').lower()
        if scenario == 'auth_failure':
            raise EiAuthenticationError('Mock authentication failed')
        if scenario == 'timeout':
            raise EiTimeoutError('Mock timeout')
        if scenario == 'connection_failure':
            raise EiConnectionError('Mock connection failure')
        if scenario == 'server_error':
            raise EiServerError('Mock server error')
        if scenario == 'invalid_response':
            raise EiIntegrationError('Mock invalid response', error_class='InvalidResponse', retryable=False)
        return scenario
