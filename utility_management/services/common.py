# -*- coding: utf-8 -*-
from datetime import datetime

import pytz
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError

from odoo.addons.utility_management.models.selections import (
    LOCATION_FIELDS,
    MANAGER_GROUP,
    SECRET_MARKERS,
    STAFF_GROUP,
)


def require_staff(env):
    user = env.user
    if env.su:
        return
    if not user or user._is_public() or not user.has_group(STAFF_GROUP):
        raise AccessError('Utility Management requires an authenticated utility user.')


def require_manager(env, summary='Only a Facility Manager can perform this action.'):
    require_staff(env)
    if env.su or env.user.has_group(MANAGER_GROUP):
        return
    from odoo.addons.utility_management.services.audit_service import AuditService
    AuditService(env).log(
        'access_denied',
        env['utility.management.config'],
        'denied',
        summary,
    )
    raise AccessError(summary)


def config_for(env, company):
    return env['utility.management.config'].sudo().search([
        ('company_id', '=', company.id),
    ], limit=1)


def company_tz(env, company):
    name = (company.partner_id.tz if company.partner_id else False) or env.user.tz or 'UTC'
    try:
        return pytz.timezone(name)
    except Exception:
        return pytz.UTC


def as_utc(value):
    if not value:
        return False
    if isinstance(value, str):
        value = fields.Datetime.to_datetime(value)
    return value


def strip_secrets(payload):
    if not isinstance(payload, dict):
        return {}
    cleaned = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            continue
        if isinstance(value, dict):
            cleaned[key] = strip_secrets(value)
        else:
            cleaned[key] = value
    return cleaned


def copy_location(source):
    return {name: source[name] or False for name in LOCATION_FIELDS if name in source._fields}


def bucket_key(moment, grouping, timezone):
    if not moment:
        return ''
    local = pytz.UTC.localize(moment).astimezone(timezone)
    if grouping == 'week':
        iso = local.isocalendar()
        return '%s-W%02d' % (iso[0], iso[1])
    if grouping == 'month':
        return local.strftime('%Y-%m')
    if grouping == 'year':
        return local.strftime('%Y')
    return local.strftime('%Y-%m-%d')


def previous_window(date_from, date_to):
    if not date_from or not date_to:
        return False, False
    start = fields.Date.to_date(date_from)
    end = fields.Date.to_date(date_to)
    span = (end - start).days + 1
    return start - relativedelta(days=span), end - relativedelta(days=span)


def page_window(filters):
    """Return (limit, offset) when the caller asked for a page.

    Callers that omit limit keep the original unpaged list.
    """
    filters = filters or {}
    raw_limit = filters.get('limit')
    if raw_limit in (None, False, ''):
        return None
    try:
        limit = int(raw_limit)
        offset = int(filters.get('offset') or 0)
    except (TypeError, ValueError):
        return None
    if limit <= 0:
        return None
    return limit, max(offset, 0)


def observed_start(value):
    """Naive start of the selected calendar day, matching analytics date filters."""
    if not value:
        return False
    return datetime.combine(fields.Date.to_date(value), datetime.min.time())


def observed_end(value):
    """Naive end of the selected calendar day, so that day stays inclusive."""
    if not value:
        return False
    return datetime.combine(fields.Date.to_date(value), datetime.max.time())


def latest_readings(env, meters, domain=None):
    """Return the newest matching reading for each meter.

    The row is the one ``search(order='observed_at desc, id desc', limit=1)``
    would return. One grouped lookup and one fetch replace a query per meter.
    """
    if not meters:
        return {}
    reading_model = env['utility.management.reading']
    base = [('meter_id', 'in', list(meters.ids))] + list(domain or [])
    peaks = [
        (meter, observed_at)
        for meter, observed_at in reading_model._read_group(base, ['meter_id'], ['observed_at:max'])
        if meter and observed_at
    ]
    if not peaks:
        return {}
    pair_domain = ['|'] * (len(peaks) - 1) if len(peaks) > 1 else []
    for meter, observed_at in peaks:
        pair_domain.extend([
            '&',
            ('meter_id', '=', meter.id),
            ('observed_at', '=', observed_at),
        ])
    chosen = {}
    for reading in reading_model.search(list(domain or []) + pair_domain, order='observed_at desc, id desc'):
        chosen.setdefault(reading.meter_id.id, reading)
    return chosen


def reading_domain(filters, utility_type=None):
    filters = filters or {}
    domain = [('status', '=', 'verified')]
    if filters.get('company_id'):
        domain.append(('company_id', '=', filters['company_id']))
    if utility_type:
        domain.append(('meter_id.utility_type', '=', utility_type))
    mapping = {
        'property_ref': 'property_ref',
        'site_ref': 'site_ref',
        'floor_ref': 'floor_ref',
        'area_ref': 'area_ref',
        'department_ref': 'department_ref',
        'meter_id': 'meter_id',
    }
    for key, field_name in mapping.items():
        if filters.get(key):
            domain.append((field_name, '=', filters[key]))
    if filters.get('utility_type') and not utility_type:
        domain.append(('meter_id.utility_type', '=', filters['utility_type']))
    if filters.get('date_from'):
        domain.append(('observed_at', '>=', observed_start(filters['date_from'])))
    if filters.get('date_to'):
        domain.append(('observed_at', '<=', observed_end(filters['date_to'])))
    return domain
