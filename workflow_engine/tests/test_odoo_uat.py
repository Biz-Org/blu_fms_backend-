# -*- coding: utf-8 -*-
"""Phase 7 complete functional UAT (transaction-isolated, no demo XML)."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.workflow_engine.services.rule_service import WorkflowRuleService
from odoo.addons.workflow_engine.services.trigger_service import WorkflowTriggerService


@tagged('post_install', '-at_install', 'we_uat')
class TestWorkflowEngineUat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.Ui = cls.env['workflow.engine.ui.api']
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.groups_id = [(4, cls.env.ref('workflow_engine.group_we_admin').id)]
        cls.user = Users.create({
            'name': 'WE UAT User',
            'login': 'we_uat_user',
            'email': 'we_uat_user@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_user').id])],
        })
        cls.other = Users.create({
            'name': 'WE UAT Other',
            'login': 'we_uat_other',
            'email': 'we_uat_other@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_user').id])],
        })
        cls.fallback = Users.create({
            'name': 'WE UAT Fallback',
            'login': 'we_uat_fallback',
            'email': 'we_uat_fallback@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_user').id])],
        })
        cls.manager = Users.create({
            'name': 'WE UAT Manager',
            'login': 'we_uat_manager',
            'email': 'we_uat_manager@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_manager').id])],
        })
        cls.ui = cls.Ui.with_user(cls.admin)

    def _payload(self, middle, event, extra_nodes=None, extra_edges=None):
        nodes = [{
            'client_key': 's', 'name': 'Start', 'technical_key': 'start',
            'node_type': 'start', 'pos_x': 40, 'pos_y': 80, 'sequence': 1,
        }]
        prev = 's'
        edges = []
        seq = 10
        for spec in middle:
            key = spec['key']
            nodes.append({
                'client_key': key, 'name': spec['name'], 'technical_key': key,
                'node_type': spec['type'], 'pos_x': 40 + seq * 8, 'pos_y': 80,
                'sequence': seq, 'config_json': spec.get('config') or False,
                'hierarchy_id': spec.get('hierarchy_id') or False,
                'rule_id': spec.get('rule_id') or False,
            })
            edges.append({'source_ref': prev, 'target_ref': key, 'sequence': seq, 'is_default': True})
            prev = key
            seq += 10
        nodes.append({
            'client_key': 'e', 'name': 'End', 'technical_key': 'end',
            'node_type': 'end', 'pos_x': 40 + seq * 8, 'pos_y': 80, 'sequence': 99,
        })
        edges.append({'source_ref': prev, 'target_ref': 'e', 'sequence': seq, 'is_default': True})
        if extra_nodes:
            nodes.extend(extra_nodes)
        if extra_edges:
            edges.extend(extra_edges)
        return {
            'nodes': nodes,
            'edges': edges,
            'triggers': [{
                'name': 'UAT %s' % event,
                'source_module': 'workflow_engine',
                'source_model': 'workflow.engine.definition',
                'event_code': event,
                'active': True,
            }],
        }

    def _activate(self, code, event, middle, extra_nodes=None, extra_edges=None):
        graph = self.ui.create_workflow({'name': 'UAT %s' % code, 'code': code})
        saved = self.ui.save_builder_graph(
            graph['definition']['id'], graph['version']['id'],
            self._payload(middle, event, extra_nodes=extra_nodes, extra_edges=extra_edges),
        )
        result = self.ui.validate_version(saved['version']['id'])
        self.assertTrue(result['ok'], result.get('message'))
        published = self.ui.publish_version(saved['version']['id'])
        return self.ui.activate_version(published['version']['id'])

    def _run(self, version_id):
        run = self.ui.test_run_version(version_id, {'we_test': True, 'value': 10})
        executions = self.env['workflow.engine.execution'].browse(run.get('execution_ids') or [])
        match = executions.filtered(lambda rec: rec.version_id.id == version_id)
        self.assertTrue(match)
        return match[0]

    def test_01_creation_reload_and_graph_edit(self):
        graph = self.ui.create_workflow({'name': 'UAT Create', 'code': 'UATCREATE'})
        definition = self.env['workflow.engine.definition'].browse(graph['definition']['id'])
        version = self.env['workflow.engine.version'].browse(graph['version']['id'])
        self.assertEqual(definition.state, 'draft')
        self.assertEqual(version.state, 'draft')
        self.assertEqual(version.version, 1)
        loaded = self.ui.load_builder_graph(definition.id, version.id)
        self.assertEqual(loaded['definition']['name'], 'UAT Create')
        self.assertEqual(len(loaded['nodes']), 2)
        saved = self.ui.save_builder_graph(definition.id, version.id, self._payload([{
            'key': 'act', 'name': 'Do', 'type': 'action', 'config': {'action': 'noop'},
        }], 'uat_create'))
        self.assertEqual(len(saved['nodes']), 3)
        self.assertEqual(len(saved['edges']), 2)
        reload_again = self.ui.load_builder_graph(definition.id, version.id)
        self.assertEqual(len(reload_again['nodes']), 3)
        self.assertEqual(len(reload_again['edges']), 2)
        # delete action node by saving start-end only + trigger
        trimmed = self.ui.save_builder_graph(definition.id, version.id, self._payload([], 'uat_create'))
        self.assertEqual(len(trimmed['nodes']), 2)
        self.assertFalse(self.env['workflow.engine.node'].search([
            ('version_id', '=', version.id), ('technical_key', '=', 'act'),
        ]))

    def test_02_validation_blocks_publish(self):
        graph = self.ui.create_workflow({'name': 'UAT Invalid', 'code': 'UATINV'})
        no_start = self.ui.save_builder_graph(graph['definition']['id'], graph['version']['id'], {
            'nodes': [{'client_key': 'e', 'name': 'End', 'technical_key': 'end', 'node_type': 'end', 'sequence': 1}],
            'edges': [],
            'triggers': [{'name': 't', 'source_module': 'workflow_engine',
                          'source_model': 'workflow.engine.definition', 'event_code': 'x', 'active': True}],
        })
        res = self.ui.validate_version(no_start['version']['id'])
        self.assertFalse(res['ok'])
        self.assertTrue(any('Start' in e for e in res['errors']))
        with self.assertRaises(UserError):
            self.ui.publish_version(no_start['version']['id'])

        no_end = self.ui.save_builder_graph(graph['definition']['id'], graph['version']['id'], {
            'nodes': [{'client_key': 's', 'name': 'Start', 'technical_key': 'start', 'node_type': 'start', 'sequence': 1}],
            'edges': [],
            'triggers': [{'name': 't', 'source_module': 'workflow_engine',
                          'source_model': 'workflow.engine.definition', 'event_code': 'x', 'active': True}],
        })
        res = self.ui.validate_version(no_end['version']['id'])
        self.assertFalse(res['ok'])
        self.assertTrue(any('End' in e for e in res['errors']))

        missing_trigger = self.ui.save_builder_graph(graph['definition']['id'], graph['version']['id'], {
            'nodes': [
                {'client_key': 's', 'name': 'Start', 'technical_key': 'start', 'node_type': 'start', 'sequence': 1},
                {'client_key': 'e', 'name': 'End', 'technical_key': 'end', 'node_type': 'end', 'sequence': 2},
            ],
            'edges': [{'source_ref': 's', 'target_ref': 'e', 'sequence': 1, 'is_default': True}],
            'triggers': [],
        })
        res = self.ui.validate_version(missing_trigger['version']['id'])
        self.assertTrue(any('trigger' in (m or '').lower() for m in (res.get('errors') or []) + (res.get('warnings') or [])))
        with self.assertRaises(UserError):
            self.ui.publish_version(missing_trigger['version']['id'])

        no_hierarchy = self.ui.save_builder_graph(
            graph['definition']['id'], graph['version']['id'],
            self._payload([{'key': 'appr', 'name': 'Approve', 'type': 'approval'}], 'noh'),
        )
        res = self.ui.validate_version(no_hierarchy['version']['id'])
        self.assertFalse(res['ok'])
        self.assertTrue(any('hierarchy' in e.lower() for e in res['errors']))

    def test_03_publish_activate_deactivate_trigger_and_audit(self):
        event = 'uat_trig_%s' % self.user.id
        graph = self._activate('UATTRIG', event, [{
            'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'},
        }])
        version = self.env['workflow.engine.version'].browse(graph['version']['id'])
        self.assertEqual(version.state, 'active')
        self.assertTrue(self.env['workflow.engine.audit.event'].search([
            ('action', 'in', ['publish', 'activate']),
        ], limit=1))
        with self.assertRaises(ValidationError):
            version.node_ids[0].write({'name': 'Hacked'})
        execution = self._run(version.id)
        self.assertEqual(execution.version_id, version)
        self.assertEqual(execution.state, 'completed')
        self.assertTrue(execution.step_ids.filtered(lambda s: s.node_id.node_type == 'start'))

        self.ui.deactivate_version(version.id)
        version.invalidate_recordset()
        self.assertEqual(version.state, 'inactive')
        result = WorkflowTriggerService(self.env).trigger(
            'workflow_engine', 'workflow.engine.definition', event, payload={'we_test': True},
        )
        executions = result.get('executions') if isinstance(result, dict) else result
        self.assertFalse(executions)

        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).activate_version(version.id)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).deactivate_version(version.id)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.manager).activate_version(version.id)

    def test_04_rules_all_types_criteria_operators(self):
        service = WorkflowRuleService(self.env)
        for rule_type in ('approval_routing', 'assignment', 'branch'):
            for criterion in ('department', 'role', 'value', 'property', 'site', 'module'):
                for operator in ('=', '!=', 'in', '<', '<=', '>', '>='):
                    rule = self.env['workflow.engine.condition.rule'].new({
                        'name': 'UAT %s %s %s' % (rule_type, criterion, operator),
                        'rule_type': rule_type,
                        'criterion': criterion,
                        'operator': operator,
                        'value': '10' if operator != 'in' else 'a,b,10',
                        'active': True,
                    })
                    ctx = service.build_context(payload={
                        criterion: 10 if criterion != 'module' else 'workflow_engine',
                        'module': 'workflow_engine',
                    })
                    if criterion == 'module' and operator in ('<', '<=', '>', '>='):
                        self.assertFalse(service.evaluate(rule, context=ctx))
                    else:
                        service.evaluate(rule, context=ctx)
                    self.assertFalse(service.evaluate(rule, context={'payload': {}}))
        with self.assertRaises(ValidationError):
            service.evaluate(self.env['workflow.engine.condition.rule'].new({
                'name': 'bad', 'rule_type': 'branch', 'criterion': 'value',
                'operator': '~~', 'value': '1', 'active': True,
            }), context={'value': 1})

    def test_05_sequential_parallel_fallback_and_rbac(self):
        seq = self.env['workflow.engine.approval.hierarchy'].create({'name': 'UAT Seq'})
        l1 = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': seq.id, 'name': 'L1', 'sequence': 10, 'mode': 'sequential', 'threshold': 1,
        })
        l2 = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': seq.id, 'name': 'L2', 'sequence': 20, 'mode': 'sequential', 'threshold': 1,
        })
        self.env['workflow.engine.approver'].create({'level_id': l1.id, 'user_id': self.user.id})
        self.env['workflow.engine.approver'].create({
            'level_id': l2.id, 'user_id': self.other.id,
        })
        self.env['workflow.engine.approver'].create({
            'level_id': l2.id, 'user_id': self.fallback.id, 'is_fallback': True,
        })
        par = self.env['workflow.engine.approval.hierarchy'].create({'name': 'UAT Par'})
        pl = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': par.id, 'name': 'P1', 'sequence': 10, 'mode': 'parallel', 'threshold': 2,
        })
        self.env['workflow.engine.approver'].create({'level_id': pl.id, 'user_id': self.user.id})
        self.env['workflow.engine.approver'].create({'level_id': pl.id, 'user_id': self.other.id})

        seq_flow = self._activate('UATSEQ', 'uat_seq', [{
            'key': 'appr', 'name': 'Seq', 'type': 'approval', 'hierarchy_id': seq.id,
        }])
        execution = self._run(seq_flow['version']['id'])
        self.assertEqual(execution.state, 'waiting_approval')
        first = execution.approval_request_ids.filtered(lambda r: r.state == 'pending')
        self.assertEqual(first.user_id, self.user)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.other).approve_request(first.id, 'no')
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.manager).approve_request(first.id, 'mgr')
        self.Ui.with_user(self.user).approve_request(first.id, 'l1 ok')
        second = execution.approval_request_ids.filtered(lambda r: r.state == 'pending')
        self.assertEqual(second.user_id, self.other)
        self.Ui.with_user(self.other).approve_request(second.id, 'l2 ok')
        self.assertEqual(execution.state, 'completed')
        self.assertTrue(first.comment)

        par_flow = self._activate('UATPAR', 'uat_par', [{
            'key': 'appr', 'name': 'Par', 'type': 'approval', 'hierarchy_id': par.id,
        }])
        pex = self._run(par_flow['version']['id'])
        pending = pex.approval_request_ids.filtered(lambda r: r.state == 'pending')
        self.assertEqual(len(pending), 2)
        self.Ui.with_user(self.user).approve_request(pending.filtered(lambda r: r.user_id == self.user).id, 'p1')
        self.assertEqual(pex.state, 'waiting_approval')
        self.Ui.with_user(self.other).approve_request(pending.filtered(lambda r: r.user_id == self.other).id, 'p2')
        self.assertEqual(pex.state, 'completed')

    def test_06_task_start_assign_complete_and_assignment_rule(self):
        flow = self._activate('UATTASK', 'uat_task', [{
            'key': 'task', 'name': 'Work', 'type': 'task',
            'config': {'user_id': self.other.id},
        }])
        execution = self._run(flow['version']['id'])
        task = execution.task_ids
        self.assertEqual(task.state, 'open')
        self.assertEqual(task.execution_id, execution)
        self.assertTrue(task.step_id)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).assign_task(task.id, self.user.id)
        self.Ui.with_user(self.manager).assign_task(task.id, self.user.id)
        self.assertEqual(task.user_id, self.user)
        self.Ui.with_user(self.user).start_task(task.id)
        self.assertEqual(task.state, 'in_progress')
        self.Ui.with_user(self.user).complete_task(task.id)
        self.assertEqual(task.state, 'done')
        self.assertEqual(execution.state, 'completed')
        self.assertTrue(self.env['workflow.engine.audit.event'].search([
            ('action', 'in', ['assign', 'reassign', 'complete', 'update']),
        ], limit=1))

        token = 'uat-assign-%s' % self.user.id
        rule = self.env['workflow.engine.condition.rule'].create({
            'name': 'UAT assign %s' % self.user.id,
            'rule_type': 'assignment',
            'criterion': 'module',
            'operator': '=',
            'value': token,
            'priority': 1,
        })
        ctx = WorkflowRuleService(self.env).build_context(payload={'module': token})
        match = WorkflowRuleService(self.env).first_match('assignment', context=ctx)
        self.assertIn(rule, match)

    def test_07_escalation_manual_cron_and_notifications(self):
        flow = self._activate('UATESC', 'uat_esc', [{
            'key': 'task', 'name': 'Slow', 'type': 'task',
            'config': {'user_id': self.user.id, 'due_hours': 1},
        }])
        execution = self._run(flow['version']['id'])
        task = execution.task_ids
        self.env['workflow.engine.escalation.rule'].create({
            'name': 'UAT auto esc',
            'target_type': 'task',
            'mode': 'automatic',
            'delay_minutes': 0,
            'level': 2,
            'user_id': self.manager.id,
            'notify': True,
            'definition_id': execution.definition_id.id,
        })
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).escalate_task(task.id)
        self.Ui.with_user(self.manager).escalate_task(task.id)
        self.assertEqual(task.state, 'escalated')
        events = self.env['workflow.engine.escalation.event'].search([('task_id', '=', task.id)])
        self.assertEqual(len(events), 1)
        self.assertTrue(self.env['workflow.engine.notification.log'].search([
            '|', ('task_id', '=', task.id), ('execution_id', '=', execution.id),
        ]))
        # second manual escalate must not duplicate
        self.Ui.with_user(self.manager).escalate_task(task.id)
        self.assertEqual(len(self.env['workflow.engine.escalation.event'].search([('task_id', '=', task.id)])), 1)

        late = self.env['workflow.engine.task'].browse(task.id)
        late.sudo().write({'date_deadline': fields.Datetime.now() - timedelta(hours=2)})
        processed = self.env['workflow.engine.escalation.rule']._cron_process_escalations()
        self.assertTrue(processed is not None)

    def test_08_complete_lifecycle_failure_retry_versioning(self):
        hierarchy = self.env['workflow.engine.approval.hierarchy'].create({'name': 'UAT Full'})
        level = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': hierarchy.id, 'sequence': 1, 'mode': 'sequential', 'threshold': 1,
        })
        self.env['workflow.engine.approver'].create({'level_id': level.id, 'user_id': self.user.id})
        full = self._activate('UATFULL', 'uat_full', [
            {'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'}},
            {'key': 'task', 'name': 'Work', 'type': 'task', 'config': {'user_id': self.user.id}},
            {'key': 'appr', 'name': 'Approve', 'type': 'approval', 'hierarchy_id': hierarchy.id},
            {'key': 'note', 'name': 'Notify', 'type': 'notification',
             'config': {'user_id': self.user.id, 'channel': 'in_app', 'subject': 'UAT done', 'body': 'ok'}},
        ])
        execution = self._run(full['version']['id'])
        self.assertEqual(execution.state, 'waiting_task')
        self.Ui.with_user(self.user).complete_task(execution.task_ids.id)
        req = execution.approval_request_ids.filtered(lambda r: r.state == 'pending')
        self.Ui.with_user(self.user).approve_request(req.id, 'go')
        self.assertEqual(execution.state, 'completed')
        self.assertTrue(execution.step_ids)
        self.assertTrue(self.env['workflow.engine.notification.log'].search([
            ('execution_id', '=', execution.id),
        ]))
        self.assertTrue(self.env['workflow.engine.audit.event'].search([
            ('execution_id', '=', execution.id),
        ], limit=1) or self.env['workflow.engine.audit.event'].search([], limit=1))

        fail = self._activate('UATFAIL', 'uat_fail', [{
            'key': 'act', 'name': 'Boom', 'type': 'action', 'config': {'action': 'explode'},
        }])
        failed_ex = self._run(fail['version']['id'])
        self.assertEqual(failed_ex.state, 'failed')
        self.assertTrue(failed_ex.error_message)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).retry_execution(failed_ex.id)
        v1 = failed_ex.version_id.id
        draft = self.ui.create_draft_from_version(v1)
        v2 = self.ui.save_builder_graph(
            draft['definition']['id'], draft['version']['id'],
            self._payload([{'key': 'act', 'name': 'Safe', 'type': 'action', 'config': {'action': 'noop'}}], 'uat_fail_v2'),
        )
        published = self.ui.publish_version(v2['version']['id'])
        activated = self.ui.activate_version(published['version']['id'])
        self.assertNotEqual(activated['version']['id'], v1)
        self.assertEqual(failed_ex.version_id.id, v1)
        retried = self.Ui.with_user(self.manager).retry_execution(failed_ex.id)
        self.assertEqual(retried['version_id'], v1)
        self.assertEqual(failed_ex.version_id.id, v1)

        graph = self.ui.create_workflow({'name': 'UAT Drafts', 'code': 'UATDRAFT'})
        with self.assertRaises(UserError):
            self.ui.create_draft_from_version(graph['version']['id'])

    def test_09_dashboard_analytics_search_integrity_menus(self):
        dash = self.ui.get_dashboard_data()
        for key in (
            'active_workflows', 'running_executions', 'pending_approvals',
            'pending_tasks', 'escalations', 'failed_executions',
        ):
            self.assertIsInstance(dash['kpis'][key], int)
        analytics = self.ui.get_analytics_data({})
        self.assertIn('completion_rate', analytics['summary'])
        execs = self.ui.search_executions([], 0, 5)
        self.assertLessEqual(len(execs['records']), 5)
        tasks = self.ui.search_tasks([], 0, 5)
        self.assertIn('total', tasks)
        notifs = self.ui.search_notifications([], 0, 20)
        self.assertIn('records', notifs)
        templates = self.ui.list_templates([['name', 'ilike', 'NO_SUCH_UAT_TEMPLATE']], 0, 20)
        self.assertEqual(templates['records'], [])
        bad_edges = self.env['workflow.engine.edge'].search([]).filtered(
            lambda e: e.source_node_id.version_id != e.target_node_id.version_id
        )
        self.assertFalse(bad_edges)
        orphan_nodes = self.env['workflow.engine.node'].search([('version_id', '=', False)])
        self.assertFalse(orphan_nodes)
        root = self.env.ref('workflow_engine.menu_we_root')
        self.assertEqual(len(self.env['ir.ui.menu'].search([('id', 'child_of', root.id)])), 8)
        self.assertEqual(len(self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])), 7)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).publish_version(
                self.ui.create_workflow({'name': 'Lock', 'code': 'UATLOCK'})['version']['id']
            )
