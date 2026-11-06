# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.utility_management.models.selections import SECRET_MARKERS
from odoo.addons.utility_management.services.common import (
    observed_end,
    observed_start,
    page_window,
    require_manager,
)

_VIEW_MARKERS = SECRET_MARKERS + (
    'email', 'e-mail', 'body', 'subject', 'html', 'template_body', 'passwd', 'pwd',
)


class AuditService(object):
    def __init__(self, env):
        self.env = env

    def log(self, event_type, record, outcome, summary, before=None, after=None, company=None):
        company = company or (record.company_id if record and 'company_id' in record._fields else False)
        if not company:
            company = self.env.company
        user = self.env.user
        if not user or user._is_public():
            user = self.env.ref('base.user_root')
        event = self.env['utility.management.audit.event'].sudo().with_context(
            utility_audit_service=True,
        ).create({
            'occurred_at': fields.Datetime.now(),
            'user_id': user.id,
            'company_id': company.id,
            'event_type': event_type,
            'model_name': record._name if record else 'utility.management.config',
            'res_id': record.id if record and record.id else 0,
            'outcome': outcome,
            'summary': summary,
            'data_before': self._clean(before),
            'data_after': self._clean(after),
        })
        return event

    def _clean(self, payload):
        if isinstance(payload, datetime):
            return fields.Datetime.to_string(payload)
        if isinstance(payload, date):
            return fields.Date.to_string(payload)
        if not isinstance(payload, dict):
            return payload or False
        cleaned = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_MARKERS):
                continue
            cleaned[key] = self._clean(value)
        return cleaned

    def list(self, filters=None):
        require_manager(self.env, 'Only a Facility Manager can review the audit log.')
        filters = filters or {}
        domain = self._domain(filters)
        model = self.env['utility.management.audit.event']
        total = model.search_count(domain)
        window = page_window(filters)
        if window:
            limit, offset = window
            events = model.search(domain, limit=limit, offset=offset)
        else:
            limit, offset = 0, 0
            events = model.search(domain)
        return {
            'rows': [self._row(event) for event in events],
            'total_count': total,
            'limit': limit,
            'offset': offset,
        }

    def get(self, event_id):
        require_manager(self.env, 'Only a Facility Manager can review the audit log.')
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            raise UserError('Audit event was not found.')
        event = self.env['utility.management.audit.event'].browse(event_id)
        if not event.exists():
            raise UserError('Audit event was not found.')
        event.check_access('read')
        return self._detail(event)

    def _domain(self, filters):
        domain = []
        if filters.get('event_type'):
            domain.append(('event_type', '=', filters['event_type']))
        if filters.get('outcome'):
            domain.append(('outcome', '=', filters['outcome']))
        user_id = self._as_int(filters.get('user_id'))
        if user_id:
            domain.append(('user_id', '=', user_id))
        if filters.get('model_name'):
            domain.append(('model_name', '=', filters['model_name']))
        if filters.get('date_from'):
            domain.append(('occurred_at', '>=', observed_start(filters['date_from'])))
        if filters.get('date_to'):
            domain.append(('occurred_at', '<=', observed_end(filters['date_to'])))
        term = filters.get('search')
        if term:
            term = str(term)
            clauses = ['|', ('summary', 'ilike', term), ('model_name', 'ilike', term)]
            if term.isdigit():
                clauses = ['|'] + [('res_id', '=', int(term))] + clauses
            domain = clauses + domain
        return domain

    def _row(self, event):
        return {
            'id': event.id,
            'occurred_at': fields.Datetime.to_string(event.occurred_at),
            'event_type': event.event_type,
            'model_name': event.model_name,
            'res_id': event.res_id,
            'user_id': event.user_id.id,
            'user_name': self._public_text(event.user_id.name, 'User'),
            'company_id': event.company_id.id,
            'company_name': self._public_text(event.company_id.name, ''),
            'outcome': event.outcome,
            'summary': self._public_text(event.summary, 'Audit event recorded.'),
        }

    def _detail(self, event):
        payload = self._row(event)
        payload['data_before'] = self._public_value(event.data_before) or {}
        payload['data_after'] = self._public_value(event.data_after) or {}
        return payload

    def _public_value(self, value):
        if isinstance(value, dict):
            cleaned = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in _VIEW_MARKERS):
                    continue
                cleaned[key] = self._public_value(item)
            return cleaned
        if isinstance(value, list):
            return [self._public_value(item) for item in value]
        if isinstance(value, str) and ('@' in value or '<' in value):
            return '[redacted]'
        return value

    def _public_text(self, value, fallback):
        text = value or ''
        if not isinstance(text, str):
            text = str(text)
        if '@' in text or '<' in text:
            return fallback
        return text

    def _as_int(self, value):
        if value in (None, False, ''):
            return False
        try:
            return int(value)
        except (TypeError, ValueError):
            return False
