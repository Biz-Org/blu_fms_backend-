# -*- coding: utf-8 -*-
"""CCTV service wrappers around the vendor-neutral stub adapter."""
from odoo import fields
from odoo.exceptions import UserError


_HEALTH_TO_STATUS = {
    'healthy': 'online',
    'online': 'online',
    'degraded': 'degraded',
    'offline': 'offline',
    'inactive': 'inactive',
}


def test_connection(camera):
    camera.ensure_one()
    camera._va_require_manager()
    from odoo.addons.video_analytics.services.cctv import get_adapter
    adapter = get_adapter(camera)
    result = adapter.test_connection() or {}
    health = result.get('health') or 'offline'
    status = _HEALTH_TO_STATUS.get(health, 'offline')
    message = result.get('message') or 'Connection test completed.'
    camera.with_context(va_camera_status=True).write({
        'status': status,
        'last_seen': fields.Datetime.now(),
        'last_error': '' if status == 'online' else message,
    })
    return {
        'ok': bool(result.get('ok')),
        'health': health,
        'status': status,
        'mode': result.get('mode') or 'stub',
        'message': message,
        'connected': False,
    }


def resolve_stream(camera):
    camera.ensure_one()
    camera._va_require_user()
    from odoo.addons.video_analytics.services.cctv import get_adapter
    adapter = get_adapter(camera)
    result = adapter.resolve_stream() or {}
    return {
        'ok': True,
        'url': result.get('url') or camera.stream_url or '',
        'protocol': result.get('protocol') or camera.stream_protocol or 'none',
        'available': bool(result.get('available') or camera.stream_url),
        'mode': result.get('mode') or 'stub',
    }


def set_status(camera, status):
    camera.ensure_one()
    camera._va_require_manager()
    allowed = {'online', 'offline', 'degraded', 'inactive'}
    if status not in allowed:
        raise UserError('Camera status is not supported.')
    camera.with_context(va_camera_status=True).write({
        'status': status,
        'last_error': False if status == 'online' else camera.last_error,
        'last_seen': fields.Datetime.now() if status == 'online' else camera.last_seen,
    })
    return {'ok': True, 'status': camera.status}
