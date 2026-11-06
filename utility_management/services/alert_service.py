# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

from .audit_service import AuditService
from .common import copy_location, page_window, require_manager, require_staff
from .notification_service import NotificationService

SYSTEM_ALERT_TYPES = (
    'meter_offline',
    'missing_reading',
    'grid_outage',
    'generator_fault',
)


class AlertService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)
        self.notification = NotificationService(env)

    def save_rule(self, values):
        require_manager(self.env, 'Only a Facility Manager can configure alert rules.')
        values = dict(values or {})
        rule_model = self.env['utility.management.alert.rule'].with_context(utility_alert_service=True)
        if values.get('id'):
            rule = rule_model.browse(values['id'])
            if not rule.exists():
                raise UserError('Alert rule was not found.')
            before = {'name': rule.name, 'threshold_value': rule.threshold_value}
            rule.write({key: values[key] for key in values if key != 'id'})
            self.audit.log('alert_change', rule, 'success', 'Alert rule updated.', before=before, after={'name': rule.name})
            return self.rule_dto(rule)
        rule = rule_model.create(values)
        self.audit.log('alert_change', rule, 'success', 'Alert rule created.', after={'name': rule.name})
        return self.rule_dto(rule)

    def list_rules(self, filters=None):
        require_staff(self.env)
        domain = []
        filters = filters or {}
        if filters.get('rule_type'):
            domain.append(('rule_type', '=', filters['rule_type']))
        if filters.get('utility_type'):
            domain.append(('utility_type', '=', filters['utility_type']))
        return [self.rule_dto(rule) for rule in self.env['utility.management.alert.rule'].search(domain)]

    def raise_for_meter(self, meter, alert_type, observed, rule=None):
        open_alert = self.env['utility.management.alert'].sudo().search([
            ('meter_id', '=', meter.id),
            ('alert_type', '=', alert_type),
            ('state', 'not in', ('resolved', 'closed')),
        ], limit=1)
        if open_alert:
            return open_alert
        if not rule and alert_type in SYSTEM_ALERT_TYPES:
            rule = self._matching_rule(meter, alert_type)
        severity = rule.severity if rule else 'medium'
        vals = {
            'rule_id': rule.id if rule else False,
            'alert_type': alert_type,
            'severity': severity,
            'state': 'new',
            'meter_id': meter.id,
            'company_id': meter.company_id.id,
            'triggered_at': fields.Datetime.now(),
            'observed_value': observed if isinstance(observed, (int, float)) else 0.0,
            'threshold_value': rule.threshold_value if rule else 0.0,
            'assignee_id': rule.escalate_to_id.id if rule and rule.escalate_to_id else False,
        }
        vals.update(copy_location(meter))
        alert = self.env['utility.management.alert'].sudo().with_context(utility_alert_service=True).create(vals)
        self.audit.log('alert_change', alert, 'success', 'Alert %s raised.' % alert.name, after={'state': 'new'})
        users = alert.assignee_id or alert.company_id and self.env.ref(
            'utility_management.group_facility_manager'
        ).users.filtered(lambda user: alert.company_id in user.company_ids)
        self.notification.notify_record(alert, users, alert.name)
        return alert

    def evaluate_reading(self, reading):
        rules = self.env['utility.management.alert.rule'].sudo().search([
            ('active', '=', True),
            ('company_id', '=', reading.company_id.id),
        ])
        for rule in rules:
            if rule.meter_id and rule.meter_id != reading.meter_id:
                continue
            if rule.utility_type and rule.utility_type != reading.meter_id.utility_type:
                continue
            if not self._matches_location(rule, reading):
                continue
            matched, observed = self._matches_reading(rule, reading)
            if not matched:
                continue
            alert = self.raise_for_meter(reading.meter_id, rule.rule_type, observed, rule)
            if alert and not alert.reading_id:
                alert.sudo().with_context(utility_alert_service=True).write({'reading_id': reading.id})
            if rule.rule_type in ('spike', 'gas_pressure') and reading.meter_id.utility_type in ('water', 'gas'):
                from .leak_service import LeakService
                LeakService(self.env).from_reading(reading, rule)

    def transition(self, alert_id, state, values=None):
        require_staff(self.env)
        values = values or {}
        alert = self._alert(alert_id)
        if state in ('resolved', 'closed'):
            require_manager(self.env, 'Only a Facility Manager can close an alert.')
        before = alert.state
        vals = {'state': state}
        now = fields.Datetime.now()
        if state == 'acknowledged':
            vals.update({'acknowledged_by': self.env.user.id, 'acknowledged_at': now})
        if state == 'in_progress' and values.get('assignee_id'):
            vals['assignee_id'] = values['assignee_id']
        if state == 'resolved':
            vals.update({
                'resolved_by': self.env.user.id,
                'resolved_at': now,
                'resolution_note': values.get('resolution_note') or alert.resolution_note,
            })
        if state == 'closed':
            vals['closed_at'] = now
        alert.with_context(utility_alert_service=True).write(vals)
        self.audit.log(
            'alert_change', alert, 'success',
            'Alert %s moved from %s to %s.' % (alert.name, before, state),
            before={'state': before}, after={'state': state},
        )
        return self.dto(alert)

    def assign(self, alert_id, user_id):
        require_staff(self.env)
        alert = self._alert(alert_id)
        alert.with_context(utility_alert_service=True).write({'assignee_id': user_id})
        self.audit.log('alert_change', alert, 'success', 'Alert assigned.', after={'assignee_id': user_id})
        return self.dto(alert)

    def escalate_due(self):
        now = fields.Datetime.now()
        alerts = self.env['utility.management.alert'].sudo().search([
            ('state', 'not in', ('resolved', 'closed')),
            ('escalation_count', '=', 0),
            ('rule_id', '!=', False),
        ])
        for alert in alerts:
            minutes = alert.rule_id.escalation_minutes or 0
            if minutes <= 0 or not alert.triggered_at:
                continue
            if alert.triggered_at + timedelta(minutes=minutes) > now:
                continue
            vals = {
                'escalation_count': alert.escalation_count + 1,
                'escalated_at': now,
            }
            if alert.rule_id.escalate_to_id:
                vals['assignee_id'] = alert.rule_id.escalate_to_id.id
            alert.with_context(utility_alert_service=True).write(vals)
            users = alert.assignee_id
            self.notification.notify_record(alert, users, 'Escalated: %s' % alert.name)
            self.audit.log('alert_change', alert, 'success', 'Alert escalated once.', after=vals)

    def list(self, filters=None):
        require_staff(self.env)
        domain = []
        filters = filters or {}
        for key in ('state', 'severity', 'alert_type', 'property_ref', 'site_ref', 'meter_id', 'company_id'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        if filters.get('utility_type'):
            domain.append(('meter_id.utility_type', '=', filters['utility_type']))
        if filters.get('search'):
            domain.append(('name', 'ilike', filters['search']))
        return self._page(self.env['utility.management.alert'], domain, 'triggered_at desc, id desc', filters)

    def overview(self, filters=None):
        rows = self.list(filters)
        return {
            'total': len(rows),
            'new': len([row for row in rows if row['state'] == 'new']),
            'in_progress': len([row for row in rows if row['state'] in ('acknowledged', 'in_progress')]),
            'resolved': len([row for row in rows if row['state'] in ('resolved', 'closed')]),
            'alerts': rows[:20],
        }

    def _page(self, model, domain, order, filters):
        window = page_window(filters)
        if not window:
            return [self.dto(record) for record in model.search(domain, order=order)]
        limit, offset = window
        records = model.search(domain, limit=limit, offset=offset, order=order)
        return {
            'rows': [self.dto(record) for record in records],
            'total_count': model.search_count(domain),
            'limit': limit,
            'offset': offset,
        }

    def dto(self, alert):
        return {
            'id': alert.id,
            'name': alert.name,
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'state': alert.state,
            'meter_id': alert.meter_id.id,
            'reading_id': alert.reading_id.id,
            'leak_id': alert.leak_id.id,
            'power_event_id': alert.power_event_id.id,
            'rule_id': alert.rule_id.id,
            'assignee_id': alert.assignee_id.id,
            'triggered_at': fields.Datetime.to_string(alert.triggered_at) if alert.triggered_at else False,
            'observed_value': alert.observed_value,
            'threshold_value': alert.threshold_value,
            'escalation_count': alert.escalation_count,
            'property_ref': alert.property_ref,
            'site_ref': alert.site_ref,
            'company_id': alert.company_id.id,
            'resolution_note': alert.resolution_note,
        }

    def rule_dto(self, rule):
        return {
            'id': rule.id,
            'name': rule.name,
            'rule_type': rule.rule_type,
            'utility_type': rule.utility_type,
            'meter_id': rule.meter_id.id,
            'threshold_value': rule.threshold_value,
            'threshold_percent': rule.threshold_percent,
            'tank_bound': rule.tank_bound,
            'severity': rule.severity,
            'escalation_minutes': rule.escalation_minutes,
            'escalate_to_id': rule.escalate_to_id.id,
            'active': rule.active,
            'property_ref': rule.property_ref,
            'site_ref': rule.site_ref,
            'company_id': rule.company_id.id,
        }

    def _matching_rule(self, meter, alert_type):
        """Active same-company rule of this type, using the reading-rule filters.

        Meter, utility, and location limits on the rule are honored. The first
        match in rule name order is used, which is the same order reading
        evaluation uses. An empty result means no rule is configured.
        """
        rules = self.env['utility.management.alert.rule'].sudo().search([
            ('active', '=', True),
            ('company_id', '=', meter.company_id.id),
            ('rule_type', '=', alert_type),
        ], order='name, id')
        for rule in rules:
            if rule.meter_id and rule.meter_id != meter:
                continue
            if rule.utility_type and rule.utility_type != meter.utility_type:
                continue
            if not self._matches_location(rule, meter):
                continue
            return rule
        return self.env['utility.management.alert.rule']

    def _matches_location(self, rule, reading):
        for name in ('property_ref', 'site_ref', 'floor_ref', 'area_ref', 'department_ref'):
            if rule[name] and rule[name] != reading[name]:
                return False
        return True

    def _matches_reading(self, rule, reading):
        if rule.rule_type == 'threshold':
            observed = reading.consumption_qty
            return bool(rule.threshold_value and observed > rule.threshold_value), observed
        if rule.rule_type == 'spike':
            previous = reading.previous_reading_id
            if not previous or not previous.consumption_qty or not rule.threshold_percent:
                return False, 0.0
            change = ((reading.consumption_qty - previous.consumption_qty) / previous.consumption_qty) * 100.0
            return change >= rule.threshold_percent, change
        if rule.rule_type == 'tank_level':
            if reading.tank_level in (None, False) or not reading.meter_id.tank_capacity:
                return False, reading.tank_level
            if rule.tank_bound == 'low':
                return reading.tank_level <= (rule.threshold_value or 0.0), reading.tank_level
            return reading.tank_level >= (rule.threshold_value or 0.0), reading.tank_level
        if rule.rule_type == 'gas_pressure':
            if not reading.pressure or not rule.threshold_value:
                return False, reading.pressure
            if rule.tank_bound == 'low':
                return reading.pressure < rule.threshold_value, reading.pressure
            return reading.pressure > rule.threshold_value, reading.pressure
        return False, 0.0

    def _alert(self, alert_id):
        alert = self.env['utility.management.alert'].browse(alert_id)
        if not alert.exists():
            raise UserError('Alert was not found.')
        alert.check_access('read')
        return alert
