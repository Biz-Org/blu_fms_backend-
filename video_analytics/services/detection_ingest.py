# -*- coding: utf-8 -*-
"""Detection ingestion. No AI engine; data-driven rules only."""
from odoo import fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.video_analytics.models.va_mixin import DETECTION_TYPE_VALUES, SEVERITY_VALUES


def _parse_timestamp(value):
    if not value:
        raise UserError('Timestamp is required.')
    try:
        parsed = fields.Datetime.to_datetime(value)
    except Exception:
        raise UserError('Timestamp is not valid.')
    if not parsed:
        raise UserError('Timestamp is not valid.')
    return parsed


def _parse_confidence(value):
    if value is None or value is False:
        raise ValidationError('Confidence is required.')
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        raise ValidationError('Confidence must be a number between 0 and 100.')
    if confidence < 0 or confidence > 100:
        raise ValidationError('Confidence must be between 0 and 100.')
    return confidence


def _find_camera(env, vals):
    camera = env['va.camera']
    camera_id = vals.get('camera_id')
    camera_code = (vals.get('camera_code') or '').strip()
    if camera_id:
        camera = camera.search([('id', '=', int(camera_id))], limit=1)
    elif camera_code:
        camera = camera.search([('code', '=', camera_code)], limit=1)
    if not camera:
        raise UserError('Camera was not found.')
    return camera


def _find_zone(env, vals):
    zone_id = vals.get('zone_id')
    zone_code = (vals.get('zone_code') or '').strip()
    if not zone_id and not zone_code:
        return env['va.zone']
    zone = env['va.zone']
    if zone_id:
        zone = zone.search([('id', '=', int(zone_id))], limit=1)
    else:
        zone = zone.search([('code', '=', zone_code)], limit=1)
    if not zone:
        raise UserError('Zone was not found.')
    return zone


def ingest(env, vals):
    """Create or reuse a detection and optionally an event. Manager+ only."""
    env['va.detection']._va_require_manager()
    vals = dict(vals or {})
    camera = _find_camera(env, vals)
    zone = _find_zone(env, vals)
    detection_type = vals.get('detection_type')
    if detection_type not in DETECTION_TYPE_VALUES:
        raise ValidationError('Detection type is not supported.')
    confidence = _parse_confidence(vals.get('confidence'))
    timestamp = _parse_timestamp(vals.get('timestamp'))
    external_id = (vals.get('external_id') or '').strip() or False
    evidence_url = vals.get('evidence_url') or False
    playback_start = vals.get('playback_start') or False
    playback_end = vals.get('playback_end') or False
    severity = vals.get('severity') or False
    if severity and severity not in SEVERITY_VALUES:
        raise ValidationError('Event severity is not supported.')

    Detection = env['va.detection']
    if external_id:
        existing = Detection.search([
            ('external_id', '=', external_id),
            ('company_id', '=', camera.company_id.id),
        ], limit=1)
        if existing:
            return {
                'ok': True,
                'detection_id': existing.id,
                'event_id': existing.event_id.id or False,
                'state': existing.state,
                'skipped': existing.state == 'skipped',
                'skip_reason': existing.skip_reason or False,
                'message': 'Existing detection reused.',
                'idempotent': True,
            }

    rule = env['va.detection.rule'].find_matching_rule(
        detection_type, camera=camera, zone=zone or None,
    )
    det_vals = {
        'camera_id': camera.id,
        'zone_id': zone.id if zone else False,
        'detection_type': detection_type,
        'confidence': confidence,
        'timestamp': timestamp,
        'evidence_url': evidence_url,
        'external_id': external_id,
        'company_id': camera.company_id.id,
        'rule_id': rule.id if rule else False,
        'state': 'new',
        'skip_reason': False,
    }
    detection = Detection.create(det_vals)
    event = env['va.event']
    skip_reason = False

    if not rule:
        message = 'Detection stored without a matching rule.'
    elif confidence < rule.confidence_threshold:
        skip_reason = 'below_threshold'
        detection.write({'state': 'skipped', 'skip_reason': skip_reason})
        message = 'Detection skipped: below confidence threshold.'
    elif not rule.create_event:
        message = 'Matching rule does not create events.'
    else:
        event = env['va.event'].create({
            'event_type': detection_type,
            'severity': severity or rule.default_severity or 'medium',
            'camera_id': camera.id,
            'zone_id': zone.id if zone else False,
            'detection_id': detection.id,
            'confidence': confidence,
            'evidence_url': evidence_url,
            'playback_start': playback_start,
            'playback_end': playback_end,
            'state': 'open',
            'company_id': camera.company_id.id,
        })
        detection.write({
            'event_id': event.id,
            'state': 'linked',
        })
        message = 'Detection linked to a new event.'

    return {
        'ok': True,
        'detection_id': detection.id,
        'event_id': event.id if event else False,
        'state': detection.state,
        'skipped': detection.state == 'skipped',
        'skip_reason': skip_reason or detection.skip_reason or False,
        'message': message,
        'idempotent': False,
    }
