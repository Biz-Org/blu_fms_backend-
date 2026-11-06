# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .approval_service import WorkflowApprovalService
from .audit_service import WorkflowAuditService
from .notification_service import WorkflowNotificationService
from .rule_service import WorkflowRuleService
from .task_service import WorkflowTaskService

SAFE_ACTIONS = frozenset({'noop', 'set_payload'})
MAX_STEPS = 200


class WorkflowExecutionService:
    """Workflow graph traversal and execution lifecycle."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)
        self.rules = WorkflowRuleService(env)
        self.approvals = WorkflowApprovalService(env)
        self.tasks = WorkflowTaskService(env)
        self.notifications = WorkflowNotificationService(env)

    def create_execution(self, version, *, source_module=None, source_model=None,
                         event_code=None, record=None, payload=None):
        if version.state != 'active':
            raise UserError('Only active workflow versions can be executed.')
        definition = version.definition_id
        if definition.state != 'active':
            raise UserError('Only active workflow definitions can be executed.')
        payload = payload if isinstance(payload, dict) else (payload or {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            payload = {'value': payload}
        name = self.env['ir.sequence'].next_by_code('workflow.engine.execution') or 'WE-EXEC'
        execution = self.env['workflow.engine.execution'].create({
            'name': name,
            'definition_id': definition.id,
            'version_id': version.id,
            'source_module': source_module,
            'source_model': source_model,
            'source_res_id': record.id if record is not None else False,
            'event_code': event_code,
            'payload_json': payload,
            'state': 'running',
            'company_id': definition.company_id.id or self.env.company.id,
            'site_ref': payload.get('site_ref') or payload.get('site'),
        })
        self.audit.log('create', record=execution, execution=execution, details='execution created')
        return execution

    def start(self, execution):
        execution.ensure_one()
        if execution.state not in ('running',):
            raise UserError('Execution cannot be started from state %s.' % execution.state)
        start_nodes = execution.version_id.node_ids.filtered(
            lambda n: n.node_type == 'start' and n.active
        )
        if len(start_nodes) != 1:
            return self.fail(
                execution,
                'Workflow version must have exactly one active start node.',
            )
        return self._process_node(execution, start_nodes)

    def advance(self, execution):
        execution.ensure_one()
        if execution.state in ('completed', 'failed'):
            return execution
        if execution.state in ('waiting_approval', 'waiting_task'):
            return execution
        if execution.state == 'escalated':
            execution.write({'state': 'running'})
        current = execution.current_node_id
        if not current:
            return self.start(execution)
        nxt = self._next_node(execution, current)
        if not nxt:
            return self.fail(execution, 'No outgoing edge from node "%s".' % current.display_name)
        return self._process_node(execution, nxt)

    def _process_node(self, execution, node, depth=0):
        if depth > MAX_STEPS:
            return self.fail(execution, 'Execution aborted: maximum node traversal exceeded.')
        if node.version_id != execution.version_id:
            return self.fail(execution, 'Cross-version graph traversal is not allowed.')
        step = self.env['workflow.engine.execution.step'].create({
            'execution_id': execution.id,
            'node_id': node.id,
            'sequence': len(execution.step_ids) + 1,
            'state': 'running',
            'date_start': fields.Datetime.now(),
            'input_json': execution.payload_json,
        })
        execution.write({
            'current_node_id': node.id,
            'current_step_id': step.id,
            'state': 'running',
        })
        try:
            if node.node_type == 'start':
                step.write({'state': 'done', 'date_end': fields.Datetime.now()})
                nxt = self._next_node(execution, node)
                if not nxt:
                    return self.fail(execution, 'Start node has no outgoing edge.')
                return self._process_node(execution, nxt, depth=depth + 1)

            if node.node_type == 'end':
                step.write({'state': 'done', 'date_end': fields.Datetime.now()})
                return self.complete(execution)

            if node.node_type == 'action':
                self._run_safe_action(execution, node, step)
                step.write({
                    'state': 'done',
                    'date_end': fields.Datetime.now(),
                    'output_json': execution.payload_json,
                })
                nxt = self._next_node(execution, node)
                if not nxt:
                    return self.fail(execution, 'Action node has no outgoing edge.')
                return self._process_node(execution, nxt, depth=depth + 1)

            if node.node_type == 'approval':
                self.approvals.create_requests(execution, step, node)
                return execution

            if node.node_type == 'task':
                self.tasks.create_for_node(execution, step, node)
                return execution

            if node.node_type == 'notification':
                self._send_node_notification(execution, node)
                step.write({'state': 'done', 'date_end': fields.Datetime.now()})
                nxt = self._next_node(execution, node)
                if not nxt:
                    return self.fail(execution, 'Notification node has no outgoing edge.')
                return self._process_node(execution, nxt, depth=depth + 1)

            if node.node_type == 'conditional':
                nxt = self._resolve_conditional(execution, node)
                step.write({
                    'state': 'done',
                    'date_end': fields.Datetime.now(),
                    'output_json': {'next_node_id': nxt.id if nxt else False},
                })
                if not nxt:
                    return self.fail(execution, 'Conditional node could not resolve a branch.')
                return self._process_node(execution, nxt, depth=depth + 1)

            return self.fail(execution, 'Unsupported node type: %s' % node.node_type)
        except Exception as exc:  # noqa: BLE001
            step.write({
                'state': 'failed',
                'date_end': fields.Datetime.now(),
                'error_message': str(exc),
            })
            return self.fail(execution, str(exc))

    def _run_safe_action(self, execution, node, step):
        config = node.config_json or {}
        if not isinstance(config, dict):
            raise UserError('Action node configuration must be a structured object.')
        action = config.get('action') or 'noop'
        if action not in SAFE_ACTIONS:
            raise UserError(
                'Action "%s" is not in the safe action registry. '
                'Arbitrary code execution is not allowed.' % action
            )
        if action == 'noop':
            return
        if action == 'set_payload':
            values = config.get('values') or {}
            if not isinstance(values, dict):
                raise UserError('set_payload values must be a dictionary.')
            payload = dict(execution.payload_json or {})
            payload.update(values)
            execution.write({'payload_json': payload})

    def _send_node_notification(self, execution, node):
        config = node.config_json or {}
        if not isinstance(config, dict):
            config = {}
        Users = self.env['res.users']
        recipients = Users
        if config.get('user_ids'):
            recipients = Users.browse(config['user_ids'])
        elif config.get('user_id'):
            recipients = Users.browse(config['user_id'])
        channel = config.get('channel') or 'in_app'
        self.notifications.send(
            channel=channel,
            recipients=recipients,
            subject=config.get('subject') or node.name,
            body=config.get('body') or node.name,
            execution=execution,
            mail_template=node.mail_template_id,
        )

    def _next_node(self, execution, node):
        edges = node.outgoing_edge_ids.sorted(lambda e: (e.sequence, e.id))
        if not edges:
            return False
        # Non-conditional: first edge
        if node.node_type != 'conditional':
            edge = edges[0]
            if edge.target_node_id.version_id != execution.version_id:
                raise ValidationError('Cross-version graph traversal is not allowed.')
            return edge.target_node_id
        return self._resolve_conditional(execution, node)

    def _resolve_conditional(self, execution, node):
        edges = node.outgoing_edge_ids.sorted(lambda e: (e.sequence, e.id))
        context = self.rules.build_context(execution=execution)
        default = False
        for edge in edges:
            if edge.target_node_id.version_id != execution.version_id:
                raise ValidationError('Cross-version graph traversal is not allowed.')
            if edge.is_default:
                default = edge.target_node_id
                continue
            if edge.rule_id and self.rules.evaluate(edge.rule_id, context=context):
                return edge.target_node_id
            condition = edge.condition_json or {}
            if isinstance(condition, dict) and condition:
                # Structured edge condition: {criterion, operator, value}
                criterion = condition.get('criterion')
                operator = condition.get('operator', '=')
                value = condition.get('value')
                if criterion and operator and value is not None:
                    fake = self.env['workflow.engine.condition.rule'].new({
                        'name': 'edge',
                        'rule_type': 'branch',
                        'criterion': criterion,
                        'operator': operator,
                        'value': str(value),
                        'active': True,
                    })
                    if self.rules.evaluate(fake, context=context):
                        return edge.target_node_id
        if default:
            return default
        if edges:
            return edges[-1].target_node_id
        return False

    def complete(self, execution):
        execution.write({
            'state': 'completed',
            'date_end': fields.Datetime.now(),
            'error_message': False,
        })
        self.audit.log('complete', record=execution, execution=execution)
        return execution

    def fail(self, execution, message):
        execution.write({
            'state': 'failed',
            'date_end': fields.Datetime.now(),
            'error_message': message,
        })
        if execution.current_step_id and execution.current_step_id.state not in ('done', 'failed'):
            execution.current_step_id.write({
                'state': 'failed',
                'date_end': fields.Datetime.now(),
                'error_message': message,
            })
        self.audit.log('failure', record=execution, execution=execution, details=message)
        return execution

    def retry(self, execution):
        execution.ensure_one()
        if not self.env.su and not self.env.user.has_group('workflow_engine.group_we_manager'):
            raise UserError('Only Workflow Engine Managers can retry executions.')
        if execution.state != 'failed':
            raise UserError('Only failed executions can be retried.')
        version_id = execution.version_id.id
        failed_steps = execution.step_ids.filtered(lambda s: s.state == 'failed').sorted('id')
        if not failed_steps:
            raise UserError('No failed step available to retry.')
        failed = failed_steps[-1]
        # Preserve history: bump retry and create a new pending step for same node
        failed.write({'retry_count': failed.retry_count + 1})
        execution.write({
            'state': 'running',
            'error_message': False,
            'date_end': False,
            'current_node_id': failed.node_id.id,
            'version_id': version_id,  # same version enforced by write constraint
        })
        self.audit.log(
            'retry',
            record=execution,
            execution=execution,
            details='retry from step %s on version %s' % (failed.id, version_id),
        )
        return self._process_node(execution, failed.node_id)
