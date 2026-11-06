# -*- coding: utf-8 -*-
"""Offline CCTV stub. Never opens sockets, HTTP, or RTSP."""
from .base import VaCctvAdapter


class VaCctvStubAdapter(VaCctvAdapter):
    key = 'stub'
    is_mock = True

    def test_connection(self):
        return {
            'ok': True,
            'health': 'offline',
            'message': 'Stub adapter: no network call performed.',
            'mode': 'stub',
            'connected': False,
        }

    def resolve_stream(self):
        camera = self.camera
        url = ''
        protocol = 'none'
        if camera is not None:
            url = getattr(camera, 'stream_url', '') or ''
            protocol = getattr(camera, 'stream_protocol', 'none') or 'none'
        return {
            'ok': True,
            'url': url,
            'protocol': protocol,
            'available': bool(url),
            'mode': 'stub',
        }
