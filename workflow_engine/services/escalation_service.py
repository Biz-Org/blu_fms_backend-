# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

from .audit_service import WorkflowAuditService
from .notification_service import WorkflowNotificationService


class WorkflowEscalationService:
    """Automatic and manual escalation processing."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)
        self.notifications = WorkflowNotificationService(env)

    def escalate(self, *, task=None, approval=None, rule=None, automatic=False, note=None):
        if not automatic:
            if not self.env.su and not self.env.user.has_group('workflow_engine.group_we_manager'):
                raise UserError('Only Workflow Engine Managers can escalate manually.')
        if not task and not approval:
            raise UserError('Escalation requires a task or approval request.')
        execution = task.execution_id if task else approval.execution_id
        if execution.state in ('completed', 'failed'):
            raise UserError('Cannot escalate a completed or failed execution.')
        rule = rule or self._find_rule(execution, task=task, approval=approval)
        # Duplicate protection: same rule + target + open execution
        domain = [
            ('execution_id', '=', execution.id),
            ('rule_id', '=', rule.id if rule else False),
        ]
        if task:
            domain.append(('task_id', '=', task.id))
        if approval:
            domain.append(('approval_id', '=', approval.id))
        existing = self.env['workflow.engine.escalation.event'].search(domain, limit=1)
        if existing:
            return existing
        recipient_user = rule.user_id if rule else False
        recipient_group = rule.group_id if rule else False
        event = self.env['workflow.engine.escalation.event'].create({
            'name': 'Escalation: %s' % execution.name,
            'execution_id': execution.id,
            'task_id': task.id if task else False,
            'approval_id': approval.id if approval else False,
            'rule_id': rule.id if rule else False,
            'level': rule.level if rule else 1,
            'date_triggered': fields.Datetime.now(),
            'user_id': recipient_user.id if recipient_user else False,
            'group_id': recipient_group.id if recipient_group else False,
            'automatic': automatic,
            'state': 'triggered',
            'note': note or '',
        })
        if task and task.state != 'done':
            task.write({'state': 'escalated'})
        execution.write({'state': 'escalated'})
        if rule and rule.notify:
            recipients = recipient_user
            if recipient_group and not recipient_user:
                recipients = self.env['res.users'].search([
                    ('groups_id', 'in', recipient_group.id),
                ])
            if recipients:
                logs = self.notifications.send(
                    channel='in_app',
                    recipients=recipients,
                    subject='Escalation: %s' % execution.name,
                    body=note or 'A workflow item has been escalated.',
                    execution=execution,
                    task=task,
                    approval=approval,
                    escalation=True,
                )
                if logs and all(log.state == 'sent' for log in logs):
                    event.write({'state': 'notified'})
        self.audit.log('escalate', record=event, execution=execution, details=note or '')
        return event

    def _find_rule(self, execution, task=None, approval=None):
        target = 'task' if task else 'approval'
        domain = [
            ('active', '=', True),
            ('target_type', '=', target),
            '|',
            ('definition_id', '=', False),
            ('definition_id', '=', execution.definition_id.id),
        ]
        return self.env['workflow.engine.escalation.rule'].search(
            domain, order='priority, id', limit=1,
        )

    def process(self):
        """Cron entry: process overdue tasks and approvals without aborting the batch."""
        now = fields.Datetime.now()
        processed = self.env['workflow.engine.escalation.event']
        tasks = self.env['workflow.engine.task'].search([
            ('state', 'in', ['open', 'in_progress']),
            '|',
            ('date_deadline', '!=', False),
            ('sla_deadline', '!=', False),
        ])
        for task in tasks:
            try:
                rule = self._matching_rule_for_task(task, now)
                if not rule:
                    continue
                processed |= self.escalate(task=task, rule=rule, automatic=True)
            except Exception as exc:  # noqa: BLE001
                self.audit.log(
                    'failure',
                    record=task,
                    execution=task.execution_id,
                    details='escalation cron task error: %s' % exc,
                )
        approvals = self.env['workflow.engine.approval.request'].search([
            ('state', '=', 'pending'),
        ])
        for approval in approvals:
            try:
                rule = self._matching_rule_for_approval(approval, now)
                if not rule:
                    continue
                processed |= self.escalate(approval=approval, rule=rule, automatic=True)
            except Exception as exc:  # noqa: BLE001
                self.audit.log(
                    'failure',
                    record=approval,
                    execution=approval.execution_id,
                    details='escalation cron approval error: %s' % exc,
                )
        return processed

    def _matching_rule_for_task(self, task, now):
        rules = self.env['workflow.engine.escalation.rule'].search([
            ('active', '=', True),
            ('mode', '=', 'automatic'),
            ('target_type', '=', 'task'),
            '|',
            ('definition_id', '=', False),
            ('definition_id', '=', task.execution_id.definition_id.id),
        ], order='priority, id')
        for rule in rules:
            if rule.node_id and task.node_id and rule.node_id != task.node_id:
                continue
            baseline = task.sla_deadline or task.date_deadline or task.create_date
            if not baseline:
                continue
            due = fields.Datetime.from_string(baseline) if isinstance(baseline, str) else baseline
            threshold = due
            if not task.sla_deadline and not task.date_deadline:
                threshold = due + timedelta(minutes=rule.delay_minutes or 0)
            if now >= threshold:
                return rule
        return False

    def _matching_rule_for_approval(self, approval, now):
        rules = self.env['workflow.engine.escalation.rule'].search([
            ('active', '=', True),
            ('mode', '=', 'automatic'),
            ('target_type', '=', 'approval'),
            '|',
            ('definition_id', '=', False),
            ('definition_id', '=', approval.execution_id.definition_id.id),
        ], order='priority, id')
        for rule in rules:
            baseline = approval.date_requested or approval.create_date
            due = fields.Datetime.from_string(baseline) if isinstance(baseline, str) else baseline
            threshold = due + timedelta(minutes=rule.delay_minutes or 0)
            if now >= threshold:
                return rule
        return False
