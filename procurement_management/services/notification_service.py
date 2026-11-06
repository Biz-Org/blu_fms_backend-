# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, env):
        self.env = env

    def approval_requested(self, request):
        self._send_template(
            'procurement_management.mail_template_pm_approval_requested',
            request,
        )

    def approval_decided(self, request):
        self._send_template(
            'procurement_management.mail_template_pm_approval_decided',
            request,
        )

    def report_ready(self, run, emails):
        return self._send_template(
            'procurement_management.mail_template_pm_report',
            run,
            email_to=emails,
            attachment=run.attachment_id,
        )

    def _send_template(self, xml_id, record, email_to='', attachment=None):
        template = self.env.ref(xml_id, raise_if_not_found=False)
        if not template:
            return 'Mail template %s is missing.' % xml_id
        emails = email_to or self._group_emails(record)
        if not emails:
            return 'No recipient email is available.'
        values = {'email_to': emails}
        if attachment:
            values['attachment_ids'] = [(4, attachment.id)]
        try:
            template.sudo().send_mail(record.id, force_send=False, email_values=values)
        except Exception as exc:
            _logger.exception('Procurement mail could not be queued.')
            return str(exc) or 'Procurement mail could not be queued.'
        return True

    def _group_emails(self, record):
        if record._name != 'procurement.management.approval.request':
            if record._name == 'procurement.management.report.run':
                return record.definition_id.recipient_emails or ''
            return ''
        groups = record.decision_ids.filtered(
            lambda row: row.decision == 'pending'
        ).mapped('group_id')
        if not groups and record.state in ('approved', 'rejected', 'returned'):
            requester = record.requester_id
            return requester.email or requester.partner_id.email or ''
        users = self.env['res.users'].sudo().search([('groups_id', 'in', groups.ids)])
        emails = [user.email or user.partner_id.email for user in users]
        return ','.join(sorted({email for email in emails if email}))
