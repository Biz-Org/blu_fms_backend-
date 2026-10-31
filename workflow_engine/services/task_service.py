# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError

from .audit_service import WorkflowAuditService
from .notification_service import WorkflowNotificationService
from .rule_service import WorkflowRuleService


class WorkflowTaskService:
    """Task creation, assignment, completion and escalation entry points."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)
        self.notifications = WorkflowNotificationService(env)
        self.rules = WorkflowRuleService(env)

    def create_for_node(self, execution, step, node):
        config = node.config_json or {}
        if not isinstance(config, dict):
            config = {}
        user, group = self._resolve_assignee(execution, node, config)
        if not user and not group:
            raise UserError('Task assignment could not be resolved for node "%s".' % node.display_name)
        deadline = False
        sla = False
        if config.get('due_hours'):
            try:
                deadline = fields.Datetime.now() + timedelta(hours=float(config['due_hours']))
            except (TypeError, ValueError):
                deadline = False
        if config.get('sla_hours'):
            try:
                sla = fields.Datetime.now() + timedelta(hours=float(config['sla_hours']))
            except (TypeError, ValueError):
                sla = False
        task = self.env['workflow.engine.task'].create({
            'name': config.get('task_name') or node.name or 'Workflow Task',
            'execution_id': execution.id,
            'step_id': step.id,
            'node_id': node.id,
            'user_id': user.id if user else False,
            'group_id': group.id if group else False,
            'priority': str(config.get('priority', '1')),
            'date_deadline': deadline,
            'sla_deadline': sla,
            'state': 'open',
        })
        execution.write({
            'state': 'waiting_task',
            'current_node_id': node.id,
            'current_step_id': step.id,
        })
        step.write({'state': 'waiting'})
        recipients = user if user else self.env['res.users']
        if group and not user:
            recipients = self.env['res.users'].search([('groups_id', 'in', group.id)])
        self.notifications.send(
            channel='in_app',
            recipients=recipients,
            subject='Task assigned: %s' % task.name,
            body='A workflow task has been assigned to you.',
            execution=execution,
            task=task,
        )
        self.audit.log('assign', record=task, execution=execution)
        return task

    def _resolve_assignee(self, execution, node, config):
        Users = self.env['res.users']
        Groups = self.env['res.groups']
        user = Users.browse(config.get('user_id')) if config.get('user_id') else Users
        group = Groups.browse(config.get('group_id')) if config.get('group_id') else Groups
        if user or group:
            return user[:1], group[:1]
        context = self.rules.build_context(execution=execution)
        match = self.rules.first_match(
            'assignment',
            context=context,
            definition=execution.definition_id,
            version=execution.version_id,
        )
        if match:
            # Assignment rule value may encode user:<id> or group:<id>
            raw = (match.value or '').strip()
            if raw.startswith('user:'):
                return Users.browse(int(raw.split(':', 1)[1])), Groups
            if raw.startswith('group:'):
                return Users, Groups.browse(int(raw.split(':', 1)[1]))
            if raw.isdigit():
                return Users.browse(int(raw)), Groups
        return Users, Groups

    def assign(self, task, user_id=False, group_id=False):
        task._we_require_manager()
        vals = {}
        if user_id is not False:
            vals['user_id'] = user_id
        if group_id is not False:
            vals['group_id'] = group_id
        if vals:
            task.write(vals)
        for rec in task:
            self.audit.log('assign', record=rec, execution=rec.execution_id)
        return task

    def reassign(self, task, user_id=False, group_id=False):
        task._we_require_manager()
        self.assign(task, user_id=user_id, group_id=group_id)
        for rec in task:
            self.audit.log('reassign', record=rec, execution=rec.execution_id)
        return task

    def start(self, task):
        for rec in task:
            self._assert_assignee(rec)
            if rec.state != 'open':
                raise UserError('Only open tasks can be started.')
            rec.sudo().write({'state': 'in_progress'})
            self.audit.log('update', record=rec, execution=rec.execution_id, details='task started')
        return task

    def complete(self, task):
        for rec in task:
            self._assert_assignee(rec)
            if rec.state == 'done':
                raise UserError('Task is already done.')
            if rec.state not in ('open', 'in_progress', 'escalated'):
                raise UserError('Invalid task state transition.')
            # Permission checked; continue with sudo for engine writes.
            rec = rec.sudo()
            if rec.state == 'open':
                rec.with_context(mail_notrack=True, tracking_disable=True).write({'state': 'in_progress'})
            rec.with_context(mail_notrack=True, tracking_disable=True).write({'state': 'done'})
            self.audit.log('complete', record=rec, execution=rec.execution_id)
            if rec.step_id:
                rec.step_id.write({
                    'state': 'done',
                    'date_end': fields.Datetime.now(),
                })
            if rec.execution_id.state in ('waiting_task', 'escalated'):
                rec.execution_id.write({'state': 'running'})
            from .execution_service import WorkflowExecutionService
            WorkflowExecutionService(rec.env).advance(rec.execution_id)
        return task

    def _assert_assignee(self, task):
        if self.env.su:
            return
        user = self.env.user
        if task.user_id and task.user_id == user:
            return
        if task.group_id and task.group_id in user.groups_id:
            return
        # Managers may complete for operational recovery
        if user.has_group('workflow_engine.group_we_manager'):
            return
        raise AccessError('You can only complete tasks assigned to you.')
