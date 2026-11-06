# -*- coding: utf-8 -*-
"""Odoo TransactionCase tests for Phase 3 domain models."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'we_domain')
class TestWorkflowEngineDomain(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = cls.env['workflow.engine.definition'].create({
            'name': 'Test Workflow',
            'code': 'WE-TEST-001',
        })
        cls.version = cls.env['workflow.engine.version'].create({
            'definition_id': cls.definition.id,
            'version': 1,
        })
        cls.start = cls.env['workflow.engine.node'].create({
            'name': 'Start',
            'technical_key': 'start',
            'version_id': cls.version.id,
            'node_type': 'start',
            'sequence': 1,
        })
        cls.end = cls.env['workflow.engine.node'].create({
            'name': 'End',
            'technical_key': 'end',
            'version_id': cls.version.id,
            'node_type': 'end',
            'sequence': 2,
        })

    def test_models_registered(self):
        for name in (
            'workflow.engine.definition',
            'workflow.engine.version',
            'workflow.engine.node',
            'workflow.engine.edge',
            'workflow.engine.trigger',
            'workflow.engine.template',
            'workflow.engine.approval.hierarchy',
            'workflow.engine.approval.level',
            'workflow.engine.approver',
            'workflow.engine.condition.rule',
            'workflow.engine.execution',
            'workflow.engine.execution.step',
            'workflow.engine.task',
            'workflow.engine.approval.request',
            'workflow.engine.escalation.rule',
            'workflow.engine.escalation.event',
            'workflow.engine.notification.log',
            'workflow.engine.audit.event',
        ):
            self.assertIn(name, self.env.registry)

    def test_definition_lifecycle_default(self):
        self.assertEqual(self.definition.state, 'draft')
        self.assertEqual(self.version.state, 'draft')

    def test_one_draft_version_per_definition(self):
        with self.assertRaises(ValidationError):
            self.env['workflow.engine.version'].create({
                'definition_id': self.definition.id,
                'version': 2,
                'state': 'draft',
            })

    def test_published_version_is_immutable(self):
        self.version.action_publish()
        self.assertEqual(self.version.state, 'published')
        with self.assertRaises(ValidationError):
            self.env['workflow.engine.node'].create({
                'name': 'Task',
                'technical_key': 'task_1',
                'version_id': self.version.id,
                'node_type': 'task',
            })
        with self.assertRaises(ValidationError):
            self.start.write({'name': 'Renamed'})

    def test_node_types_enforced(self):
        with self.assertRaises(Exception):
            self.env['workflow.engine.node'].create({
                'name': 'Bad',
                'technical_key': 'bad',
                'version_id': self.version.id,
                'node_type': 'gateway',
            })

    def test_edge_same_version_and_no_self_loop(self):
        other_def = self.env['workflow.engine.definition'].create({
            'name': 'Other',
            'code': 'WE-TEST-002',
        })
        other_ver = self.env['workflow.engine.version'].create({
            'definition_id': other_def.id,
            'version': 1,
        })
        other_node = self.env['workflow.engine.node'].create({
            'name': 'Other Start',
            'technical_key': 'start',
            'version_id': other_ver.id,
            'node_type': 'start',
        })
        with self.assertRaises(ValidationError):
            self.env['workflow.engine.edge'].create({
                'version_id': self.version.id,
                'source_node_id': self.start.id,
                'target_node_id': other_node.id,
            })
        with self.assertRaises(ValidationError):
            self.env['workflow.engine.edge'].create({
                'version_id': self.version.id,
                'source_node_id': self.start.id,
                'target_node_id': self.start.id,
            })
        edge = self.env['workflow.engine.edge'].create({
            'version_id': self.version.id,
            'source_node_id': self.start.id,
            'target_node_id': self.end.id,
        })
        self.assertEqual(edge.source_node_id.version_id, edge.target_node_id.version_id)

    def test_trigger_belongs_to_version(self):
        trigger = self.env['workflow.engine.trigger'].create({
            'name': 'On Create',
            'version_id': self.version.id,
            'source_module': 'workflow_engine_test',
            'source_model': 'res.partner',
            'event_code': 'created',
        })
        self.assertEqual(trigger.version_id, self.version)
        self.assertEqual(trigger.definition_id, self.definition)

    def test_execution_states_and_version_binding(self):
        self.version.action_publish()
        execution = self.env['workflow.engine.execution'].create({
            'name': 'EX-1',
            'definition_id': self.definition.id,
            'version_id': self.version.id,
            'source_module': 'workflow_engine_test',
            'source_model': 'res.partner',
            'event_code': 'created',
        })
        self.assertEqual(execution.state, 'running')
        self.assertEqual(execution.version_id, self.version)
        other = self.env['workflow.engine.version'].with_context(we_version_transition=True).create({
            'definition_id': self.definition.id,
            'version': 2,
            'state': 'published',
        })
        with self.assertRaises(ValidationError):
            execution.write({'version_id': other.id})

    def test_task_and_approval_structure(self):
        self.version.action_publish()
        execution = self.env['workflow.engine.execution'].create({
            'name': 'EX-2',
            'definition_id': self.definition.id,
            'version_id': self.version.id,
        })
        step = self.env['workflow.engine.execution.step'].create({
            'execution_id': execution.id,
            'node_id': self.start.id,
            'state': 'done',
        })
        task = self.env['workflow.engine.task'].create({
            'name': 'Review',
            'execution_id': execution.id,
            'step_id': step.id,
            'node_id': self.start.id,
            'user_id': self.env.user.id,
        })
        self.assertEqual(task.state, 'open')
        hierarchy = self.env['workflow.engine.approval.hierarchy'].create({
            'name': 'Capex',
            'priority': 1,
        })
        level = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': hierarchy.id,
            'sequence': 1,
            'mode': 'parallel',
            'threshold': 1,
        })
        self.env['workflow.engine.approver'].create({
            'level_id': level.id,
            'user_id': self.env.user.id,
        })
        request = self.env['workflow.engine.approval.request'].create({
            'name': 'Approve spend',
            'execution_id': execution.id,
            'step_id': step.id,
            'hierarchy_id': hierarchy.id,
            'level_id': level.id,
            'user_id': self.env.user.id,
        })
        request.action_approve(comment='ok')
        self.assertEqual(request.state, 'approved')
        self.assertEqual(level.mode, 'parallel')

    def test_conditional_rule_types_and_operators(self):
        rule = self.env['workflow.engine.condition.rule'].create({
            'name': 'High value',
            'rule_type': 'approval_routing',
            'criterion': 'value',
            'operator': '>=',
            'value': '1000',
            'definition_id': self.definition.id,
            'version_id': self.version.id,
        })
        self.assertEqual(rule.rule_type, 'approval_routing')
        with self.assertRaises(Exception):
            self.env['workflow.engine.condition.rule'].create({
                'name': 'Bad',
                'rule_type': 'script',
                'criterion': 'value',
                'operator': '=',
                'value': '1',
            })

    def test_relationships_and_logs(self):
        self.env['workflow.engine.edge'].create({
            'version_id': self.version.id,
            'source_node_id': self.start.id,
            'target_node_id': self.end.id,
        })
        self.version.action_publish()
        self.version.action_activate()
        version_id = self.version.id
        execution = self.env['workflow.engine.execution'].create({
            'name': 'EX-3',
            'definition_id': self.definition.id,
            'version_id': self.version.id,
            'state': 'failed',
        })
        failed_step = self.env['workflow.engine.execution.step'].create({
            'execution_id': execution.id,
            'node_id': self.start.id,
            'state': 'failed',
            'error_message': 'boom',
        })
        self.env['workflow.engine.notification.log'].create({
            'name': 'Notify',
            'execution_id': execution.id,
            'channel': 'email',
            'state': 'queued',
            'user_id': self.env.user.id,
        })
        execution.action_retry()
        self.assertEqual(execution.version_id.id, version_id)
        self.assertTrue(failed_step.exists())
        self.assertTrue(self.env['workflow.engine.audit.event'].search([
            ('action', '=', 'retry'),
            ('execution_id', '=', execution.id),
        ]))
        self.assertIn(execution.state, ('running', 'completed'))

    def test_user_cannot_publish(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({
            'name': 'WE User',
            'login': 'we_user_phase3',
            'groups_id': [(6, 0, [self.env.ref('workflow_engine.group_we_user').id])],
        })
        with self.assertRaises(AccessError):
            self.version.with_user(user).action_publish()
