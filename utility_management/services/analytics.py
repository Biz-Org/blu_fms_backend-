# -*- coding: utf-8 -*-
from odoo.tools import SQL

from .common import company_tz, latest_readings, previous_window, reading_domain, require_staff


def _reading_model(env, domain):
    require_staff(env)
    model = env['utility.management.reading']
    query = model._search(domain)
    return model, query


def _column(model, query, name):
    return model._field_to_sql(model._table, name, query)


def _number(value):
    if value in (None, False):
        return 0.0
    return float(value)


def _rows(env, query, columns, group=None, order=None):
    if query.is_empty():
        return []
    if group is not None:
        query.groupby = group
    if order is not None:
        query.order = order
    return env.execute_query(query.select(*columns))


def _bucket_sql(observed, grouping, tz_name):
    local = SQL("timezone(%s, timezone('UTC', %s))", tz_name, observed)
    if grouping == 'week':
        return SQL("to_char(%s, 'IYYY-\"W\"IW')", local)
    if grouping == 'month':
        return SQL("to_char(%s, 'YYYY-MM')", local)
    if grouping == 'year':
        return SQL("to_char(%s, 'YYYY')", local)
    return SQL("to_char(%s, 'YYYY-MM-DD')", local)


def _timezone_name(env, filters, utility_type):
    latest = env['utility.management.reading'].search(
        reading_domain(filters, utility_type),
        order='observed_at desc, id desc',
        limit=1,
    )
    company = latest.company_id or env.company
    timezone = company_tz(env, company)
    return getattr(timezone, 'zone', None) or 'UTC'


def overview(env, filters, utility_type, measures):
    model, query = _reading_model(env, reading_domain(filters, utility_type))
    consumption = _column(model, query, 'consumption_qty')
    abnormal = _column(model, query, 'is_abnormal')
    demand = _column(model, query, 'demand_kw')
    columns = [
        SQL('COUNT(*)'),
        SQL('COALESCE(SUM(%s), 0)', consumption),
        SQL('COUNT(*) FILTER (WHERE %s)', abnormal),
        SQL('COALESCE(MAX(%s), 0)', demand),
    ]
    measure_columns = []
    for measure in measures:
        field = model._fields.get(measure)
        if not field or field.type != 'float' or not field.store:
            measure_columns.append(None)
            continue
        column = _column(model, query, measure)
        measure_columns.append(column)
        columns.append(SQL('COALESCE(AVG(%s) FILTER (WHERE %s <> 0), 0)', column, column))
        columns.append(SQL('COALESCE(MAX(%s) FILTER (WHERE %s <> 0), 0)', column, column))
    aggregated = _rows(env, query, columns)
    if aggregated:
        reading_count, total, abnormal_count, peak = aggregated[0][:4]
        measure_values = list(aggregated[0][4:])
    else:
        reading_count, total, abnormal_count, peak = 0, 0.0, 0, 0.0
        measure_values = []
    payload = {
        'utility_type': utility_type,
        'reading_count': int(reading_count or 0),
        'consumption': _number(total),
        'abnormal': int(abnormal_count or 0),
    }
    cursor = 0
    for measure, column in zip(measures, measure_columns):
        if column is None:
            payload[measure] = {'average': 0.0, 'maximum': 0.0}
            continue
        payload[measure] = {
            'average': _number(measure_values[cursor]),
            'maximum': _number(measure_values[cursor + 1]),
        }
        cursor += 2
    if utility_type == 'electricity':
        payload['peak_demand'] = _number(peak)
    return payload


def trends(env, filters, utility_type):
    filters = filters or {}
    grouping = filters.get('grouping') or 'day'
    model, query = _reading_model(env, reading_domain(filters, utility_type))
    observed = _column(model, query, 'observed_at')
    consumption = _column(model, query, 'consumption_qty')
    demand = _column(model, query, 'demand_kw')
    bucket = _bucket_sql(observed, grouping, _timezone_name(env, filters, utility_type))
    aggregated = _rows(env, query, [
        bucket,
        SQL('COALESCE(SUM(%s), 0)', consumption),
        SQL('COALESCE(MAX(%s), 0)', demand),
        SQL('COUNT(*)'),
    ], group=bucket)
    rows = [{
        'bucket': key or '',
        'consumption': _number(total),
        'peak_demand': _number(peak),
        'count': int(count or 0),
    } for key, total, peak, count in aggregated]
    rows = sorted(rows, key=lambda row: row['bucket'])
    comparison = {'consumption': 0.0}
    if filters.get('comparison') == 'previous_period':
        start, end = previous_window(filters.get('date_from'), filters.get('date_to'))
        if start and end:
            previous_filters = dict(filters)
            previous_filters.update({'date_from': start, 'date_to': end, 'comparison': 'none'})
            comparison = {'consumption': overview(env, previous_filters, utility_type, ())['consumption']}
    peak_bucket = max(rows, key=lambda row: row['consumption'])['bucket'] if rows else False
    return {
        'utility_type': utility_type,
        'grouping': grouping,
        'buckets': rows,
        'previous_period': comparison,
        'peak_bucket': peak_bucket,
    }


def buildings(env, filters, utility_type):
    model, query = _reading_model(env, reading_domain(filters, utility_type))
    site = _column(model, query, 'site_ref')
    prop = _column(model, query, 'property_ref')
    observed = _column(model, query, 'observed_at')
    identity = _column(model, query, 'id')
    consumption = _column(model, query, 'consumption_qty')
    demand = _column(model, query, 'demand_kw')
    key = SQL("COALESCE(NULLIF(%s, ''), NULLIF(%s, ''), 'unassigned')", site, prop)
    aggregated = _rows(env, query, [
        SQL("(ARRAY_AGG(%s ORDER BY %s DESC, %s DESC))[1]", site, observed, identity),
        SQL("(ARRAY_AGG(%s ORDER BY %s DESC, %s DESC))[1]", prop, observed, identity),
        SQL('COALESCE(SUM(%s), 0)', consumption),
        SQL('COALESCE(MAX(%s), 0)', demand),
        SQL('MAX(%s)', observed),
        SQL('MAX(%s)', identity),
    ], group=key)
    aggregated.sort(key=lambda row: ((row[4] is not None), row[4] or '', row[5] or 0), reverse=True)
    return [{
        'site_ref': site_ref or False,
        'property_ref': property_ref or False,
        'consumption': _number(total),
        'peak_demand': _number(peak),
    } for site_ref, property_ref, total, peak, _observed, _identity in aggregated]


def meter_rows(env, filters=None):
    require_staff(env)
    domain = reading_domain(filters)
    model = env['utility.management.reading']
    grouped = model._read_group(
        domain,
        ['meter_id'],
        ['consumption_qty:sum', 'demand_kw:max', 'is_abnormal:bool_or'],
    )
    meters = env['utility.management.meter'].browse([meter.id for meter, _total, _peak, _abnormal in grouped if meter])
    latest = latest_readings(env, meters, domain)
    rows = []
    for meter, total, peak, abnormal in grouped:
        if not meter or meter.id not in latest:
            continue
        reading = latest[meter.id]
        rows.append((reading.observed_at, reading.id, {
            'meter_id': meter.id,
            'meter_code': meter.meter_code,
            'utility_type': meter.utility_type,
            'property_ref': reading.property_ref or False,
            'site_ref': reading.site_ref or False,
            'consumption': _number(total),
            'abnormal': bool(abnormal),
            'peak_demand': _number(peak),
        }))
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in rows]


def property_rows(env, filters=None):
    model, query = _reading_model(env, reading_domain(filters))
    if query.is_empty():
        return []
    prop = _column(model, query, 'property_ref')
    observed = _column(model, query, 'observed_at')
    identity = _column(model, query, 'id')
    consumption = _column(model, query, 'consumption_qty')
    meter_alias = query.join(model._table, 'meter_id', 'utility_management_meter', 'id', 'meter_id')
    utility = SQL.identifier(meter_alias, 'utility_type')
    key = SQL("COALESCE(NULLIF(%s, ''), '')", prop)
    aggregated = _rows(env, query, [
        key,
        SQL("COALESCE(SUM(%s) FILTER (WHERE %s = 'electricity'), 0)", consumption, utility),
        SQL("COALESCE(SUM(%s) FILTER (WHERE %s = 'water'), 0)", consumption, utility),
        SQL("COALESCE(SUM(%s) FILTER (WHERE %s = 'gas'), 0)", consumption, utility),
        SQL('MAX(%s)', observed),
        SQL('MAX(%s)', identity),
    ], group=key)
    aggregated.sort(key=lambda row: ((row[4] is not None), row[4] or '', row[5] or 0), reverse=True)
    return [{
        'property_ref': property_ref or False,
        'electricity': _number(electricity),
        'water': _number(water),
        'gas': _number(gas),
    } for property_ref, electricity, water, gas, _observed, _identity in aggregated]


def tanks(env, filters):
    require_staff(env)
    domain = [('meter_role', '=', 'tank'), ('utility_type', '=', 'water')]
    filters = filters or {}
    for key in ('property_ref', 'site_ref', 'floor_ref', 'area_ref'):
        if filters.get(key):
            domain.append((key, '=', filters[key]))
    meters = env['utility.management.meter'].search(domain)
    latest = latest_readings(env, meters, [('status', '=', 'verified')])
    rows = []
    for meter in meters:
        reading = latest.get(meter.id)
        capacity = meter.tank_capacity or 0.0
        availability = False
        if reading and capacity:
            availability = capacity - reading.tank_level
        rows.append({
            'meter_id': meter.id,
            'meter_code': meter.meter_code,
            'name': meter.name,
            'tank_level': reading.tank_level if reading else False,
            'tank_capacity': capacity,
            'availability': availability,
            'inflow': reading.inflow if reading else False,
            'outflow': reading.outflow if reading else False,
            'flow_rate': reading.flow_rate if reading else False,
            'property_ref': meter.property_ref,
            'site_ref': meter.site_ref,
        })
    return rows
