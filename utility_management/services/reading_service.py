# -*- coding: utf-8 -*-
import base64

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.utility_management.models.selections import (
    MANAGER_GROUP,
    PHOTO_MAX_BYTES,
    PHOTO_MIMETYPES,
    READING_SOURCES,
)

from .audit_service import AuditService
from .common import (
    config_for,
    copy_location,
    observed_end,
    observed_start,
    page_window,
    require_manager,
    require_staff,
)


class ReadingService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)

    def create_manual(self, values):
        require_staff(self.env)
        payload = dict(values or {})
        payload['source'] = payload.get('source') or 'manual'
        return self._create(payload)

    def apply_payload(self, payload):
        require_staff(self.env)
        values = dict(payload or {})
        values['source'] = values.get('source') or 'smart_meter'
        if values['source'] not in ('smart_meter', 'imported', 'other'):
            raise UserError('This ingest source is not supported.')
        return self._create(values)

    def verify(self, reading_id):
        require_manager(self.env, 'Only a Facility Manager can verify a reading.')
        reading = self._reading(reading_id)
        before = reading.status
        reading.with_context(utility_reading_service=True).write({
            'status': 'verified',
            'verified_by': self.env.user.id,
            'verified_at': fields.Datetime.now(),
        })
        self.audit.log(
            'reading_verification', reading, 'success',
            'Reading %s verified from %s.' % (reading.name, before),
            before={'status': before}, after={'status': reading.status},
        )
        return self.dto(reading)

    def invalidate(self, reading_id, reason=None):
        require_manager(self.env, 'Only a Facility Manager can invalidate a reading.')
        reading = self._reading(reading_id)
        before = reading.status
        vals = {'status': 'invalid'}
        if reason:
            vals['notes'] = reason
        reading.with_context(utility_reading_service=True).write(vals)
        self.audit.log(
            'reading_verification', reading, 'success',
            'Reading %s invalidated from %s.' % (reading.name, before),
            before={'status': before}, after={'status': 'invalid'},
        )
        return self.dto(reading)

    def correct(self, reading_id, values):
        require_manager(self.env, 'Only a Facility Manager can correct a reading.')
        original = self._reading(reading_id)
        if original.status != 'verified':
            raise UserError('Only a verified reading can be corrected.')
        reason = (values or {}).get('notes') or (values or {}).get('reason')
        if not reason or not str(reason).strip():
            raise UserError('A correction reason is required.')
        before = self.dto(original)
        original.with_context(utility_reading_service=True).write({'status': 'corrected'})
        payload = dict(values or {})
        payload.update({
            'meter_id': original.meter_id.id,
            'source': original.source,
            'observed_at': payload.get('observed_at') or original.observed_at,
            'notes': reason,
            'corrects_reading_id': original.id,
        })
        payload.pop('idempotency_key', None)
        created = self._create(payload)
        self.audit.log(
            'reading_correction', original, 'success',
            'Reading %s corrected.' % original.name,
            before=before, after={'replacement_id': created['reading_id']},
        )
        return created

    def attach_photo(self, reading_id, datas, filename, mimetype):
        require_staff(self.env)
        reading = self._reading(reading_id)
        if mimetype not in PHOTO_MIMETYPES:
            raise UserError('Meter photos must be JPEG, PNG, or WebP.')
        raw = base64.b64decode(datas or b'')
        if len(raw) > PHOTO_MAX_BYTES:
            raise UserError('Meter photos must be 5 MB or smaller.')
        if reading.photo_attachment_id:
            reading.photo_attachment_id.sudo().unlink()
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename or 'meter-photo',
            'datas': datas,
            'mimetype': mimetype,
            'res_model': 'utility.management.reading',
            'res_id': reading.id,
            'public': False,
            'company_id': reading.company_id.id,
        })
        reading.with_context(utility_reading_service=True).write({
            'photo_attachment_id': attachment.id,
        })
        return {'attachment_id': attachment.id, 'public': False}

    def flag_missing(self):
        now = fields.Datetime.now()
        from .alert_service import AlertService
        alerts = AlertService(self.env)
        meters = self.env['utility.management.meter'].sudo().search([
            ('status', 'in', ('online', 'connecting')),
            ('active', '=', True),
        ])
        for meter in meters:
            config = config_for(self.env, meter.company_id)
            window = config.missing_reading_after_minutes if config and config.missing_reading_after_minutes else meter.sync_frequency_minutes
            if not window:
                continue
            latest = self.env['utility.management.reading'].sudo().search([
                ('meter_id', '=', meter.id),
                ('status', '!=', 'corrected'),
            ], order='observed_at desc', limit=1)
            anchor = latest.observed_at if latest else meter.last_sync
            if not anchor:
                continue
            age = (now - anchor).total_seconds() / 60.0
            if age > window:
                alerts.raise_for_meter(meter, 'missing_reading', meter.meter_code)

    def list(self, filters=None):
        require_staff(self.env)
        domain = []
        filters = filters or {}
        for key in ('utility_type',):
            if filters.get(key):
                domain.append(('meter_id.utility_type', '=', filters[key]))
        for key in ('property_ref', 'site_ref', 'source', 'status', 'meter_id'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        if filters.get('search'):
            term = filters['search']
            domain.extend(['|', ('name', 'ilike', term), ('meter_id.meter_code', 'ilike', term)])
        if filters.get('date_from'):
            domain.append(('observed_at', '>=', observed_start(filters['date_from'])))
        if filters.get('date_to'):
            domain.append(('observed_at', '<=', observed_end(filters['date_to'])))
        model = self.env['utility.management.reading']
        window = page_window(filters)
        if not window:
            return [self.dto(reading) for reading in model.search(domain, order='observed_at desc, id desc')]
        limit, offset = window
        return {
            'rows': [self.dto(reading) for reading in model.search(domain, limit=limit, offset=offset, order='observed_at desc, id desc')],
            'total_count': model.search_count(domain),
            'limit': limit,
            'offset': offset,
        }

    def dto(self, reading):
        return {
            'id': reading.id,
            'name': reading.name,
            'meter_id': reading.meter_id.id,
            'meter_code': reading.meter_id.meter_code,
            'utility_type': reading.meter_id.utility_type,
            'observed_at': fields.Datetime.to_string(reading.observed_at),
            'source': reading.source,
            'status': reading.status,
            'register_value': reading.register_value,
            'interval_quantity': reading.interval_quantity,
            'consumption_qty': reading.consumption_qty,
            'previous_reading_id': reading.previous_reading_id.id,
            'corrects_reading_id': reading.corrects_reading_id.id,
            'is_abnormal': reading.is_abnormal,
            'abnormal_reason': reading.abnormal_reason,
            'is_rollover': reading.is_rollover,
            'notes': reading.notes,
            'voltage': reading.voltage,
            'current': reading.current,
            'frequency': reading.frequency,
            'power_factor': reading.power_factor,
            'demand_kw': reading.demand_kw,
            'load_kw': reading.load_kw,
            'flow_rate': reading.flow_rate,
            'tank_level': reading.tank_level,
            'inflow': reading.inflow,
            'outflow': reading.outflow,
            'pressure': reading.pressure,
            'safety_observation': reading.safety_observation,
            'photo_attachment_id': reading.photo_attachment_id.id,
            'property_ref': reading.property_ref,
            'site_ref': reading.site_ref,
            'company_id': reading.company_id.id,
        }

    def _create(self, values):
        meter = self.env['utility.management.meter'].with_context(active_test=False).browse(values.get('meter_id'))
        if not meter.exists():
            raise UserError('Meter was not found.')
        meter.check_access('read')
        if meter.status == 'deactivated' or not meter.active:
            raise UserError('A deactivated meter cannot receive readings.')
        source = values.get('source')
        if source not in dict(READING_SOURCES):
            raise UserError('Reading source is not supported.')
        observed = fields.Datetime.to_datetime(values.get('observed_at'))
        if not observed:
            raise UserError('Reading time is required.')
        if observed > fields.Datetime.now():
            raise UserError('Reading time cannot be in the future.')
        key = (values.get('idempotency_key') or '').strip()
        if key:
            existing = self.env['utility.management.reading'].sudo().search([
                ('company_id', '=', meter.company_id.id),
                ('idempotency_key', '=', key),
                ('status', '!=', 'corrected'),
            ], limit=1)
            if existing:
                return {'status': 'duplicate', 'reading_id': existing.id, 'reading': self.dto(existing)}
        duplicate = self.env['utility.management.reading'].sudo().search_count([
            ('company_id', '=', meter.company_id.id),
            ('meter_id', '=', meter.id),
            ('observed_at', '=', observed),
            ('source', '=', source),
            ('status', '!=', 'corrected'),
        ])
        if duplicate:
            raise UserError('A reading already exists for this meter, time, and source.')
        self._check_chronology(meter, observed, values.get('corrects_reading_id'))
        self._check_incoming_measures(meter, values)
        config = config_for(self.env, meter.company_id)
        verification_required = True if not config else config.verification_required
        consumption, previous, abnormal, reason = self._consumption(meter, observed, values)
        vals = {
            'meter_id': meter.id,
            'company_id': meter.company_id.id,
            'observed_at': observed,
            'source': source,
            'status': 'pending_verification' if verification_required else 'recorded',
            'register_value': values.get('register_value') or 0.0,
            'interval_quantity': values.get('interval_quantity') or 0.0,
            'consumption_qty': consumption,
            'previous_reading_id': previous.id if previous else False,
            'corrects_reading_id': values.get('corrects_reading_id') or False,
            'idempotency_key': key or False,
            'is_abnormal': abnormal,
            'abnormal_reason': reason or False,
            'is_rollover': bool(values.get('is_rollover')),
            'notes': values.get('notes') or False,
            'voltage': values.get('voltage') or 0.0,
            'current': values.get('current') or 0.0,
            'frequency': values.get('frequency') or 0.0,
            'power_factor': values.get('power_factor') or 0.0,
            'demand_kw': values.get('demand_kw') or 0.0,
            'load_kw': values.get('load_kw') or 0.0,
            'flow_rate': values.get('flow_rate') or 0.0,
            'tank_level': values.get('tank_level') or 0.0,
            'inflow': values.get('inflow') or 0.0,
            'outflow': values.get('outflow') or 0.0,
            'pressure': values.get('pressure') or 0.0,
            'safety_observation': values.get('safety_observation') or False,
        }
        vals.update(copy_location(meter))
        try:
            reading = self.env['utility.management.reading'].with_context(
                utility_reading_service=True,
            ).create(vals)
        except Exception as exc:
            if 'utility_reading_observation_uniq' in str(exc) or 'utility_reading_idempotency_uniq' in str(exc):
                raise UserError('A reading already exists for this meter, time, and source.')
            raise
        if source == 'smart_meter':
            from .meter_service import MeterService
            MeterService(self.env).note_communication(meter)
        from .alert_service import AlertService
        AlertService(self.env).evaluate_reading(reading)
        return {'status': 'accepted', 'reading_id': reading.id, 'reading': self.dto(reading)}

    def _check_chronology(self, meter, observed, corrects_id):
        if meter.reading_mode != 'cumulative' or corrects_id:
            return
        latest = self.env['utility.management.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('status', '=', 'verified'),
        ], order='observed_at desc', limit=1)
        if latest and observed < latest.observed_at:
            raise UserError('Reading time is earlier than the latest verified reading.')

    def _check_incoming_measures(self, meter, values):
        utility = meter.utility_type
        electrical = ('voltage', 'current', 'frequency', 'power_factor', 'demand_kw', 'load_kw')
        water_only = ('tank_level', 'inflow', 'outflow')
        gas = ('pressure', 'safety_observation')
        if utility != 'electricity' and any(values.get(name) for name in electrical):
            raise ValidationError('Electrical measures belong on electricity meters only.')
        if utility not in ('water', 'gas') and values.get('flow_rate'):
            raise ValidationError('Flow rate belongs on water or gas meters only.')
        if utility != 'water' and any(values.get(name) for name in water_only):
            raise ValidationError('Water measures belong on water meters only.')
        if utility != 'gas' and any(values.get(name) for name in gas):
            raise ValidationError('Gas measures belong on gas meters only.')
        if 'frequency' in values and values.get('frequency') not in (None, False) and float(values['frequency']) <= 0:
            raise ValidationError('Frequency must be greater than zero.')
        if 'power_factor' in values and values.get('power_factor') not in (None, False):
            factor = float(values['power_factor'])
            if factor < 0 or factor > 1:
                raise ValidationError('Power factor must be between 0 and 1.')
        for name in ('voltage', 'current', 'demand_kw', 'load_kw', 'flow_rate', 'tank_level', 'inflow', 'outflow', 'pressure', 'register_value', 'interval_quantity'):
            if name in values and values.get(name) not in (None, False) and float(values[name]) < 0:
                raise ValidationError('Physical measures cannot be negative.')
        if meter.meter_role == 'tank' and values.get('tank_level') not in (None, False):
            if not meter.tank_capacity or float(values['tank_level']) > meter.tank_capacity:
                raise ValidationError('Tank level cannot exceed tank capacity.')

    def _consumption(self, meter, observed, values):
        previous = self.env['utility.management.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('status', '=', 'verified'),
            ('observed_at', '<', observed),
        ], order='observed_at desc, id desc', limit=1)
        is_rollover = bool(values.get('is_rollover'))
        if is_rollover and not (self.env.su or self.env.user.has_group(MANAGER_GROUP)):
            raise AccessError('Only a Facility Manager can record a rollover.')
        if meter.reading_mode == 'interval':
            if values.get('interval_quantity') in (None, False):
                raise UserError('Interval quantity is required.')
            quantity = float(values['interval_quantity'])
        else:
            if values.get('register_value') in (None, False):
                raise UserError('Register value is required.')
            register_value = float(values['register_value'])
            if previous:
                quantity = register_value - previous.register_value
            else:
                quantity = 0.0
            if quantity < 0 and not is_rollover:
                raise UserError('Consumption cannot be negative without a rollover.')
        abnormal = False
        reason = False
        if (
            meter.anomaly_enabled
            and meter.anomaly_percent
            and previous
            and previous.consumption_qty
            and quantity > previous.consumption_qty
        ):
            change = ((quantity - previous.consumption_qty) / previous.consumption_qty) * 100.0
            if change >= meter.anomaly_percent:
                abnormal = True
                reason = 'Consumption exceeded the anomaly percent.'
        return quantity, previous, abnormal, reason

    def _reading(self, reading_id):
        reading = self.env['utility.management.reading'].browse(reading_id)
        if not reading.exists():
            raise UserError('Reading was not found.')
        reading.check_access('read')
        return reading
