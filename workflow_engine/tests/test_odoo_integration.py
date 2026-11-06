# -*- coding: utf-8 -*-
"""Phase 6 UI ↔ backend integration tests (transaction-isolated, no demo data)."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'we_integration')
class TestWorkflowEngineIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.Ui = cls.env['workflow.engine.ui.api']
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.groups_id = [(4, cls.env.ref('workflow_engine.group_we_admin').id)]
        cls.user = Users.create({
            'name': 'WE P6 User',
            'login': 'we_p6_user',
            'email': 'we_p6_user@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_user').id])],
        })
        cls.other = Users.create({
            'name': 'WE P6 Other',
            'login': 'we_p6_other',
            'email': 'we_p6_other@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_user').id])],
        })
        cls.manager = Users.create({
            'name': 'WE P6 Manager',
            'login': 'we_p6_manager',
            'email': 'we_p6_manager@example.com',
            'groups_id': [(6, 0, [cls.env.ref('workflow_engine.group_we_manager').id])],
        })
        cls.ui_admin = cls.Ui.with_user(cls.admin)

    def _linear_payload(self, middle_nodes, event_code):
        nodes = [{
            'client_key': 's', 'name': 'Start', 'technical_key': 'start',
            'node_type': 'start', 'pos_x': 40, 'pos_y': 80, 'sequence': 1,
        }]
        prev = 's'
        edges = []
        seq = 10
        for spec in middle_nodes:
            key = spec['key']
            nodes.append({
                'client_key': key,
                'name': spec['name'],
                'technical_key': key,
                'node_type': spec['type'],
                'pos_x': 40 + seq * 8,
                'pos_y': 80,
                'sequence': seq,
                'config_json': spec.get('config') or False,
                'hierarchy_id': spec.get('hierarchy_id') or False,
            })
            edges.append({
                'source_ref': prev, 'target_ref': key, 'sequence': seq, 'is_default': True,
            })
            prev = key
            seq += 10
        nodes.append({
            'client_key': 'e', 'name': 'End', 'technical_key': 'end',
            'node_type': 'end', 'pos_x': 40 + seq * 8, 'pos_y': 80, 'sequence': 99,
        })
        edges.append({
            'source_ref': prev, 'target_ref': 'e', 'sequence': seq, 'is_default': True,
        })
        triggers = [{
            'name': 'P6 %s' % event_code,
            'source_module': 'workflow_engine',
            'source_model': 'workflow.engine.definition',
            'event_code': event_code,
            'active': True,
        }]
        return {'nodes': nodes, 'edges': edges, 'triggers': triggers}

    def _create_active_flow(self, code, event_code, middle_nodes):
        graph = self.ui_admin.create_workflow({'name': 'P6 %s' % code, 'code': code})
        saved = self.ui_admin.save_builder_graph(
            graph['definition']['id'],
            graph['version']['id'],
            self._linear_payload(middle_nodes, event_code),
        )
        result = self.ui_admin.validate_version(saved['version']['id'])
        self.assertTrue(result['ok'], result.get('message'))
        published = self.ui_admin.publish_version(saved['version']['id'])
        self.assertEqual(published['version']['state'], 'published')
        activated = self.ui_admin.activate_version(published['version']['id'])
        self.assertEqual(activated['version']['state'], 'active')
        return activated

    def _execution_from_run(self, run, version_id):
        self.assertTrue(run.get('ok'))
        executions = self.env['workflow.engine.execution'].browse(run.get('execution_ids') or [])
        match = executions.filtered(lambda rec: rec.version_id.id == version_id)
        self.assertTrue(match, 'Expected an execution bound to version %s' % version_id)
        return match[0]

    def test_dashboard_rpc_and_empty_or_live(self):
        data = self.ui_admin.get_dashboard_data()
        for key in (
            'active_workflows', 'running_executions', 'pending_approvals',
            'pending_tasks', 'escalations', 'failed_executions',
        ):
            self.assertIsInstance(data['kpis'][key], int)
        self.assertEqual(len(data['trend']), 7)
        self.assertIn('module_usage', data)
        self.assertIn('recent_activity', data)

    def test_workflow_list_and_builder_draft_load_save(self):
        stamp = 'P6L%s' % self.user.id
        graph = self.ui_admin.create_workflow({'name': 'List Flow', 'code': stamp})
        listed = self.ui_admin.list_workflows()
        self.assertTrue(any(row['code'] == stamp for row in listed))
        loaded = self.ui_admin.load_builder_graph(graph['definition']['id'], graph['version']['id'])
        self.assertFalse(loaded['readonly'])
        saved = self.ui_admin.save_builder_graph(
            graph['definition']['id'],
            graph['version']['id'],
            self._linear_payload([{
                'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'},
            }], 'list_evt_%s' % stamp),
        )
        self.assertEqual(len(saved['nodes']), 3)
        self.assertEqual(len(saved['edges']), 2)
        self.assertEqual(len(saved['triggers']), 1)

    def test_builder_validation_publish_activate_deactivate(self):
        stamp = 'P6V%s' % self.manager.id
        graph = self.ui_admin.create_workflow({'name': 'Val Flow', 'code': stamp})
        broken = self.ui_admin.save_builder_graph(
            graph['definition']['id'],
            graph['version']['id'],
            {
                'nodes': [{
                    'client_key': 's', 'name': 'Start', 'technical_key': 'start',
                    'node_type': 'start', 'sequence': 1,
                }],
                'edges': [],
                'triggers': [],
            },
        )
        invalid = self.ui_admin.validate_version(broken['version']['id'])
        self.assertFalse(invalid['ok'])
        with self.assertRaises(UserError):
            self.ui_admin.publish_version(broken['version']['id'])

        event = 'val_evt_%s' % stamp
        saved = self.ui_admin.save_builder_graph(
            graph['definition']['id'],
            graph['version']['id'],
            self._linear_payload([{
                'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'},
            }], event),
        )
        self.assertTrue(self.ui_admin.validate_version(saved['version']['id'])['ok'])
        published = self.ui_admin.publish_version(saved['version']['id'])
        self.assertTrue(published['readonly'])
        activated = self.ui_admin.activate_version(published['version']['id'])
        self.assertEqual(activated['version']['state'], 'active')
        deactivated = self.ui_admin.deactivate_version(activated['version']['id'])
        self.assertEqual(deactivated['version']['state'], 'inactive')
        with self.assertRaises(ValidationError):
            self.ui_admin.save_builder_graph(
                graph['definition']['id'],
                deactivated['version']['id'],
                self._linear_payload([{
                    'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'},
                }], event),
            )
        self.ui_admin.activate_version(deactivated['version']['id'])

    def test_end_to_end_task_notification_audit(self):
        stamp = 'P6E%s' % self.user.id
        event = 'e2e_%s' % stamp
        graph = self._create_active_flow(stamp, event, [
            {
                'key': 'task', 'name': 'Do work', 'type': 'task',
                'config': {'user_id': self.user.id},
            },
            {
                'key': 'note', 'name': 'Notify', 'type': 'notification',
                'config': {
                    'user_id': self.user.id,
                    'channel': 'in_app',
                    'subject': 'P6 notify',
                    'body': 'done path',
                },
            },
        ])
        dash_before = self.ui_admin.get_dashboard_data()['kpis']['pending_tasks']
        run = self.ui_admin.test_run_version(graph['version']['id'], {'we_test': True})
        execution = self._execution_from_run(run, graph['version']['id'])
        self.assertEqual(execution.version_id.id, graph['version']['id'])
        self.assertEqual(execution.state, 'waiting_task')
        task = execution.task_ids
        self.assertEqual(task.user_id, self.user)
        dash_mid = self.ui_admin.get_dashboard_data()['kpis']['pending_tasks']
        self.assertGreaterEqual(dash_mid, dash_before)

        with self.assertRaises(AccessError):
            self.Ui.with_user(self.other).complete_task(task.id)
        self.Ui.with_user(self.user).complete_task(task.id)
        self.assertEqual(task.state, 'done')
        self.assertEqual(execution.state, 'completed')
        self.assertTrue(self.env['workflow.engine.audit.event'].search([
            ('action', 'in', ['publish', 'activate', 'assign', 'complete']),
        ], limit=1))
        self.assertTrue(self.env['workflow.engine.notification.log'].search([
            ('execution_id', '=', execution.id),
        ], limit=1))
        analytics = self.ui_admin.get_analytics_data({'definition_id': graph['definition']['id']})
        self.assertGreaterEqual(analytics['summary']['total_executions'], 1)
        self.assertIn('user_performance', analytics)
        self.assertIn('trend', analytics)
        self.assertIn('comparison', analytics)

    def test_same_version_retry_after_v2_activate(self):
        stamp = 'P6R%s' % self.manager.id
        event_v1 = 'retry_v1_%s' % stamp
        graph = self._create_active_flow(stamp, event_v1, [{
            'key': 'act', 'name': 'Boom', 'type': 'action',
            'config': {'action': 'explode'},
        }])
        v1_id = graph['version']['id']
        run = self.ui_admin.test_run_version(v1_id, {'we_test': True})
        execution = self._execution_from_run(run, v1_id)
        self.assertEqual(execution.state, 'failed')
        self.assertEqual(execution.version_id.id, v1_id)

        draft = self.ui_admin.create_draft_from_version(v1_id)
        v2 = self.ui_admin.save_builder_graph(
            draft['definition']['id'],
            draft['version']['id'],
            self._linear_payload([{
                'key': 'act', 'name': 'Safe', 'type': 'action', 'config': {'action': 'noop'},
            }], 'retry_v2_%s' % stamp),
        )
        published = self.ui_admin.publish_version(v2['version']['id'])
        activated = self.ui_admin.activate_version(published['version']['id'])
        self.assertEqual(activated['version']['state'], 'active')
        self.assertNotEqual(activated['version']['id'], v1_id)
        self.assertEqual(execution.version_id.id, v1_id)

        retried = self.Ui.with_user(self.manager).retry_execution(execution.id)
        self.assertEqual(retried['version_id'], v1_id)
        self.assertEqual(retried['bound_version_id'], v1_id)
        self.assertEqual(execution.version_id.id, v1_id)

    def test_template_crud_preview_and_create_workflow(self):
        Template = self.env['workflow.engine.template'].with_user(self.admin)
        rec = Template.create({
            'name': 'P6 Template',
            'category': 'core',
            'description': 'fixture',
            'state': 'draft',
        })
        preview = self.ui_admin.preview_template(rec.id)
        self.assertEqual(preview['name'], 'P6 Template')
        listed = self.ui_admin.list_templates([['category', '=', 'core']], 0, 50)
        self.assertTrue(any(row['id'] == rec.id for row in listed['records']))
        rec.action_activate()
        self.assertEqual(rec.state, 'active')
        copy_id = self.ui_admin.duplicate_template(rec.id)
        copy = self.env['workflow.engine.template'].browse(copy_id)
        self.assertEqual(copy.state, 'draft')
        tpl_id = self.ui_admin.save_template(False, {
            'name': 'P6 Saved Template',
            'category': 'core',
            'description': 'via ui.api',
        })
        self.ui_admin.activate_template(tpl_id)
        created = self.ui_admin.create_workflow_from_template(tpl_id, {'name': 'From P6 Saved Template'})
        self.assertTrue(created['definition']['id'])
        self.ui_admin.deactivate_template(tpl_id)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).save_template(False, {'name': 'Nope'})

    def test_approval_and_rule_crud(self):
        hierarchy = self.env['workflow.engine.approval.hierarchy'].with_user(self.admin).create({
            'name': 'P6 Hierarchy',
            'priority': 5,
        })
        level = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': hierarchy.id,
            'name': 'L1',
            'sequence': 10,
            'mode': 'sequential',
            'threshold': 1,
        })
        self.env['workflow.engine.approver'].create({
            'level_id': level.id,
            'user_id': self.user.id,
        })
        hierarchy.write({'description': 'updated'})
        for rule_type in ('approval_routing', 'assignment', 'branch'):
            for operator in ('=', '!=', 'in', '<', '<=', '>', '>='):
                rule = self.env['workflow.engine.condition.rule'].create({
                    'name': 'P6 %s %s' % (rule_type, operator),
                    'rule_type': rule_type,
                    'criterion': 'value',
                    'operator': operator,
                    'value': '10',
                })
                self.assertEqual(rule.operator, operator)
        hierarchy.action_deactivate()
        hierarchy.action_activate()
        hid = self.ui_admin.save_hierarchy({
            'name': 'P6 UI Hierarchy',
            'priority': 3,
            'active': True,
            'levels': [{
                'name': 'L1',
                'sequence': 10,
                'mode': 'sequential',
                'threshold': 1,
                'approver_user_ids': [self.user.id],
                'approver_group_ids': [],
                'fallback_user_id': False,
            }],
        })
        detail = self.ui_admin.get_hierarchy_detail(hid)
        self.assertEqual(len(detail['levels']), 1)
        self.assertEqual(detail['levels'][0]['approver_user_ids'], [self.user.id])
        rid = self.ui_admin.save_rule(False, {
            'name': 'P6 UI Rule',
            'rule_type': 'branch',
            'criterion': 'value',
            'operator': '=',
            'value': 'ok',
            'priority': 1,
            'active': True,
        })
        self.assertTrue(rid)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).save_rule(False, {
                'name': 'blocked', 'rule_type': 'branch', 'criterion': 'value',
                'operator': '=', 'value': 'x',
            })
        setup = self.ui_admin.get_approval_setup()
        self.assertTrue(any(row['id'] == hid for row in setup['hierarchies']))

    def test_execution_and_task_detail_rpc(self):
        stamp = 'P6D%s' % self.user.id
        graph = self._create_active_flow(stamp, 'detail_%s' % stamp, [{
            'key': 'task', 'name': 'Work', 'type': 'task',
            'config': {'user_id': self.user.id},
        }])
        run = self.ui_admin.test_run_version(graph['version']['id'])
        execution = self._execution_from_run(run, graph['version']['id'])
        exec_detail = self.ui_admin.get_execution_detail(execution.id)
        self.assertEqual(exec_detail['record']['id'], execution.id)
        self.assertTrue(exec_detail['steps'])
        task = execution.task_ids
        task_detail = self.ui_admin.get_task_detail(task.id)
        self.assertEqual(task_detail['record']['id'], task.id)
        analytics = self.ui_admin.get_analytics_data({})
        for key in (
            'total_executions', 'completion_rate', 'failure_rate',
            'avg_duration_hours', 'avg_approval_hours', 'avg_task_hours',
        ):
            self.assertIn(key, analytics['summary'])

    def test_approval_approve_reject_via_ui_api(self):
        stamp = 'P6A%s' % self.user.id
        hierarchy = self.env['workflow.engine.approval.hierarchy'].create({'name': 'P6 Appr'})
        level = self.env['workflow.engine.approval.level'].create({
            'hierarchy_id': hierarchy.id, 'sequence': 1, 'mode': 'sequential', 'threshold': 1,
        })
        self.env['workflow.engine.approver'].create({
            'level_id': level.id, 'user_id': self.user.id,
        })
        graph = self._create_active_flow(stamp, 'appr_%s' % stamp, [{
            'key': 'appr', 'name': 'Approve', 'type': 'approval', 'hierarchy_id': hierarchy.id,
        }])
        run = self.ui_admin.test_run_version(graph['version']['id'])
        execution = self._execution_from_run(run, graph['version']['id'])
        request = execution.approval_request_ids
        self.assertEqual(request.state, 'pending')
        pending = self.Ui.with_user(self.user).search_approvals([['state', '=', 'pending']], 0, 50)
        self.assertTrue(any(row['id'] == request.id for row in pending['records']))
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.other).approve_request(request.id, 'nope')
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.manager).approve_request(request.id, 'manager')
        self.Ui.with_user(self.user).reject_request(request.id, 'not this time')
        self.assertEqual(request.state, 'rejected')

    def test_task_assign_complete_escalate_retry_permissions(self):
        stamp = 'P6T%s' % self.other.id
        graph = self._create_active_flow(stamp, 'task_%s' % stamp, [{
            'key': 'task', 'name': 'Work', 'type': 'task',
            'config': {'user_id': self.user.id},
        }])
        run = self.ui_admin.test_run_version(graph['version']['id'])
        execution = self._execution_from_run(run, graph['version']['id'])
        task = execution.task_ids
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).assign_task(task.id, self.other.id)
        self.Ui.with_user(self.manager).assign_task(task.id, self.user.id)
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).escalate_task(task.id)
        self.Ui.with_user(self.manager).escalate_task(task.id)
        self.assertEqual(task.state, 'escalated')
        self.Ui.with_user(self.user).complete_task(task.id)
        self.assertEqual(execution.state, 'completed')

        fail_stamp = 'P6F%s' % self.other.id
        failed_graph = self._create_active_flow(fail_stamp, 'fail_%s' % fail_stamp, [{
            'key': 'act', 'name': 'Boom', 'type': 'action',
            'config': {'action': 'explode'},
        }])
        failed_run = self.ui_admin.test_run_version(failed_graph['version']['id'])
        failed = self._execution_from_run(failed_run, failed_graph['version']['id'])
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).retry_execution(failed.id)
        result = self.Ui.with_user(self.manager).retry_execution(failed.id)
        self.assertEqual(result['version_id'], failed.version_id.id)

    def test_user_cannot_publish_or_activate(self):
        graph = self.ui_admin.create_workflow({'name': 'Lock', 'code': 'P6LOCK%s' % self.user.id})
        saved = self.ui_admin.save_builder_graph(
            graph['definition']['id'],
            graph['version']['id'],
            self._linear_payload([{
                'key': 'act', 'name': 'Noop', 'type': 'action', 'config': {'action': 'noop'},
            }], 'lock_%s' % self.user.id),
        )
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).publish_version(saved['version']['id'])
        published = self.ui_admin.publish_version(saved['version']['id'])
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).activate_version(published['version']['id'])
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.manager).activate_version(published['version']['id'])
        self.ui_admin.activate_version(published['version']['id'])
        with self.assertRaises(AccessError):
            self.Ui.with_user(self.user).deactivate_version(published['version']['id'])

    def test_search_pagination_and_menus(self):
        executions = self.ui_admin.search_executions([], 0, 5)
        self.assertIn('total', executions)
        self.assertLessEqual(len(executions['records']), 5)
        tasks = self.ui_admin.search_tasks([], 0, 5)
        self.assertIn('records', tasks)
        notifs = self.ui_admin.search_notifications([], 0, 5)
        self.assertIn('records', notifs)
        root = self.env.ref('workflow_engine.menu_we_root')
        menus = self.env['ir.ui.menu'].search([('id', 'child_of', root.id)])
        self.assertEqual(len(menus), 8)
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])
        self.assertEqual(len(children), 7)
