# -*- coding: utf-8 -*-
"""Legacy system adapter — extensible protocol architecture (REST first)."""
from .mock_adapter import MockAdapter


class LegacyAdapter(MockAdapter):
    """
    Legacy connector abstraction.

    settings_json may include:
      {"protocol": "rest"|"soap"|"sftp"|"file"|"database", "mock_scenario": "success"}

    Only mock REST-style exchange is implemented now. Other protocols are
    extension points for concrete providers without changing the core engine.
    """

    key = 'legacy'
    category = 'legacy'
    is_mock = True
    SUPPORTED_PROTOCOLS = ('rest', 'soap', 'sftp', 'file', 'database')

    def protocol(self):
        import json
        settings = getattr(self.connector, 'settings_json', None) or '{}'
        if isinstance(settings, dict):
            data = settings
        else:
            try:
                data = json.loads(settings) if settings else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                data = {}
        protocol = (data.get('protocol') or 'rest').lower()
        if protocol not in self.SUPPORTED_PROTOCOLS:
            protocol = 'rest'
        return protocol

    def test_connection(self):
        result = super().test_connection()
        result['protocol'] = self.protocol()
        result['message'] = (
            f'Mock legacy ({result["protocol"]}) connection successful — not live.'
        )
        return result
