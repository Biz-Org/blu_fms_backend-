# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .audit_service import AuditService
from .common import require_manager, require_staff
from odoo.addons.utility_management.models.selections import POWER_EVENT_FOR_STATE, POWER_STATES


class PowerSourceService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)

    def create(self, values):
        require_manager(self.env, 'Only a Facility Manager can register a power source.')
        values = dict(values or {})
        kind = values.get('source_kind')
        if kind == 'generator':
            values.setdefault('status', 'generator_standby')
        else:
            values.setdefault('status', 'grid_active')
            values.setdefault('source_kind', 'grid')
        if values['status'] not in dict(POWER_STATES):
            raise UserError('Power status is not supported.')
        source = self.env['utility.management.power.source'].with_context(
            utility_power_service=True,
        ).create(values)
        return self.dto(source)

    def transition(self, source_id, status, values=None):
        require_staff(self.env)
        values = dict(values or {})
        source = self._source(source_id)
        now = fields.Datetime.now()
        open_events = source.event_ids.filtered(lambda event: not event.ended_at)
        if open_events:
            open_events.with_context(utility_power_service=True).write({'ended_at': now})
        event_vals = {
            'source_id': source.id,
            'company_id': source.company_id.id,
            'event_type': POWER_EVENT_FOR_STATE.get(status, 'outage'),
            'state': status,
            'started_at': now,
            'load': values.get('load') or 0.0,
            'note': values.get('note') or False,
            'has_fuel_level': 'fuel_level_percent' in values,
            'fuel_level_percent': values.get('fuel_level_percent') or 0.0,
            'has_fuel_consumed': 'fuel_consumed' in values,
            'fuel_consumed': values.get('fuel_consumed') or 0.0,
        }
        if status == 'power_restored':
            event_vals['ended_at'] = now
        event = self.env['utility.management.power.event'].with_context(
            utility_power_service=True,
        ).create(event_vals)
        source_vals = {
            'status': status,
            'last_transition_at': now,
        }
        if 'fuel_level_percent' in values:
            source_vals.update({
                'has_fuel_level': True,
                'fuel_level_percent': values['fuel_level_percent'],
            })
        if 'fuel_consumed' in values:
            source_vals.update({
                'has_fuel_consumed': True,
                'fuel_consumed': values['fuel_consumed'],
            })
        source.with_context(utility_power_service=True).write(source_vals)
        if status == 'power_restored':
            source.with_context(utility_power_service=True).write({
                'status': 'grid_active',
                'last_transition_at': now,
            })
        if status in ('grid_outage', 'generator_fault'):
            from .alert_service import AlertService
            meter = source.meter_id
            if meter:
                AlertService(self.env).raise_for_meter(
                    meter,
                    'grid_outage' if status == 'grid_outage' else 'generator_fault',
                    values.get('load') or 0.0,
                )
                alert = self.env['utility.management.alert'].sudo().search([
                    ('meter_id', '=', meter.id),
                    ('alert_type', '=', 'grid_outage' if status == 'grid_outage' else 'generator_fault'),
                ], limit=1)
                if alert and not alert.power_event_id:
                    alert.with_context(utility_alert_service=True).write({'power_event_id': event.id})
        return self.dto(source)

    def list(self, filters=None):
        require_staff(self.env)
        domain = []
        filters = filters or {}
        for key in ('source_kind', 'status', 'property_ref', 'site_ref'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        return [self.dto(source) for source in self.env['utility.management.power.source'].search(domain)]

    def history(self, source_id):
        require_staff(self.env)
        source = self._source(source_id)
        return {
            'source': self.dto(source),
            'events': [self.event_dto(event) for event in source.event_ids],
        }

    def overview(self, filters=None):
        rows = self.list(filters)
        return {
            'total': len(rows),
            'grid_active': len([row for row in rows if row['status'] == 'grid_active']),
            'outages': len([row for row in rows if row['status'] == 'grid_outage']),
            'sources': rows,
        }

    def dto(self, source):
        return {
            'id': source.id,
            'name': source.name,
            'source_kind': source.source_kind,
            'status': source.status,
            'property_ref': source.property_ref,
            'site_ref': source.site_ref,
            'asset_ref': source.asset_ref,
            'meter_id': source.meter_id.id,
            'fuel_level_percent': source.fuel_level_percent if source.has_fuel_level else False,
            'fuel_consumed': source.fuel_consumed if source.has_fuel_consumed else False,
            'rated_load': source.rated_load,
            'last_transition_at': fields.Datetime.to_string(source.last_transition_at) if source.last_transition_at else False,
            'company_id': source.company_id.id,
        }

    def event_dto(self, event):
        return {
            'id': event.id,
            'event_type': event.event_type,
            'state': event.state,
            'started_at': fields.Datetime.to_string(event.started_at),
            'ended_at': fields.Datetime.to_string(event.ended_at) if event.ended_at else False,
            'runtime_hours': event.runtime_hours if event.ended_at else False,
            'load': event.load,
            'fuel_level_percent': event.fuel_level_percent if event.has_fuel_level else False,
            'fuel_consumed': event.fuel_consumed if event.has_fuel_consumed else False,
            'note': event.note,
        }

    def _source(self, source_id):
        source = self.env['utility.management.power.source'].browse(source_id)
        if not source.exists():
            raise UserError('Power source was not found.')
        source.check_access('read')
        return source
