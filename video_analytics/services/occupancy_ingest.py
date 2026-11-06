# -*- coding: utf-8 -*-
"""Occupancy snapshot ingestion. Percentages are always computed server-side."""
from odoo import fields
from odoo.exceptions import UserError, ValidationError


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


def _find_zone(env, vals):
    zone = env['va.zone']
    zone_id = vals.get('zone_id')
    zone_code = (vals.get('zone_code') or '').strip()
    if zone_id:
        zone = zone.search([('id', '=', int(zone_id))], limit=1)
    elif zone_code:
        zone = zone.search([('code', '=', zone_code)], limit=1)
    if not zone:
        raise UserError('Zone was not found.')
    return zone


def _find_camera(env, vals):
    camera_id = vals.get('camera_id')
    camera_code = (vals.get('camera_code') or '').strip()
    if not camera_id and not camera_code:
        return env['va.camera']
    camera = env['va.camera']
    if camera_id:
        camera = camera.search([('id', '=', int(camera_id))], limit=1)
    else:
        camera = camera.search([('code', '=', camera_code)], limit=1)
    if not camera:
        raise UserError('Camera was not found.')
    return camera


def _crowd_severity(zone, camera):
    rule = zone.env['va.detection.rule'].find_matching_rule(
        'crowd_density', camera=camera or None, zone=zone,
    )
    if rule:
        return rule.default_severity or 'medium'
    return 'medium'


def ingest(env, vals):
    """Create a snapshot and reuse/create a crowd event when over threshold. Manager+ only."""
    env['va.occupancy.snapshot']._va_require_manager()
    vals = dict(vals or {})
    vals.pop('occupancy_pct', None)
    vals.pop('over_threshold', None)
    zone = _find_zone(env, vals)
    camera = _find_camera(env, vals)
    timestamp = _parse_timestamp(vals.get('timestamp'))
    if vals.get('count') is None or vals.get('count') is False:
        raise ValidationError('Occupancy count is required.')
    try:
        count = int(vals.get('count'))
    except (TypeError, ValueError):
        raise ValidationError('Occupancy count must be an integer greater than or equal to 0.')
    if count < 0:
        raise ValidationError('Occupancy count cannot be negative.')
    if zone.capacity <= 0:
        raise ValidationError('Occupancy capacity must be greater than 0.')

    occupancy_pct = round(100.0 * count / zone.capacity, 2)
    over_threshold = occupancy_pct >= zone.occupancy_threshold_pct
    event = env['va.event']
    if over_threshold:
        event = env['va.event'].search([
            ('zone_id', '=', zone.id),
            ('event_type', '=', 'crowd_density'),
            ('state', '=', 'open'),
            ('company_id', '=', zone.company_id.id),
        ], limit=1, order='id desc')
        if not event:
            event = env['va.event'].create({
                'event_type': 'crowd_density',
                'severity': _crowd_severity(zone, camera),
                'zone_id': zone.id,
                'camera_id': camera.id if camera else False,
                'state': 'open',
                'company_id': zone.company_id.id,
                'confidence': occupancy_pct,
            })
    snapshot = env['va.occupancy.snapshot'].create({
        'zone_id': zone.id,
        'camera_id': camera.id if camera else False,
        'timestamp': timestamp,
        'count': count,
        'capacity': zone.capacity,
        'company_id': zone.company_id.id,
        'event_id': event.id if event else False,
    })
    return {
        'ok': True,
        'snapshot_id': snapshot.id,
        'event_id': event.id if event else False,
        'occupancy_pct': snapshot.occupancy_pct,
        'over_threshold': snapshot.over_threshold,
        'capacity': snapshot.capacity,
        'count': snapshot.count,
    }
