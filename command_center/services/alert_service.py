# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError

from .common import (
    ACTIVE_STATES,
    ALERT_ACTIONS,
    CLOSED_STATES,
    assert_admin_action,
    assert_manager_action,
    assert_state,
    assert_user_action,
    extra_values,
    is_manager,
    is_overdue,
    lifecycle,
    now,
    require_record,
    require_user,
    assert_company_access,
)
from .escalation_service import EscalationService


class AlertService:
    def __init__(self, env):
        self.env = env
        self.escalation = EscalationService(env)

    def get_alert(self, alert_id):
        return require_record(self.env, 'cc.alert', alert_id, 'Alert')

    def run_action(self, alert_id, action, extra=None):
        action = (action or '').strip()
        if action not in ALERT_ACTIONS:
            raise UserError('Unknown action "%s".' % (action or ''))
        alert = self.get_alert(alert_id)
        assert_user_action(alert)
        extra = extra_values(extra)
        method = getattr(self, action)
        return method(alert, extra) if action in ('assign', 'escalate', 'resolve', 'add_note', 'to_incident') else method(alert)

    def acknowledge(self, alert, extra=None):
        assert_user_action(alert)
        assert_state(alert, ('open',), 'acknowledge')
        lifecycle(alert).write({
            'state': 'acknowledged',
            'acknowledged_uid': self.env.uid,
            'acknowledged_at': now(),
        })
        return alert

    def investigate(self, alert, extra=None):
        assert_user_action(alert)
        assert_state(alert, ('open', 'acknowledged'), 'investigate')
        lifecycle(alert).write({'state': 'investigating'})
        return alert

    def assign(self, alert, extra=None):
        assert_user_action(alert)
        extra = extra_values(extra)
        user_id = extra.get('user_id')
        if user_id in (None, False, ''):
            user_id = self.env.uid
        user = require_user(self.env, user_id)
        if user.id != self.env.uid and not is_manager(self.env):
            raise AccessError('Users may assign alerts only to themselves.')
        assert_company_access(user, alert.company_id)
        alert.write({'user_id': user.id})
        return alert

    def escalate(self, alert, extra=None):
        self.escalation.escalate_alert(alert, extra)
        return alert

    def to_incident(self, alert, extra=None):
        assert_manager_action(alert)
        extra = extra_values(extra)
        if alert.incident_id:
            return alert
        from .incident_service import IncidentService
        incident = IncidentService(self.env).create_incident({
            'summary': extra.get('summary') or alert.alert_type or alert.name,
            'severity': extra.get('severity') or alert.severity or 'medium',
            'site_id': extra.get('site_id') or (alert.site_id.id if alert.site_id else False),
            'user_id': extra.get('user_id') or (alert.user_id.id if alert.user_id else False),
            'company_id': alert.company_id.id,
        })
        alert.write({'incident_id': incident.id})
        return alert

    def resolve(self, alert, extra=None):
        assert_manager_action(alert)
        assert_state(alert, ('acknowledged', 'investigating'), 'resolve')
        extra = extra_values(extra)
        values = {
            'state': 'resolved',
            'resolved_uid': self.env.uid,
            'resolved_at': now(),
        }
        note = extra.get('resolution_note') or extra.get('resolution')
        if note:
            values['resolution_note'] = note
        lifecycle(alert).write(values)
        return alert

    def close(self, alert, extra=None):
        assert_manager_action(alert)
        assert_state(alert, ('resolved',), 'close')
        lifecycle(alert).write({
            'state': 'closed',
            'closed_at': now(),
        })
        return alert

    def reopen(self, alert, extra=None):
        assert_admin_action(alert)
        assert_state(alert, CLOSED_STATES, 'reopen')
        lifecycle(alert).write({
            'state': 'open',
            'acknowledged_uid': False,
            'acknowledged_at': False,
            'resolved_uid': False,
            'resolved_at': False,
            'closed_at': False,
        })
        return alert

    def add_note(self, alert, extra=None):
        assert_user_action(alert)
        extra = extra_values(extra)
        body = extra.get('body') or extra.get('note') or extra.get('resolution_note')
        if not str(body or '').strip():
            raise UserError('Investigation note body is required.')
        return self.env['cc.investigation.note'].create({
            'alert_id': alert.id,
            'body': body,
        })

    def handle_overdue(self, alert, extra=None):
        assert_manager_action(alert)
        if not alert.is_emergency:
            raise UserError('Alert is not an emergency.')
        if not is_overdue(alert):
            raise UserError('Emergency is not overdue.')
        assert_state(alert, ACTIVE_STATES, 'handle_overdue')
        extra = extra_values(extra)
        rule = self.escalation.select_rule(alert, extra.get('rule_id'))
        if not rule:
            raise UserError('No applicable escalation rule.')
        self.escalation.create_history(alert, rule, extra, result='triggered')
        if rule.user_id:
            alert.user_id = rule.user_id.id
        return alert
