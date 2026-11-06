# -*- coding: utf-8 -*-
"""WhatsApp connector adapter — mock until official provider credentials exist."""
from .mock_adapter import MockAdapter


class WhatsAppAdapter(MockAdapter):
    """
    Message operation abstraction only.
    Not an unofficial WhatsApp service. Not live.
    """

    key = 'whatsapp'
    category = 'whatsapp'
    is_mock = True

    def send_message(self, to, body, **kwargs):
        self._apply_scenario()
        return {
            'ok': True,
            'mode': 'mock',
            'to': to,
            'body_preview': (body or '')[:80],
            'delivery_status': 'accepted',
        }

    def delivery_status(self, message_id):
        self._apply_scenario()
        return {
            'ok': True,
            'mode': 'mock',
            'message_id': message_id,
            'status': 'delivered',
        }

    def push(self, entity, payload):
        payload = payload or {}
        if entity in ('message', 'whatsapp_message'):
            return self.send_message(payload.get('to'), payload.get('body'))
        return super().push(entity, payload)
