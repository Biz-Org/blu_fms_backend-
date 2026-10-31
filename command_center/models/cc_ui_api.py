# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError
from odoo.osv.expression import AND

from ..services.alert_service import AlertService
from ..services.common import (
    CLOSED_STATES,
    EMERGENCY_ACTIONS,
    assignable_users,
    dt_string,
    extra_values,
    history_rows,
    is_overdue,
    note_rows,
    overdue_domain,
    site_rows,
)
from ..services.incident_service import IncidentService


class CcUiApi(models.TransientModel):
    _name = 'cc.ui.api'
    _description = 'Command Center UI API'
    _inherit = ['cc.mixin']

    def _alerts(self):
        return AlertService(self.env)

    def _incidents(self):
        return IncidentService(self.env)

    @api.model
    def get_session_context(self):
        self._cc_require_user()
        user = self.env.user
        return {
            'uid': user.id,
            'name': user.name,
            'is_user': user.has_group('command_center.group_cc_user'),
            'is_manager': user.has_group('command_center.group_cc_manager'),
            'is_admin': user.has_group('command_center.group_cc_admin'),
        }

    @api.model
    def get_dashboard_data(self):
        self._cc_require_user()
        Alert = self.env['cc.alert']
        Incident = self.env['cc.incident']
        Site = self.env['cc.site']
        closed = list(CLOSED_STATES)
        active_alerts = [('state', 'not in', closed)]
        kpis = {
            'sites_total': Site.search_count([]),
            'sites_operational': Site.search_count([('operational_status', '=', 'normal')]),
            'alerts_active': Alert.search_count(active_alerts),
            'alerts_critical': Alert.search_count(active_alerts + [('severity', '=', 'critical')]),
            'alerts_high': Alert.search_count(active_alerts + [('severity', '=', 'high')]),
            'alerts_medium': Alert.search_count(active_alerts + [('severity', '=', 'medium')]),
            'alerts_low': Alert.search_count(active_alerts + [('severity', '=', 'low')]),
            'incidents_open': Incident.search_count([('state', 'not in', closed)]),
            'incidents_high': Incident.search_count([
                ('state', 'not in', closed),
                ('severity', 'in', ['high', 'critical']),
            ]),
            'emergencies_active': Alert.search_count([
                ('is_emergency', '=', True),
                ('state', 'not in', closed),
            ]),
            'unresolved_overdue': Alert.search_count(overdue_domain()),
        }
        return {
            'kpis': kpis,
            'recent_activity': self._recent_activity(),
            'sites_summary': self._sites_summary(),
        }

    @api.model
    def get_alerts_data(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        domain = self._alert_domain(filters)
        alerts = self.env['cc.alert'].search(domain, order='id desc', limit=100)
        selected = False
        if filters.get('alert_id'):
            match = alerts.filtered(lambda rec: rec.id == int(filters['alert_id']))
            selected = self._alert_payload(match[:1], detailed=True) if match else False
        return {
            'kpis': self._alert_kpis(domain),
            'alerts': [self._alert_payload(alert) for alert in alerts],
            'selected': selected,
            'assignable_users': assignable_users(self.env),
            'sites': site_rows(self.env),
        }

    @api.model
    def run_alert_action(self, alert_id, action, extra=None):
        self._cc_require_user()
        rec = self._alerts().run_action(alert_id, action, extra)
        if action == 'add_note':
            alert = rec.alert_id
        else:
            alert = rec
        return {
            'ok': True,
            'action': action,
            'alert': self._alert_payload(alert, detailed=True),
        }

    @api.model
    def get_monitoring_data(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        domain = []
        if filters.get('site_id'):
            domain.append(('id', '=', int(filters['site_id'])))
        if filters.get('operational_status'):
            domain.append(('operational_status', '=', filters['operational_status']))
        sites = self.env['cc.site'].search(domain, order='name, id')
        return {'sites': [self._monitoring_site(site) for site in sites]}

    @api.model
    def get_incidents_data(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        domain = self._incident_domain(filters)
        incidents = self.env['cc.incident'].search(domain, order='id desc', limit=100)
        selected = False
        if filters.get('incident_id'):
            match = incidents.filtered(lambda rec: rec.id == int(filters['incident_id']))
            selected = self._incident_payload(match[:1], detailed=True) if match else False
        closed = list(CLOSED_STATES)
        return {
            'kpis': {
                'total': self.env['cc.incident'].search_count(domain),
                'incidents_open': self.env['cc.incident'].search_count(
                    AND([domain, [('state', 'not in', closed)]])
                ),
            },
            'incidents': [self._incident_payload(rec) for rec in incidents],
            'selected': selected,
            'assignable_users': assignable_users(self.env),
            'sites': site_rows(self.env),
        }

    @api.model
    def run_incident_action(self, incident_id, action, extra=None):
        self._cc_require_user()
        rec = self._incidents().run_action(incident_id, action, extra)
        if action == 'add_note':
            incident = rec.incident_id
        elif action == 'create':
            incident = rec
        else:
            incident = rec
        return {
            'ok': True,
            'action': action,
            'incident': self._incident_payload(incident, detailed=True),
        }

    @api.model
    def get_emergency_data(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        domain = self._emergency_domain(filters)
        alerts = self.env['cc.alert'].search(domain, order='id desc', limit=100)
        selected = False
        history = []
        if filters.get('alert_id'):
            match = alerts.filtered(lambda rec: rec.id == int(filters['alert_id']))
            if match:
                selected = self._alert_payload(match[:1], detailed=True)
                history = history_rows(match.history_ids.sorted('id', reverse=True))
        closed = list(CLOSED_STATES)
        return {
            'kpis': {
                'emergencies_active': self.env['cc.alert'].search_count(
                    AND([domain, [('state', 'not in', closed)]])
                ),
                'unresolved_overdue': self.env['cc.alert'].search_count(
                    AND([domain, overdue_domain()])
                ),
                'total': self.env['cc.alert'].search_count(domain),
            },
            'alerts': [self._alert_payload(alert) for alert in alerts],
            'selected': selected,
            'history': history,
            'rules': self._rule_rows(),
            'sites': site_rows(self.env),
        }

    @api.model
    def run_emergency_action(self, alert_id, action, extra=None):
        self._cc_require_user()
        action = (action or '').strip()
        if action not in EMERGENCY_ACTIONS:
            raise UserError('Unknown action "%s".' % (action or ''))
        alert = self._alerts().get_alert(alert_id)
        if not alert.is_emergency:
            raise UserError('Alert is not an emergency.')
        if action == 'handle_overdue':
            rec = self._alerts().handle_overdue(alert, extra)
        else:
            rec = self._alerts().run_action(alert.id, action, extra)
        if action == 'add_note':
            alert = rec.alert_id
        else:
            alert = rec
        return {
            'ok': True,
            'action': action,
            'alert': self._alert_payload(alert, detailed=True),
        }

    @api.model
    def get_reports_data(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        source = filters.get('source')
        if source and source not in ('alerts', 'incidents', 'sites', 'emergency'):
            raise UserError('Report source is not supported.')
        payload = {
            'kpis': {
                'alerts': self.env['cc.alert'].search_count(self._alert_domain(filters)),
                'incidents': self.env['cc.incident'].search_count(self._incident_domain(filters)),
                'sites': self.env['cc.site'].search_count(self._site_report_domain(filters)),
                'emergency': self.env['cc.alert'].search_count(self._emergency_domain(filters)),
            },
            'alerts': [],
            'incidents': [],
            'sites': [],
            'emergency': [],
        }
        if source in (None, False, '', 'alerts'):
            payload['alerts'] = [
                self._alert_payload(rec)
                for rec in self.env['cc.alert'].search(
                    self._alert_domain(filters), order='id desc', limit=100
                )
            ]
        if source in (None, False, '', 'incidents'):
            payload['incidents'] = [
                self._incident_payload(rec)
                for rec in self.env['cc.incident'].search(
                    self._incident_domain(filters), order='id desc', limit=100
                )
            ]
        if source in (None, False, '', 'sites'):
            payload['sites'] = site_rows(self.env, self._site_report_domain(filters))
        if source in (None, False, '', 'emergency'):
            payload['emergency'] = [
                self._alert_payload(rec)
                for rec in self.env['cc.alert'].search(
                    self._emergency_domain(filters), order='id desc', limit=100
                )
            ]
        return payload

    @api.model
    def get_report_definitions(self, filters=None):
        self._cc_require_user()
        filters = extra_values(filters)
        domain = []
        if filters.get('source'):
            domain.append(('source', '=', filters['source']))
        if 'active' in filters and filters.get('active') not in (None, ''):
            domain.append(('active', '=', filters['active'] in (True, 'true', '1', 1)))
        definitions = self.env['cc.report.definition'].search(domain, order='name, id')
        exports = self.env['cc.report.export'].search([], order='id desc', limit=100)
        return {
            'definitions': [{
                'id': rec.id,
                'name': rec.name,
                'source': rec.source,
                'field_names': rec.field_names or [],
                'filters_json': rec.filters_json or {},
                'grouping': rec.grouping or '',
                'sorting': rec.sorting or '',
                'active': rec.active,
                'owner_id': rec.owner_id.id or False,
            } for rec in definitions],
            'exports': [{
                'id': rec.id,
                'definition_id': rec.definition_id.id or False,
                'export_format': rec.export_format,
                'filename': rec.filename or '',
                'create_date': dt_string(rec.create_date),
            } for rec in exports],
        }

    @api.model
    def run_report(self, definition_id=None, spec=None):
        self._cc_require_user()
        spec = extra_values(spec)
        source = spec.get('source')
        if definition_id:
            definition = self.env['cc.report.definition'].browse(int(definition_id))
            if not definition.exists():
                raise UserError('Report definition not found.')
            source = source or definition.source
        if source not in ('alerts', 'incidents', 'sites', 'emergency'):
            raise UserError('Report source is not supported.')
        data = self.get_reports_data({'source': source})
        return {
            'source': source,
            'rows': data[source if source != 'emergency' else 'emergency'],
        }

    @api.model
    def export_report(self, definition_id=None, spec=None, export_format='csv'):
        self._cc_require_user()
        raise UserError('Report export is not available yet.')

    def _alert_domain(self, filters):
        domain = []
        mapping = {
            'severity': 'severity',
            'source': 'source',
            'alert_type': 'alert_type',
            'state': 'state',
            'is_emergency': 'is_emergency',
        }
        for key, field in mapping.items():
            if filters.get(key) not in (None, False, ''):
                domain.append((field, '=', filters[key]))
        if filters.get('site_id'):
            domain.append(('site_id', '=', int(filters['site_id'])))
        if filters.get('user_id'):
            domain.append(('user_id', '=', int(filters['user_id'])))
        if filters.get('alert_id'):
            domain.append(('id', '=', int(filters['alert_id'])))
        domain.extend(self._date_domain(filters))
        search = filters.get('search')
        if search:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', search))
            domain.append(('alert_type', 'ilike', search))
            domain.append(('resolution_note', 'ilike', search))
        return domain

    def _incident_domain(self, filters):
        domain = []
        if filters.get('severity'):
            domain.append(('severity', '=', filters['severity']))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('site_id'):
            domain.append(('site_id', '=', int(filters['site_id'])))
        if filters.get('user_id'):
            domain.append(('user_id', '=', int(filters['user_id'])))
        if filters.get('incident_id'):
            domain.append(('id', '=', int(filters['incident_id'])))
        domain.extend(self._date_domain(filters))
        search = filters.get('search')
        if search:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', search))
            domain.append(('summary', 'ilike', search))
            domain.append(('resolution', 'ilike', search))
        return domain

    def _emergency_domain(self, filters):
        domain = [('is_emergency', '=', True)]
        if filters.get('alert_type'):
            domain.append(('alert_type', '=', filters['alert_type']))
        if filters.get('site_id'):
            domain.append(('site_id', '=', int(filters['site_id'])))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('alert_id'):
            domain.append(('id', '=', int(filters['alert_id'])))
        if filters.get('level') not in (None, False, ''):
            domain.append(('history_ids.level', '=', int(filters['level'])))
        if filters.get('overdue') in (True, 'true', '1', 1):
            domain = AND([domain, overdue_domain()])
        return domain

    def _date_domain(self, filters):
        domain = []
        if filters.get('date_from'):
            domain.append(('create_date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('create_date', '<=', filters['date_to']))
        return domain

    def _site_report_domain(self, filters):
        domain = []
        if filters.get('site_id'):
            domain.append(('id', '=', int(filters['site_id'])))
        if filters.get('operational_status'):
            domain.append(('operational_status', '=', filters['operational_status']))
        return domain

    def _alert_kpis(self, domain):
        Alert = self.env['cc.alert']
        closed = list(CLOSED_STATES)
        return {
            'total': Alert.search_count(domain),
            'alerts_active': Alert.search_count(AND([domain, [('state', 'not in', closed)]])),
            'emergencies_active': Alert.search_count(AND([
                domain,
                [('is_emergency', '=', True), ('state', 'not in', closed)],
            ])),
            'unresolved_overdue': Alert.search_count(AND([domain, overdue_domain()])),
        }

    def _alert_payload(self, alert, detailed=False):
        if not alert:
            return False
        data = {
            'id': alert.id,
            'name': alert.name,
            'alert_type': alert.alert_type,
            'severity': alert.severity or False,
            'source': alert.source or False,
            'state': alert.state,
            'site_id': alert.site_id.id or False,
            'site_name': alert.site_id.name or '',
            'company_id': alert.company_id.id,
            'user_id': alert.user_id.id or False,
            'user_name': alert.user_id.name or '',
            'is_emergency': bool(alert.is_emergency),
            'is_overdue': is_overdue(alert),
            'response_deadline': dt_string(alert.response_deadline),
            'acknowledged_at': dt_string(alert.acknowledged_at),
            'resolved_at': dt_string(alert.resolved_at),
            'closed_at': dt_string(alert.closed_at),
            'incident_id': alert.incident_id.id or False,
            'create_date': dt_string(alert.create_date),
            'write_date': dt_string(alert.write_date),
            'source_model': alert.source_model or '',
            'source_id': alert.source_id or False,
        }
        if detailed:
            data['resolution_note'] = alert.resolution_note or ''
            data['notes'] = note_rows(alert.note_ids)
            data['history'] = history_rows(alert.history_ids.sorted('id', reverse=True))
        return data

    def _incident_payload(self, incident, detailed=False):
        if not incident:
            return False
        data = {
            'id': incident.id,
            'name': incident.name,
            'severity': incident.severity or False,
            'state': incident.state,
            'site_id': incident.site_id.id or False,
            'site_name': incident.site_id.name or '',
            'company_id': incident.company_id.id,
            'user_id': incident.user_id.id or False,
            'user_name': incident.user_id.name or '',
            'summary': incident.summary or '',
            'opened_at': dt_string(incident.opened_at),
            'acknowledged_at': dt_string(incident.acknowledged_at),
            'resolved_at': dt_string(incident.resolved_at),
            'closed_at': dt_string(incident.closed_at),
            'create_date': dt_string(incident.create_date),
            'write_date': dt_string(incident.write_date),
        }
        if detailed:
            data['resolution'] = incident.resolution or ''
            data['notes'] = note_rows(incident.note_ids)
            data['alert_ids'] = incident.alert_ids.ids
            data['alerts'] = [{
                'id': alert.id,
                'name': alert.name,
                'state': alert.state,
            } for alert in incident.alert_ids]
        return data

    def _monitoring_site(self, site):
        closed = list(CLOSED_STATES)
        alerts = self.env['cc.alert'].search([
            ('site_id', '=', site.id),
            ('state', 'not in', closed),
        ])
        incidents = self.env['cc.incident'].search([
            ('site_id', '=', site.id),
            ('state', 'not in', closed),
        ])
        latest_alert = self.env['cc.alert'].search(
            [('site_id', '=', site.id)], order='write_date desc, id desc', limit=1,
        )
        latest_incident = self.env['cc.incident'].search(
            [('site_id', '=', site.id)], order='write_date desc, id desc', limit=1,
        )
        latest_rec = False
        latest_model = False
        for rec in (latest_alert, latest_incident):
            if not rec:
                continue
            stamp = rec.write_date or rec.create_date
            if not latest_rec or stamp > (latest_rec.write_date or latest_rec.create_date):
                latest_rec = rec
                latest_model = rec._name
        label = ''
        activity_at = False
        if latest_rec:
            activity_at = dt_string(latest_rec.write_date or latest_rec.create_date)
            if latest_model == 'cc.alert':
                label = 'Alert %s' % latest_rec.name
            else:
                label = 'Incident %s' % latest_rec.name
        return {
            'id': site.id,
            'name': site.name,
            'code': site.code,
            'operational_status': site.operational_status,
            'alerts_active': len(alerts),
            'incidents_open': len(incidents),
            'has_emergency': bool(alerts.filtered('is_emergency')),
            'latest_activity_at': activity_at,
            'latest_activity_label': label,
        }

    def _sites_summary(self):
        return [self._monitoring_site(site) for site in self.env['cc.site'].search([], order='name, id')]

    def _recent_activity(self):
        rows = []
        for alert in self.env['cc.alert'].search([], order='write_date desc, id desc', limit=10):
            rows.append({
                'id': alert.id,
                'model': 'cc.alert',
                'name': alert.name,
                'state': alert.state,
                'severity': alert.severity or False,
                'site_id': alert.site_id.id or False,
                'site_name': alert.site_id.name or '',
                'event_type': alert.alert_type or 'Alert',
                'at': dt_string(alert.write_date or alert.create_date),
            })
        for incident in self.env['cc.incident'].search([], order='write_date desc, id desc', limit=10):
            rows.append({
                'id': incident.id,
                'model': 'cc.incident',
                'name': incident.name,
                'state': incident.state,
                'severity': incident.severity or False,
                'site_id': incident.site_id.id or False,
                'site_name': incident.site_id.name or '',
                'event_type': 'Incident',
                'at': dt_string(incident.write_date or incident.create_date),
            })
        rows.sort(key=lambda item: item['at'] or '', reverse=True)
        return rows[:10]

    def _rule_rows(self):
        rules = self.env['cc.escalation.rule'].search([('active', '=', True)], order='level desc, id asc')
        return [{
            'id': rule.id,
            'name': rule.name,
            'level': rule.level,
            'delay_minutes': rule.delay_minutes,
            'mode': rule.mode,
            'site_id': rule.site_id.id or False,
            'user_id': rule.user_id.id or False,
            'group_id': rule.group_id.id or False,
        } for rule in rules]
