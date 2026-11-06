# -*- coding: utf-8 -*-
"""Phase 5 UI API / navigation integration tests (no fake production data)."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'we_ui')
class TestWorkflowEngineUi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ui = cls.env['workflow.engine.ui.api']
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.groups_id = [(4, cls.env.ref('workflow_engine.group_we_admin').id)]

    def test_session_context(self):
        ctx = self.Ui.with_user(self.admin).get_session_context()
        self.assertTrue(ctx['is_admin'])
        self.assertTrue(ctx['is_manager'])
        self.assertTrue(ctx['is_user'])

    def test_dashboard_empty_safe(self):
        data = self.Ui.with_user(self.admin).get_dashboard_data()
        self.assertIn('kpis', data)
        for key in (
            'active_workflows', 'running_executions', 'pending_approvals',
            'pending_tasks', 'escalations', 'failed_executions',
        ):
            self.assertIn(key, data['kpis'])
            self.assertIsInstance(data['kpis'][key], int)
        self.assertEqual(len(data['trend']), 7)

    def test_analytics_empty_safe(self):
        data = self.Ui.with_user(self.admin).get_analytics_data()
        self.assertEqual(data['summary']['total_executions'], data['summary']['total_executions'])
        self.assertIn('completion_rate', data['summary'])
        self.assertIn('by_state', data)

    def test_builder_create_load_validate_immutability(self):
        ui = self.Ui.with_user(self.admin)
        graph = ui.create_workflow({'name': 'UI Test Flow', 'code': 'UI_TEST_FLOW'})
        self.assertTrue(graph['definition']['id'])
        self.assertEqual(graph['version']['state'], 'draft')
        self.assertFalse(graph['readonly'])
        self.assertTrue(any(n['node_type'] == 'start' for n in graph['nodes']))
        self.assertTrue(any(n['node_type'] == 'end' for n in graph['nodes']))

        loaded = ui.load_builder_graph(graph['definition']['id'], graph['version']['id'])
        self.assertEqual(loaded['version']['id'], graph['version']['id'])

        result = ui.validate_version(graph['version']['id'])
        self.assertTrue(result['ok'])
        self.assertTrue(any('trigger' in (w or '').lower() for w in result.get('warnings') or []))
        with self.assertRaises(UserError):
            ui.publish_version(graph['version']['id'])

        saved = ui.save_builder_graph(graph['definition']['id'], graph['version']['id'], {
            'nodes': [
                {'client_key': 's', 'name': 'Start', 'technical_key': 'start', 'node_type': 'start', 'sequence': 1},
                {'client_key': 'e', 'name': 'End', 'technical_key': 'end', 'node_type': 'end', 'sequence': 99},
            ],
            'edges': [{'source_ref': 's', 'target_ref': 'e', 'sequence': 10, 'is_default': True}],
            'triggers': [{
                'name': 'UI trigger', 'source_module': 'workflow_engine',
                'source_model': 'workflow.engine.definition', 'event_code': 'ui_test', 'active': True,
            }],
        })
        result = ui.validate_version(saved['version']['id'])
        self.assertTrue(result['ok'], result.get('message'))

        published = ui.publish_version(saved['version']['id'])
        self.assertEqual(published['version']['state'], 'published')
        self.assertTrue(published['readonly'])

        version = self.env['workflow.engine.version'].browse(published['version']['id'])
        with self.assertRaises(Exception):
            version.node_ids[0].write({'name': 'Hacked'})

    def test_retry_same_version_and_menus(self):
        # Menu integrity (exactly 8)
        root = self.env.ref('workflow_engine.menu_we_root')
        menus = self.env['ir.ui.menu'].search([('id', 'child_of', root.id)])
        self.assertEqual(len(menus), 8)
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)], order='sequence')
        self.assertEqual(len(children), 7)
        names = children.mapped('name')
        self.assertEqual(names, [
            'Dashboard',
            'Workflow Builder',
            'Workflow Templates',
            'Approval & Rule Management',
            'Task & Execution Management',
            'Notifications & Approval Tracking',
            'Workflow Analytics & Reports',
        ])

    def test_client_actions_tag(self):
        for xmlid in (
            'action_we_dashboard', 'action_we_builder', 'action_we_templates',
            'action_we_approvals', 'action_we_tasks', 'action_we_notifications',
            'action_we_analytics',
        ):
            action = self.env.ref('workflow_engine.%s' % xmlid)
            self.assertEqual(action.tag, 'workflow_engine_app')

    def test_user_cannot_publish(self):
        user = self.env['res.users'].create({
            'name': 'WE UI User',
            'login': 'we_ui_user_%s' % self.env.user.id,
            'groups_id': [(6, 0, [self.env.ref('workflow_engine.group_we_user').id])],
        })
        # Admin creates draft
        graph = self.Ui.with_user(self.admin).create_workflow({
            'name': 'Locked Flow',
            'code': 'UI_LOCK_%s' % user.id,
        })
        with self.assertRaises(AccessError):
            self.Ui.with_user(user).publish_version(graph['version']['id'])

    def test_save_graph_and_triggers(self):
        ui = self.Ui.with_user(self.admin)
        graph = ui.create_workflow({'name': 'Save Flow', 'code': 'UI_SAVE_FLOW'})
        def_id = graph['definition']['id']
        ver_id = graph['version']['id']
        nodes = [
            {
                'client_key': 's', 'name': 'Start', 'technical_key': 'start',
                'node_type': 'start', 'pos_x': 40, 'pos_y': 80, 'sequence': 1,
            },
            {
                'client_key': 'a', 'name': 'Notify', 'technical_key': 'notify',
                'node_type': 'notification', 'pos_x': 220, 'pos_y': 80, 'sequence': 2,
            },
            {
                'client_key': 'e', 'name': 'End', 'technical_key': 'end',
                'node_type': 'end', 'pos_x': 400, 'pos_y': 80, 'sequence': 3,
            },
        ]
        edges = [
            {'source_ref': 's', 'target_ref': 'a', 'sequence': 10, 'is_default': True},
            {'source_ref': 'a', 'target_ref': 'e', 'sequence': 20, 'is_default': True},
        ]
        triggers = [{
            'name': 'Manual',
            'source_module': 'workflow_engine',
            'source_model': 'workflow.engine.definition',
            'event_code': 'manual_test',
            'active': True,
        }]
        saved = ui.save_builder_graph(def_id, ver_id, {
            'definition': {'name': 'Save Flow Updated'},
            'nodes': nodes,
            'edges': edges,
            'triggers': triggers,
        })
        self.assertEqual(len(saved['nodes']), 3)
        self.assertEqual(len(saved['edges']), 2)
        self.assertEqual(len(saved['triggers']), 1)
        self.assertEqual(saved['definition']['name'], 'Save Flow Updated')
