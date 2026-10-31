# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .audit_service import WorkflowAuditService


class WorkflowNotificationService:
    """Dispatch Workflow Engine notifications via Odoo mail and log results."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)

    def send(
        self,
        *,
        channel='in_app',
        recipients=None,
        subject=None,
        body=None,
        execution=None,
        task=None,
        approval=None,
        mail_template=None,
        reminder=False,
        escalation=False,
    ):
        recipients = recipients or self.env['res.users']
        if channel not in ('in_app', 'email'):
            return self._log_failure(
                name=subject or 'Invalid channel',
                channel=channel if channel in ('in_app', 'email') else 'in_app',
                execution=execution,
                task=task,
                approval=approval,
                error='Unsupported notification channel: %s' % channel,
                reminder=reminder,
                escalation=escalation,
            )
        logs = self.env['workflow.engine.notification.log']
        subject = subject or 'Workflow Engine notification'
        body = body or subject
        for user in recipients:
            log = self.env['workflow.engine.notification.log'].sudo().create({
                'name': subject,
                'execution_id': execution.id if execution else False,
                'task_id': task.id if task else False,
                'approval_id': approval.id if approval else False,
                'channel': channel,
                'state': 'queued',
                'user_id': user.id,
                'partner_id': user.partner_id.id,
                'mail_template_id': mail_template.id if mail_template else False,
                'reminder': reminder,
                'escalation': escalation,
                'company_id': (
                    execution.company_id.id if execution else self.env.company.id
                ),
            })
            try:
                if channel == 'in_app':
                    partner = user.partner_id
                    self.env['mail.message'].sudo().create({
                        'message_type': 'notification',
                        'subtype_id': self.env.ref('mail.mt_note').id,
                        'subject': subject,
                        'body': body,
                        'partner_ids': [(4, partner.id)] if partner else [],
                        'model': execution._name if execution else False,
                        'res_id': execution.id if execution else False,
                        'author_id': self.env.user.partner_id.id,
                    })
                else:
                    email_to = user.email_formatted or user.email or user.login
                    if not email_to or '@' not in str(email_to):
                        raise UserError('Recipient has no email address.')
                    mail = self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': '<p>%s</p>' % body,
                        'email_to': email_to,
                        'auto_delete': True,
                    })
                    # Avoid hard failure when outgoing mail server is unset.
                    try:
                        mail.send()
                    except Exception:
                        mail.write({'state': 'exception'})
                        raise
                log.write({
                    'state': 'sent',
                    'date_sent': fields.Datetime.now(),
                })
            except Exception as exc:  # noqa: BLE001 - isolate notification failures
                log.write({
                    'state': 'failed',
                    'error_message': str(exc),
                })
                self.audit.log(
                    'failure',
                    record=log,
                    execution=execution,
                    details='notification failed: %s' % exc,
                )
            logs |= log
        return logs

    def _log_failure(self, *, name, channel, execution, task, approval, error, reminder, escalation):
        log = self.env['workflow.engine.notification.log'].sudo().create({
            'name': name,
            'execution_id': execution.id if execution else False,
            'task_id': task.id if task else False,
            'approval_id': approval.id if approval else False,
            'channel': channel,
            'state': 'failed',
            'error_message': error,
            'reminder': reminder,
            'escalation': escalation,
            'company_id': execution.company_id.id if execution else self.env.company.id,
        })
        self.audit.log('failure', record=log, execution=execution, details=error)
        return log
