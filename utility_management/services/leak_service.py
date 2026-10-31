# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .audit_service import AuditService
from .common import copy_location, page_window, require_manager, require_staff


class LeakService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)

    def create(self, values):
        require_staff(self.env)
        values = dict(values or {})
        meter = False
        if values.get('meter_id'):
            meter = self.env['utility.management.meter'].browse(values['meter_id'])
            if not meter.exists():
                raise UserError('Meter was not found.')
            meter.check_access('read')
        vals = {
            'leak_type': values.get('leak_type'),
            'severity': values.get('severity') or 'medium',
            'state': 'detected',
            'detected_at': values.get('detected_at') or fields.Datetime.now(),
            'meter_id': meter.id if meter else False,
            'reading_id': values.get('reading_id') or False,
            'assignee_id': values.get('assignee_id') or False,
            'affected_consumption': values.get('affected_consumption') or 0.0,
            'company_id': meter.company_id.id if meter else values.get('company_id') or self.env.company.id,
        }
        if meter and not any(values.get(name) for name in ('property_ref', 'site_ref', 'department_ref')):
            vals.update(copy_location(meter))
        else:
            for name in (
                'property_ref', 'property_label', 'site_ref', 'site_label',
                'floor_ref', 'floor_label', 'area_ref', 'area_label',
                'department_ref', 'department_label',
            ):
                if name in values:
                    vals[name] = values[name]
        leak = self.env['utility.management.leak'].with_context(utility_leak_service=True).create(vals)
        self.audit.log('leak_change', leak, 'success', 'Leak %s detected.' % leak.name, after={'state': 'detected'})
        return self.dto(leak)

    def from_reading(self, reading, rule):
        existing = self.env['utility.management.leak'].sudo().search([
            ('reading_id', '=', reading.id),
            ('state', '!=', 'closed'),
        ], limit=1)
        if existing:
            return existing
        leak_type = 'gas' if reading.meter_id.utility_type == 'gas' else 'water'
        if rule.rule_type == 'gas_pressure':
            leak_type = 'gas'
        return self.env['utility.management.leak'].sudo().with_context(utility_leak_service=True).create({
            'leak_type': leak_type,
            'severity': rule.severity if rule.severity in ('low', 'medium', 'high', 'critical') else 'medium',
            'state': 'detected',
            'detected_at': reading.observed_at,
            'meter_id': reading.meter_id.id,
            'reading_id': reading.id,
            'company_id': reading.company_id.id,
            'affected_consumption': reading.consumption_qty,
            **copy_location(reading),
        })

    def assign(self, leak_id, user_id):
        require_staff(self.env)
        leak = self._leak(leak_id)
        leak.with_context(utility_leak_service=True).write({'assignee_id': user_id})
        self.audit.log('leak_change', leak, 'success', 'Leak assigned.', after={'assignee_id': user_id})
        return self.dto(leak)

    def transition(self, leak_id, state):
        require_staff(self.env)
        if state in ('resolved', 'closed'):
            require_manager(self.env, 'Only a Facility Manager can resolve or close a leak.')
        leak = self._leak(leak_id)
        before = leak.state
        now = fields.Datetime.now()
        vals = {'state': state}
        if state in ('investigating', 'action_required') and not leak.response_at:
            vals['response_at'] = now
        if state == 'resolved':
            vals['resolved_at'] = now
        if state == 'closed':
            vals['closed_at'] = now
        leak.with_context(utility_leak_service=True).write(vals)
        self.audit.log(
            'leak_change', leak, 'success',
            'Leak %s moved from %s to %s.' % (leak.name, before, state),
            before={'state': before}, after={'state': state},
        )
        return self.dto(leak)

    def add_action(self, leak_id, values):
        require_staff(self.env)
        leak = self._leak(leak_id)
        if leak.state in ('resolved', 'closed') and not (self.env.su or self.env.user.has_group(
            'utility_management.group_facility_manager'
        )):
            raise UserError('This leak is already finished.')
        action = self.env['utility.management.leak.action'].with_context(utility_leak_service=True).create({
            'leak_id': leak.id,
            'company_id': leak.company_id.id,
            'entry_kind': (values or {}).get('entry_kind') or 'investigation',
            'note': (values or {}).get('note'),
            'user_id': self.env.user.id,
            'occurred_at': fields.Datetime.now(),
        })
        self.audit.log('leak_change', leak, 'success', 'Leak action recorded.', after={'action_id': action.id})
        return self.dto(leak)

    def list(self, filters=None):
        require_staff(self.env)
        domain = []
        filters = filters or {}
        for key in ('state', 'severity', 'leak_type', 'property_ref', 'site_ref', 'assignee_id', 'company_id'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        if filters.get('search'):
            domain.append(('name', 'ilike', filters['search']))
        model = self.env['utility.management.leak']
        order = 'detected_at desc, id desc'
        window = page_window(filters)
        if not window:
            return [self.dto(leak) for leak in model.search(domain, order=order)]
        limit, offset = window
        return {
            'rows': [self.dto(leak) for leak in model.search(domain, limit=limit, offset=offset, order=order)],
            'total_count': model.search_count(domain),
            'limit': limit,
            'offset': offset,
        }

    def overview(self, filters=None):
        rows = self.list(filters)
        return {
            'total': len(rows),
            'detected': len([row for row in rows if row['state'] == 'detected']),
            'investigating': len([row for row in rows if row['state'] == 'investigating']),
            'closed': len([row for row in rows if row['state'] == 'closed']),
            'leaks': rows[:20],
        }

    def dto(self, leak):
        response_minutes = False
        resolution_minutes = False
        if leak.response_at and leak.detected_at:
            response_minutes = (leak.response_at - leak.detected_at).total_seconds() / 60.0
        if leak.resolved_at and leak.detected_at:
            resolution_minutes = (leak.resolved_at - leak.detected_at).total_seconds() / 60.0
        return {
            'id': leak.id,
            'name': leak.name,
            'leak_type': leak.leak_type,
            'severity': leak.severity,
            'state': leak.state,
            'detected_at': fields.Datetime.to_string(leak.detected_at),
            'response_at': fields.Datetime.to_string(leak.response_at) if leak.response_at else False,
            'resolved_at': fields.Datetime.to_string(leak.resolved_at) if leak.resolved_at else False,
            'closed_at': fields.Datetime.to_string(leak.closed_at) if leak.closed_at else False,
            'response_minutes': response_minutes,
            'resolution_minutes': resolution_minutes,
            'meter_id': leak.meter_id.id,
            'reading_id': leak.reading_id.id,
            'assignee_id': leak.assignee_id.id,
            'affected_consumption': leak.affected_consumption,
            'property_ref': leak.property_ref,
            'site_ref': leak.site_ref,
            'company_id': leak.company_id.id,
            'actions': [{
                'id': action.id,
                'entry_kind': action.entry_kind,
                'note': action.note,
                'user_id': action.user_id.id,
                'occurred_at': fields.Datetime.to_string(action.occurred_at),
            } for action in leak.action_ids],
        }

    def _leak(self, leak_id):
        leak = self.env['utility.management.leak'].browse(leak_id)
        if not leak.exists():
            raise UserError('Leak was not found.')
        leak.check_access('read')
        return leak
