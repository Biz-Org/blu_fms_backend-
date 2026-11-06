# -*- coding: utf-8 -*-
import csv
import json
from io import StringIO

from odoo import SUPERUSER_ID
from odoo.exceptions import AccessError, UserError


class DocumentAuditService:
    def __init__(self, env):
        self.env = env

    def _audit_env(self):
        return self.env(user=SUPERUSER_ID, su=True)

    def log(self, event_type, document=None, version_name=None, metadata=None, user=None):
        if event_type == 'viewed':
            return self.env['document.management.audit.event']
        values = {
            'event_type': event_type,
            'user_id': (user or self.env.user).id,
            'version_name': version_name or False,
            'metadata': json.dumps(metadata) if metadata else False,
            'company_id': (document.company_id.id if document else self.env.company.id),
        }
        if document:
            values['document_id'] = document.id
            values['document_name'] = document.name
        event = self._audit_env()['document.management.audit.event'].create(values)
        event.flush_recordset()
        return event

    def deny(self, document, message, version_name=None, metadata=None):
        self.log(
            'unauthorized_access',
            document=document,
            version_name=version_name,
            metadata=metadata,
        )
        raise AccessError(message)

    def _authorized_events(self, domain):
        from .access_service import DocumentAccessService
        events = self.env['document.management.audit.event'].sudo().search(
            domain,
            order='timestamp desc, id desc',
        )
        access = DocumentAccessService(self.env)
        return events.filtered(
            lambda event: not event.document_id or access.can(event.document_id, 'read')
        )

    def get_audit_data(self, filters=None, offset=0, limit=50):
        filters = filters or {}
        domain = []
        if filters.get('event_type') or filters.get('action'):
            domain.append(('event_type', '=', filters.get('event_type') or filters.get('action')))
        if filters.get('document_id'):
            domain.append(('document_id', '=', filters['document_id']))
        if filters.get('document'):
            domain.append(('document_name', 'ilike', filters['document']))
        if filters.get('user_id'):
            domain.append(('user_id', '=', filters['user_id']))
        if filters.get('user'):
            domain.append(('user_id.name', 'ilike', filters['user']))
        if filters.get('date_from'):
            domain.append(('timestamp', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('timestamp', '<=', filters['date_to']))
        authorized = self._authorized_events(domain)
        offset = int(offset or 0)
        limit = int(limit or 50)
        events = authorized[offset:offset + limit]
        total = len(authorized)
        rows = [{
            'id': event.id,
            'timestamp': event.timestamp,
            'user': event.user_id.name if event.user_id else False,
            'document': event.document_name,
            'document_id': event.document_id.id if event.document_id else False,
            'action': event.event_type,
            'version': event.version_name,
        } for event in events]
        kpis = {
            'activity_events': total,
            'uploads': len(authorized.filtered(lambda event: event.event_type == 'uploaded')),
            'downloads': len(authorized.filtered(lambda event: event.event_type == 'downloaded')),
            'shares': len(authorized.filtered(lambda event: event.event_type == 'access_changed')),
        }
        action_names = authorized.mapped('event_type')
        user_names = authorized.mapped('user_id.name')
        breakdown = []
        for action in dict.fromkeys(action_names):
            breakdown.append({
                'action': action,
                'count': action_names.count(action),
            })
        top_users = []
        for name in dict.fromkeys(user_names):
            if name:
                top_users.append({'name': name, 'count': user_names.count(name)})
        top_users = sorted(top_users, key=lambda item: item['count'], reverse=True)[:5]
        alerts = authorized.filtered(lambda event: event.event_type == 'unauthorized_access')[:8]
        return {
            'kpis': kpis,
            'rows': rows,
            'breakdown': breakdown,
            'top_users': top_users,
            'security_alerts': [{
                'id': event.id,
                'timestamp': event.timestamp,
                'user': event.user_id.name if event.user_id else False,
                'document': event.document_name,
                'action': event.event_type,
            } for event in alerts],
            'total': total,
            'offset': offset,
            'limit': limit,
        }

    def export_audit(self, filters=None):
        data = self.get_audit_data(filters, offset=0, limit=5000)
        handle = StringIO()
        writer = csv.writer(handle)
        writer.writerow(['timestamp', 'user', 'document', 'action', 'version'])
        for row in data['rows']:
            writer.writerow([
                row['timestamp'] or '',
                row['user'] or '',
                row['document'] or '',
                row['action'] or '',
                row['version'] or '',
            ])
        return {
            'filename': 'document-audit.csv',
            'csv': handle.getvalue(),
        }
