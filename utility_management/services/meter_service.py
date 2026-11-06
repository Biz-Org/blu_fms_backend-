# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .audit_service import AuditService
from .common import (
    copy_location,
    latest_readings,
    page_window,
    require_manager,
    require_staff,
    strip_secrets,
)


class MeterService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)

    def create(self, values):
        require_manager(self.env, 'Only a Facility Manager can register a meter.')
        vals = self._prepare(values)
        meter = self.env['utility.management.meter'].create(vals)
        self._log(meter, meter.status, meter.health, False)
        self.audit.log('meter_change', meter, 'success', 'Meter registered.', after=self._audit_values(meter))
        return self.detail(meter)

    def write(self, meter_id, values):
        require_manager(self.env, 'Only a Facility Manager can modify a meter.')
        meter = self._meter(meter_id)
        before = self._audit_values(meter)
        vals = self._prepare(values, creating=False)
        vals.pop('status', None)
        vals.pop('active', None)
        meter.write(vals)
        self.audit.log('meter_change', meter, 'success', 'Meter updated.', before=before, after=self._audit_values(meter))
        return self.detail(meter)

    def set_status(self, meter_id, status, health=None, error_message=None):
        if not self.env.su:
            require_manager(self.env, 'Only a Facility Manager can change meter status.')
        meter = self._meter(meter_id)
        before = self._audit_values(meter)
        vals = {'status': status}
        if health:
            vals['health'] = health
        if status == 'deactivated':
            vals['active'] = False
        if meter.status == 'deactivated' and status == 'connecting':
            vals['active'] = True
        meter.with_context(utility_meter_status=True).write(vals)
        self._log(meter, meter.status, meter.health, error_message)
        self.audit.log(
            'meter_change', meter, 'success',
            'Meter status changed from %s to %s.' % (before.get('status'), meter.status),
            before=before, after=self._audit_values(meter),
        )
        if meter.status == 'offline':
            from .alert_service import AlertService
            AlertService(self.env).raise_for_meter(meter, 'meter_offline', meter.meter_code)
        return self.detail(meter)

    def test_connection(self, meter_id=None, **_kwargs):
        require_staff(self.env)
        if not meter_id:
            return {'ok': False, 'error': 'no_provider_connected'}
        meter = self._meter(meter_id)
        self._log(meter, meter.status, meter.health, 'no_provider_connected')
        return {'ok': False, 'error': 'no_provider_connected', 'status': meter.status}

    def note_communication(self, meter):
        now = fields.Datetime.now()
        vals = {'last_sync': now}
        target_status = meter.status
        if meter.status in ('connecting', 'offline', 'error'):
            target_status = 'online'
            vals['status'] = 'online'
            vals['health'] = 'healthy'
        meter.sudo().with_context(utility_meter_status=True).write(vals)
        if 'status' in vals:
            self._log(meter, meter.status, meter.health, False)

    def mark_offline(self):
        config_model = self.env['utility.management.config'].sudo()
        now = fields.Datetime.now()
        meters = self.env['utility.management.meter'].sudo().search([
            ('status', '=', 'online'),
            ('last_sync', '!=', False),
        ])
        for meter in meters:
            config = config_model.search([('company_id', '=', meter.company_id.id)], limit=1)
            window = config.offline_after_minutes if config and config.offline_after_minutes else meter.sync_frequency_minutes
            if not window:
                continue
            age = (now - meter.last_sync).total_seconds() / 60.0
            if age > window:
                self.env['utility.management.meter'].browse(meter.id).sudo()
                self.set_status(meter.id, 'offline', health='failed', error_message='Sync window elapsed.')

    def list(self, filters=None):
        require_staff(self.env)
        filters = filters or {}
        domain = self._domain(filters)
        model = self.env['utility.management.meter'].with_context(active_test=False)
        window = page_window(filters)
        if not window:
            return [self.summary(meter) for meter in model.search(domain)]
        limit, offset = window
        total = model.search_count(domain)
        meters = model.search(domain, limit=limit, offset=offset, order='meter_code, id')
        warning_domain = domain + [('status', 'in', ('offline', 'error'))]
        warnings = model.search(warning_domain, limit=5, order='meter_code, id')
        return {
            'rows': [self.summary(meter) for meter in meters],
            'total_count': total,
            'limit': limit,
            'offset': offset,
            'summary': self._summary_counts(model, domain),
            'warnings': [self.summary(meter) for meter in warnings],
            'properties': self._properties(model, filters),
        }

    def detail(self, meter):
        if isinstance(meter, int):
            meter = self._meter(meter)
        return {
            'id': meter.id,
            'name': meter.name,
            'meter_code': meter.meter_code,
            'serial_number': meter.serial_number,
            'utility_type': meter.utility_type,
            'meter_role': meter.meter_role,
            'reading_mode': meter.reading_mode,
            'manufacturer': meter.manufacturer,
            'model': meter.model,
            'uom': meter.uom,
            'protocol': meter.protocol,
            'connection': strip_secrets(meter.connection_config or {}),
            'sync_frequency_minutes': meter.sync_frequency_minutes,
            'status': meter.status,
            'health': meter.health,
            'health_note': meter.health_note,
            'battery_percent': meter.battery_percent,
            'firmware': meter.firmware,
            'anomaly_enabled': meter.anomaly_enabled,
            'anomaly_percent': meter.anomaly_percent,
            'tank_capacity': meter.tank_capacity,
            'power_source_id': meter.power_source_id.id,
            'last_sync': fields.Datetime.to_string(meter.last_sync) if meter.last_sync else False,
            'active': meter.active,
            'company_id': meter.company_id.id,
            **{name: meter[name] or False for name in (
                'property_ref', 'property_label', 'site_ref', 'site_label',
                'floor_ref', 'floor_label', 'area_ref', 'area_label',
                'department_ref', 'department_label',
            )},
        }

    def summary(self, meter):
        payload = self.detail(meter)
        payload.pop('connection', None)
        return payload

    def dashboard(self, filters=None):
        require_staff(self.env)
        filters = filters or {}
        model = self.env['utility.management.meter'].with_context(active_test=False)
        domain = self._domain(filters)
        meters = model.search(domain, limit=20, order='meter_code, id')
        latest = latest_readings(self.env, meters, [('status', '!=', 'invalid')])
        rows = []
        for meter in meters:
            payload = self.summary(meter)
            payload.update(self._latest_payload(meter, latest.get(meter.id)))
            rows.append(payload)
        return {
            'total': model.search_count(domain),
            'counts': self._status_counts(model, domain),
            'meters': rows,
            'properties': self._properties(model, filters),
        }

    def connectivity(self, meter_id):
        require_staff(self.env)
        meter = self._meter(meter_id)
        rows = self.env['utility.management.connectivity'].search([('meter_id', '=', meter.id)])
        return [{
            'id': row.id,
            'observed_at': fields.Datetime.to_string(row.observed_at),
            'status': row.status,
            'health': row.health,
            'error_message': row.error_message,
            'response_ms': row.response_ms,
        } for row in rows]

    def _meter(self, meter_id):
        meter = self.env['utility.management.meter'].with_context(active_test=False).browse(meter_id)
        if not meter.exists():
            raise UserError('Meter was not found.')
        meter.check_access('read')
        return meter

    def _prepare(self, values, creating=True):
        allowed = {
            'name', 'meter_code', 'serial_number', 'utility_type', 'meter_role', 'reading_mode',
            'manufacturer', 'model', 'uom', 'protocol', 'connection_config', 'sync_frequency_minutes',
            'health', 'health_note', 'battery_percent', 'firmware', 'anomaly_enabled', 'anomaly_percent',
            'tank_capacity', 'power_source_id', 'company_id',
            'property_ref', 'property_label', 'site_ref', 'site_label', 'floor_ref', 'floor_label',
            'area_ref', 'area_label', 'department_ref', 'department_label',
        }
        vals = {key: values[key] for key in allowed if key in values}
        if creating:
            vals.setdefault('status', 'connecting')
            vals.setdefault('health', 'unknown')
        return vals

    def _domain(self, filters):
        domain = []
        for key in ('utility_type', 'status', 'meter_role', 'property_ref', 'site_ref', 'floor_ref', 'area_ref', 'department_ref'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        if filters.get('search'):
            term = filters['search']
            domain.extend(['|', ('meter_code', 'ilike', term), ('name', 'ilike', term)])
        return domain

    def _summary_counts(self, model, domain):
        counts = {'electricity': 0, 'water': 0, 'gas': 0, 'online': 0, 'offline': 0, 'error': 0}
        for utility, count in model._read_group(domain, ['utility_type'], ['__count']):
            if utility in counts:
                counts[utility] += count
        for status, count in model._read_group(domain, ['status'], ['__count']):
            if status in ('online', 'offline', 'error'):
                counts[status] += count
        return counts

    def _status_counts(self, model, domain):
        counts = {status: 0 for status in (
            'connecting', 'online', 'offline', 'error', 'maintenance', 'deactivated',
        )}
        for status, count in model._read_group(domain, ['status'], ['__count']):
            counts[status] = counts.get(status, 0) + count
        return counts

    def _properties(self, model, filters):
        option_filters = {key: value for key, value in filters.items() if key != 'property_ref'}
        grouped = model._read_group(self._domain(option_filters), ['property_ref'], [])
        return sorted({property_ref for (property_ref,) in grouped if property_ref})

    def _latest_payload(self, meter, reading):
        if not reading:
            return {'latest_reading': False, 'latest_uom': meter.uom or False}
        return {
            'latest_reading': reading.consumption_qty,
            'latest_uom': meter.uom or False,
        }

    def _latest_reading(self, meter):
        reading = latest_readings(self.env, meter, [('status', '!=', 'invalid')]).get(meter.id)
        return self._latest_payload(meter, reading)

    def _log(self, meter, status, health, error_message):
        self.env['utility.management.connectivity'].with_context(utility_connectivity_log=True).create({
            'meter_id': meter.id,
            'company_id': meter.company_id.id,
            'observed_at': fields.Datetime.now(),
            'status': status,
            'health': health or 'unknown',
            'error_message': error_message or False,
        })

    def _audit_values(self, meter):
        payload = self.detail(meter)
        payload.pop('connection', None)
        return payload
