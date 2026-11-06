# -*- coding: utf-8 -*-
import csv
import io

from odoo.exceptions import AccessError

from .common import has_group


class AuditService:
    def __init__(self, env):
        self.env = env

    def search(self, limit=80):
        if not has_group(self.env, 'group_procurement_manager'):
            raise AccessError('Only a procurement manager can read the audit log.')
        return self.env['procurement.management.audit.event'].search([], limit=limit, order='id desc')

    def export_csv(self):
        events = self.search(limit=500)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Time', 'User', 'Action', 'Status', 'Model', 'Reference', 'Before', 'After', 'Detail'])
        for event in events:
            writer.writerow([
                event.event_time, event.user_id.name, event.action, event.status,
                event.res_model, event.reference, event.before_value, event.after_value, event.detail,
            ])
        return buffer.getvalue()
