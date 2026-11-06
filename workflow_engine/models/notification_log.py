# -*- coding: utf-8 -*-
from odoo import fields, models

CHANNELS = [
    ('in_app', 'In-app'),
    ('email', 'Email'),
]

LOG_STATES = [
    ('queued', 'Queued'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
]


class WorkflowEngineNotificationLog(models.Model):
    _name = 'workflow.engine.notification.log'
    _description = 'Notification Log'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    execution_id = fields.Many2one(
        'workflow.engine.execution',
        ondelete='cascade',
        index=True,
    )
    task_id = fields.Many2one('workflow.engine.task', ondelete='set null')
    approval_id = fields.Many2one('workflow.engine.approval.request', ondelete='set null')
    channel = fields.Selection(CHANNELS, required=True, index=True)
    state = fields.Selection(LOG_STATES, default='queued', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Recipient User', index=True)
    partner_id = fields.Many2one('res.partner', string='Recipient Partner', index=True)
    mail_template_id = fields.Many2one('mail.template', ondelete='set null')
    mail_message_id = fields.Many2one('mail.message', ondelete='set null')
    mail_mail_id = fields.Many2one('mail.mail', ondelete='set null')
    date_sent = fields.Datetime()
    error_message = fields.Text()
    reminder = fields.Boolean()
    escalation = fields.Boolean()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
