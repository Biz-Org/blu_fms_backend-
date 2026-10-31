# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError

from .audit_service import WorkflowAuditService
from .notification_service import WorkflowNotificationService
from .rule_service import WorkflowRuleService


class WorkflowApprovalService:
    """Approval hierarchy resolution and request lifecycle."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)
        self.notifications = WorkflowNotificationService(env)
        self.rules = WorkflowRuleService(env)

    def resolve_hierarchy(self, node, execution):
        if node.hierarchy_id and node.hierarchy_id.active:
            return node.hierarchy_id
        context = self.rules.build_context(execution=execution)
        match = self.rules.first_match(
            'approval_routing',
            context=context,
            definition=execution.definition_id,
            version=execution.version_id,
        )
        if match and match.hierarchy_id and match.hierarchy_id.active:
            return match.hierarchy_id
        raise UserError('No active approval hierarchy could be resolved for this node.')

    def create_requests(self, execution, step, node):
        hierarchy = self.resolve_hierarchy(node, execution)
        levels = hierarchy.level_ids.filtered('active').sorted('sequence')
        if not levels:
            raise UserError('Approval hierarchy "%s" has no active levels.' % hierarchy.display_name)
        first_level = levels[0]
        requests = self._create_level_requests(execution, step, hierarchy, first_level)
        if not requests:
            raise UserError('No approvers configured for level %s.' % first_level.sequence)
        execution.write({
            'state': 'waiting_approval',
            'current_node_id': node.id,
            'current_step_id': step.id,
        })
        step.write({'state': 'waiting'})
        recipients = requests.mapped('user_id')
        self.notifications.send(
            channel='in_app',
            recipients=recipients,
            subject='Approval required: %s' % execution.name,
            body='Please review workflow approval request.',
            execution=execution,
            approval=requests[:1],
        )
        self.audit.log('create', record=requests[:1], execution=execution, details='approval requests')
        return requests

    def _create_level_requests(self, execution, step, hierarchy, level):
        Approver = self.env['workflow.engine.approver'].sudo()
        Request = self.env['workflow.engine.approval.request'].sudo()
        approvers = level.sudo().approver_ids.filtered('active')
        primary = approvers.filtered(lambda a: not a.is_fallback)
        if not primary:
            primary = approvers.filtered('is_fallback')
        requests = Request
        for approver in primary:
            if not approver.user_id and not approver.group_id:
                continue
            requests |= Request.create({
                'name': '%s / L%s' % (execution.name, level.sequence),
                'execution_id': execution.id,
                'step_id': step.id if step else False,
                'hierarchy_id': hierarchy.id,
                'level_id': level.id,
                'user_id': approver.user_id.id,
                'group_id': approver.group_id.id,
                'state': 'pending',
            })
        return requests

    def _assert_authorized_approver(self, request):
        user = self.env.user
        if self.env.su:
            return
        if request.user_id and request.user_id == user:
            return
        if request.group_id and request.group_id in user.groups_id:
            return
        raise AccessError('You are not an authorized approver for this request.')

    def approve(self, request, comment=None):
        request.ensure_one()
        self._assert_authorized_approver(request)
        if request.state != 'pending':
            raise UserError('Only pending approval requests can be approved.')
        # Access checked above; engine progression uses sudo for internal records.
        request = request.sudo()
        request.write({
            'state': 'approved',
            'comment': comment if comment is not None else request.comment,
            'decided_by': self.env.user.id,
            'date_decided': fields.Datetime.now(),
        })
        self.audit.log('approve', record=request, execution=request.execution_id)
        return self._after_decision(request)

    def reject(self, request, comment=None):
        request.ensure_one()
        self._assert_authorized_approver(request)
        if request.state != 'pending':
            raise UserError('Only pending approval requests can be rejected.')
        request = request.sudo()
        request.write({
            'state': 'rejected',
            'comment': comment if comment is not None else request.comment,
            'decided_by': self.env.user.id,
            'date_decided': fields.Datetime.now(),
        })
        execution = request.execution_id
        step = request.step_id
        if step:
            step.write({
                'state': 'failed',
                'date_end': fields.Datetime.now(),
                'error_message': 'Approval rejected',
            })
        execution.write({
            'state': 'failed',
            'date_end': fields.Datetime.now(),
            'error_message': 'Approval rejected%s' % (
                (': %s' % comment) if comment else ''
            ),
        })
        self.audit.log('reject', record=request, execution=execution)
        self.audit.log('failure', record=execution, execution=execution, details='approval rejected')
        return execution

    def _after_decision(self, request):
        # request is already sudo'd by approve()
        execution = request.execution_id
        level = request.level_id
        hierarchy = request.hierarchy_id
        level_requests = execution.approval_request_ids.filtered(
            lambda r: r.level_id == level
        )
        if not self._level_satisfied(level, level_requests):
            return execution
        next_levels = hierarchy.level_ids.filtered(
            lambda l: l.active and l.sequence > level.sequence
        ).sorted('sequence')
        if next_levels:
            nxt = next_levels[0]
            created = self._create_level_requests(execution, request.step_id, hierarchy, nxt)
            if not created:
                raise UserError('No approvers configured for next approval level.')
            recipients = created.mapped('user_id')
            self.notifications.send(
                channel='in_app',
                recipients=recipients,
                subject='Approval required: %s' % execution.name,
                body='Please review the next approval level.',
                execution=execution,
                approval=created[:1],
            )
            return execution
        if request.step_id:
            request.step_id.write({
                'state': 'done',
                'date_end': fields.Datetime.now(),
            })
        execution.write({'state': 'running'})
        from .execution_service import WorkflowExecutionService
        return WorkflowExecutionService(execution.env).advance(execution)

    def _level_satisfied(self, level, level_requests):
        approved = level_requests.filtered(lambda r: r.state == 'approved')
        pending = level_requests.filtered(lambda r: r.state == 'pending')
        rejected = level_requests.filtered(lambda r: r.state == 'rejected')
        if rejected:
            return False
        if level.mode == 'sequential':
            return bool(approved) and not pending
        threshold = level.threshold or 1
        return len(approved) >= threshold
