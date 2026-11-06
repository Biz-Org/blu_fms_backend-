# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError

from .common import (
    CLOSED_STATES,
    INCIDENT_ACTIONS,
    assert_admin_action,
    assert_manager_action,
    assert_state,
    assert_user_action,
    extra_values,
    is_manager,
    lifecycle,
    now,
    require_record,
    require_user,
    assert_company_access,
)


class IncidentService:
    def __init__(self, env):
        self.env = env

    def get_incident(self, incident_id):
        return require_record(self.env, 'cc.incident', incident_id, 'Incident')

    def run_action(self, incident_id, action, extra=None):
        action = (action or '').strip()
        extra = extra_values(extra)
        if action not in INCIDENT_ACTIONS:
            raise UserError('Unknown action "%s".' % (action or ''))
        if action == 'create':
            self.env['cc.incident']._cc_require_manager()
            return self.create_incident(extra)
        incident = self.get_incident(incident_id)
        assert_user_action(incident)
        method = getattr(self, action)
        return method(incident, extra) if action in ('assign', 'resolve', 'add_note', 'escalate') else method(incident)

    def create_incident(self, values):
        self.env['cc.incident']._cc_require_manager()
        values = extra_values(values)
        summary = values.get('summary')
        severity = values.get('severity')
        if not str(summary or '').strip():
            raise UserError('Incident summary is required.')
        allowed = {item[0] for item in self.env['cc.incident']._fields['severity'].selection}
        if severity not in allowed:
            raise UserError('Incident severity is not supported.')
        vals = {
            'summary': summary,
            'severity': severity,
            'state': 'open',
            'opened_at': now(),
            'company_id': values.get('company_id') or self.env.company.id,
        }
        if values.get('site_id'):
            site = require_record(self.env, 'cc.site', values['site_id'], 'Site')
            if site.company_id.id != vals['company_id']:
                raise UserError('Incident company must match the selected site company.')
            vals['site_id'] = site.id
        if values.get('user_id'):
            user = require_user(self.env, values['user_id'])
            company = self.env['res.company'].browse(vals['company_id'])
            assert_company_access(user, company)
            vals['user_id'] = user.id
        if values.get('name'):
            vals['name'] = values['name']
        return self.env['cc.incident'].create(vals)

    def acknowledge(self, incident, extra=None):
        assert_user_action(incident)
        assert_state(incident, ('open',), 'acknowledge')
        lifecycle(incident).write({
            'state': 'acknowledged',
            'acknowledged_at': now(),
        })
        return incident

    def investigate(self, incident, extra=None):
        assert_user_action(incident)
        assert_state(incident, ('open', 'acknowledged'), 'investigate')
        lifecycle(incident).write({'state': 'investigating'})
        return incident

    def escalate(self, incident, extra=None):
        assert_manager_action(incident)
        assert_state(incident, ('open', 'acknowledged', 'investigating'), 'escalate')
        extra = extra_values(extra)
        alerts = incident.alert_ids
        if not alerts:
            raise UserError('Link an alert before escalating this incident.')
        from .escalation_service import EscalationService
        service = EscalationService(self.env)
        for alert in alerts:
            service.escalate_alert(alert, extra)
        return incident

    def assign(self, incident, extra=None):
        assert_user_action(incident)
        extra = extra_values(extra)
        user_id = extra.get('user_id')
        if user_id in (None, False, ''):
            user_id = self.env.uid
        user = require_user(self.env, user_id)
        if user.id != self.env.uid and not is_manager(self.env):
            raise AccessError('Users may assign incidents only to themselves.')
        assert_company_access(user, incident.company_id)
        incident.write({'user_id': user.id})
        return incident

    def resolve(self, incident, extra=None):
        assert_manager_action(incident)
        assert_state(incident, ('acknowledged', 'investigating'), 'resolve')
        extra = extra_values(extra)
        values = {
            'state': 'resolved',
            'resolved_at': now(),
        }
        if extra.get('resolution'):
            values['resolution'] = extra.get('resolution')
        lifecycle(incident).write(values)
        return incident

    def close(self, incident, extra=None):
        assert_manager_action(incident)
        assert_state(incident, ('resolved',), 'close')
        lifecycle(incident).write({
            'state': 'closed',
            'closed_at': now(),
        })
        return incident

    def reopen(self, incident, extra=None):
        assert_admin_action(incident)
        assert_state(incident, CLOSED_STATES, 'reopen')
        lifecycle(incident).write({
            'state': 'open',
            'acknowledged_at': False,
            'resolved_at': False,
            'closed_at': False,
        })
        return incident

    def add_note(self, incident, extra=None):
        assert_user_action(incident)
        extra = extra_values(extra)
        body = extra.get('body') or extra.get('note')
        if not str(body or '').strip():
            raise UserError('Investigation note body is required.')
        return self.env['cc.investigation.note'].create({
            'incident_id': incident.id,
            'body': body,
        })
