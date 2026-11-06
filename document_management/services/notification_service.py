# -*- coding: utf-8 -*-
from odoo.exceptions import UserError


class DocumentNotificationService:
    def __init__(self, env):
        self.env = env

    def create_notification(self, user, document, kind, body):
        if not user:
            return self.env['document.management.notification']
        # Expiry overlays are idempotent. Other kinds must still notify each event.
        if kind in ('expiry_soon', 'expired'):
            existing = self.env['document.management.notification'].sudo().search([
                ('user_id', '=', user.id),
                ('document_id', '=', document.id if document else False),
                ('kind', '=', kind),
                ('is_read', '=', False),
            ], limit=1)
            if existing:
                return existing
        return self.env['document.management.notification'].sudo().create({
            'name': body,
            'user_id': user.id,
            'document_id': document.id if document else False,
            'kind': kind,
            'body': body,
            'company_id': document.company_id.id if document else self.env.company.id,
        })

    def ensure_expiry_notifications(self, documents=None):
        domain = [
            ('expiry_notify', '=', True),
            ('expiry_status', 'in', ['expiring_soon', 'expired']),
            ('state', '!=', 'archived'),
        ]
        if documents:
            domain.append(('id', 'in', documents.ids))
        records = documents or self.env['document.management.document'].search(domain)
        for document in records:
            kind = 'expired' if document.expiry_status == 'expired' else 'expiry_soon'
            self.create_notification(
                document.owner_id,
                document,
                kind,
                '%s is %s' % (document.name, kind.replace('_', ' ')),
            )
        return True

    def list_notifications(self):
        items = self.env['document.management.notification'].search([
            ('user_id', '=', self.env.user.id),
        ])
        return {
            'items': [{
                'id': item.id,
                'name': item.name,
                'kind': item.kind,
                'body': item.body,
                'is_read': item.is_read,
                'document_id': item.document_id.id if item.document_id else False,
            } for item in items],
        }

    def mark_read(self, notification_id):
        notification = self.env['document.management.notification'].browse(notification_id)
        if not notification.exists() or notification.user_id != self.env.user:
            raise UserError('Notification not found.')
        notification.write({'is_read': True})
        return True
