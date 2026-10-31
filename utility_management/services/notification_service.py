# -*- coding: utf-8 -*-
from .audit_service import AuditService
from .common import config_for

ALERT_TEMPLATE = 'utility_management.mail_template_utility_alert'


class NotificationService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)

    def notify_record(self, record, users, summary):
        config = config_for(self.env, record.company_id)
        if not config or not config.mail_notifications:
            self._audit_notification(
                record, 'skipped', 'notifications_disabled', attempted=False,
            )
            return {'sent': False, 'error': False, 'skipped': True}
        recipients = self._company_recipients(record, users)
        if not recipients:
            self._audit_notification(
                record, 'skipped', 'recipient_unavailable', attempted=False,
            )
            return {'sent': False, 'error': False, 'skipped': True}
        self._schedule_activities(record, recipients, summary)
        if record._name != 'utility.management.alert':
            return {'sent': True, 'error': False, 'skipped': False}
        emails = ','.join(recipients.mapped('email'))
        return self.send_template(record, ALERT_TEMPLATE, emails)

    def send_template(self, record, template_xmlid, email_to):
        config = config_for(self.env, record.company_id)
        addresses = [item.strip() for item in (email_to or '').split(',') if item.strip()]
        if not config or not config.mail_notifications:
            self._audit_notification(
                record, 'skipped', 'notifications_disabled', attempted=False,
                template_xmlid=template_xmlid,
            )
            return {'sent': False, 'error': False, 'skipped': True}
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            self._audit_notification(
                record, 'failed', 'template_missing', attempted=True,
                template_xmlid=template_xmlid,
            )
            return {'sent': False, 'error': 'Mail template is missing.', 'skipped': False}
        if not addresses:
            self._audit_notification(
                record, 'skipped', 'recipient_unavailable', attempted=False,
                template_xmlid=template_xmlid,
            )
            return {'sent': False, 'error': False, 'skipped': True}
        self._audit_notification(
            record, 'attempted', attempted=True, template_xmlid=template_xmlid,
            recipient_count=len(addresses),
        )
        try:
            with self.env.cr.savepoint():
                template.sudo().send_mail(record.id, force_send=False, email_values={
                    'email_to': ','.join(addresses),
                })
        except Exception as exc:
            reason = self._safe_reason(exc)
            self._audit_notification(
                record, 'failed', reason, attempted=True,
                template_xmlid=template_xmlid, recipient_count=len(addresses),
            )
            return {'sent': False, 'error': reason, 'skipped': False}
        self._audit_notification(
            record, 'sent', attempted=True, template_xmlid=template_xmlid,
            recipient_count=len(addresses),
        )
        return {'sent': True, 'error': False, 'skipped': False}

    def _company_recipients(self, record, users):
        if not users:
            return self.env['res.users']
        company = record.company_id
        return users.filtered(lambda user: user.email and company in user.company_ids)

    def _schedule_activities(self, record, users, summary):
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type or not hasattr(record, 'activity_schedule'):
            return
        for user in users:
            try:
                with self.env.cr.savepoint():
                    record.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=summary,
                    )
            except Exception:
                continue

    def _audit_notification(self, record, status, reason=False, attempted=False,
                            template_xmlid=False, recipient_count=0):
        summaries = {
            'attempted': 'Notification attempted.',
            'sent': 'Notification sent.',
            'failed': 'Notification failed.',
            'skipped': 'Notification skipped.',
        }
        after = {
            'notification_status': status,
            'attempted': bool(attempted),
            'recipient_count': recipient_count,
        }
        if reason:
            after['reason'] = self._safe_reason(reason)
        if template_xmlid:
            after['template'] = template_xmlid
        if record._name == 'utility.management.alert':
            event_type = 'alert_change'
        elif record._name == 'utility.management.report.run':
            event_type = 'report_execution'
        else:
            event_type = 'config_change'
        outcome = 'success' if status == 'sent' else 'denied'
        self.audit.log(
            event_type, record, outcome, summaries[status], after=after,
        )

    def _safe_reason(self, reason):
        text = ' '.join(str(reason or '').split())
        lowered = text.lower()
        if (
            not text
            or '@' in text
            or '<' in text
            or 'body_html' in lowered
            or 'email_to' in lowered
            or 'subject' in lowered
        ):
            return 'delivery_failed'
        return text[:180]
