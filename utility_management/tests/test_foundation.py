# -*- coding: utf-8 -*-
import pathlib
import unittest

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

SCREEN_IDS = (
    'utility_dashboard',
    'utility_meter_inventory',
    'utility_electricity_monitoring',
    'utility_water_monitoring',
    'utility_gas_monitoring',
    'utility_power_source',
    'utility_overall_consumption',
    'utility_meter_reading',
    'utility_leak_detection',
    'utility_alerts',
    'utility_reports',
    'utility_settings',
)

BUSINESS_MODELS = (
    'utility.management.meter',
    'utility.management.connectivity',
    'utility.management.reading',
    'utility.management.power.source',
    'utility.management.power.event',
    'utility.management.leak',
    'utility.management.leak.action',
    'utility.management.alert.rule',
    'utility.management.alert',
    'utility.management.report.definition',
    'utility.management.report.run',
    'utility.management.audit.event',
    'utility.management.access.scope',
    'utility.management.config',
)

ACTION_XMLIDS = (
    'action_utility_dashboard',
    'action_utility_meter_inventory',
    'action_utility_electricity_monitoring',
    'action_utility_water_monitoring',
    'action_utility_gas_monitoring',
    'action_utility_power_source',
    'action_utility_overall_consumption',
    'action_utility_meter_reading',
    'action_utility_leak_detection',
    'action_utility_alerts',
    'action_utility_reports',
    'action_utility_settings',
)

MENU_XMLIDS = (
    'menu_utility_root',
    'menu_utility_dashboard',
    'menu_utility_meter_inventory',
    'menu_utility_electricity_monitoring',
    'menu_utility_water_monitoring',
    'menu_utility_gas_monitoring',
    'menu_utility_power_source',
    'menu_utility_overall_consumption',
    'menu_utility_meter_reading',
    'menu_utility_leak_detection',
    'menu_utility_alerts',
    'menu_utility_reports',
    'menu_utility_settings',
)


@tagged('post_install', '-at_install', 'utility_foundation')
class TestUtilityFoundation(TransactionCase):

    def test_module_installed_and_dependencies(self):
        module = self.env['ir.module.module'].search([
            ('name', '=', 'utility_management'),
        ])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, 'installed')
        self.assertFalse(module.demo)
        self.assertEqual(module.installed_version, '18.0.1.0.0')
        dependency_names = set(module.dependencies_id.mapped('name'))
        self.assertEqual(dependency_names, {'base', 'web', 'mail'})

    def test_security_groups(self):
        staff = self.env.ref('utility_management.group_utility_staff')
        manager = self.env.ref('utility_management.group_facility_manager')
        internal = self.env.ref('base.group_user')
        category = self.env.ref('utility_management.module_category_utility_management')
        groups = self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'res.groups'),
        ])
        self.assertEqual(set(groups.mapped('name')), {
            'group_utility_staff',
            'group_facility_manager',
        })
        self.assertEqual(len(groups), 2)
        self.assertIn(internal, staff.implied_ids)
        self.assertIn(staff, manager.implied_ids)
        self.assertEqual(staff.category_id, category)
        self.assertEqual(manager.category_id, category)
        self.assertEqual(staff.name, 'Utility Staff')
        self.assertEqual(manager.name, 'Facility Manager')

    def test_menus(self):
        root = self.env.ref('utility_management.menu_utility_root')
        data = self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'ir.ui.menu'),
        ])
        self.assertEqual(set(data.mapped('name')), set(MENU_XMLIDS))
        self.assertEqual(len(data), 13)
        self.assertEqual(root.name, 'Utility Management')
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])
        self.assertEqual(len(children), 12)
        self.assertEqual(
            children.sorted('sequence').mapped('name'),
            [
                'Dashboard',
                'Meter Inventory',
                'Electricity Monitoring',
                'Water Monitoring',
                'Gas Monitoring',
                'Power Source',
                'Overall Consumption',
                'Meter Reading',
                'Leak Detection',
                'Utility Alerts',
                'Utility Reports',
                'Settings',
            ],
        )

    def test_client_actions_and_screen_ids(self):
        data = self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'ir.actions.client'),
        ])
        self.assertEqual(set(data.mapped('name')), set(ACTION_XMLIDS))
        self.assertEqual(len(data), 12)
        for xmlid, screen in zip(ACTION_XMLIDS, SCREEN_IDS):
            action = self.env.ref('utility_management.%s' % xmlid)
            self.assertEqual(action.tag, 'utility_management_app')
            self.assertIn("'screen': '%s'" % screen, action.context)
            self.assertEqual(action.params.get('screen'), screen)

    def test_ui_api_health_and_authorization(self):
        api = self.env['utility.management.ui.api']
        self.assertTrue(api._abstract)
        self.assertFalse(api._auto)
        payload = api.health()
        self.assertEqual(payload['ok'], True)
        self.assertEqual(payload['module'], 'utility_management')
        self.assertEqual(payload['version'], '18.0.1.0.0')
        self.assertEqual(tuple(payload['screens']), SCREEN_IDS)
        self.assertTrue(payload['is_utility_staff'])
        self.assertTrue(payload['is_facility_manager'])
        self.assertNotIn('password', payload)
        self.assertNotIn('connection_config', payload)

        staff = self.env['res.users'].create({
            'name': 'Utility Staff Foundation',
            'login': 'utility_staff_foundation',
            'groups_id': [(6, 0, [
                self.env.ref('utility_management.group_utility_staff').id,
            ])],
        })
        staff_payload = api.with_user(staff).health()
        self.assertTrue(staff_payload['is_utility_staff'])
        self.assertFalse(staff_payload['is_facility_manager'])

        outsider = self.env['res.users'].create({
            'name': 'Outside Utility Foundation',
            'login': 'outside_utility_foundation',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            api.with_user(outsider).health()
        with self.assertRaises(AccessError):
            api.with_user(self.env.ref('base.public_user')).health()

    def test_domain_registry_sequences_and_jobs(self):
        registry_models = [
            name for name in self.env
            if name.startswith('utility.management.')
        ]
        self.assertEqual(
            set(registry_models),
            set(BUSINESS_MODELS) | {
                'utility.management.mixin',
                'utility.management.ui.api',
            },
        )
        for model_name in BUSINESS_MODELS:
            model = self.env[model_name]
            self.assertTrue(model._auto)
            self.assertFalse(model._abstract)
            self.assertIn('company_id', model._fields)
        self.assertTrue(self.env['utility.management.mixin']._abstract)
        self.assertTrue(self.env['utility.management.ui.api']._abstract)
        self.env.cr.execute(
            """
            SELECT tablename
              FROM pg_tables
             WHERE schemaname = 'public'
               AND tablename LIKE 'utility_management%'
            """
        )
        tables = {row[0] for row in self.env.cr.fetchall()}
        self.assertEqual(len(tables), 14)
        sequences = self.env['ir.sequence'].search([
            ('code', 'in', [
                'utility.management.reading',
                'utility.management.leak',
                'utility.management.alert',
                'utility.management.report.run',
            ]),
        ])
        self.assertEqual(len(sequences), 4)
        self.assertEqual(
            set(sequences.mapped('prefix')),
            {'RDG/%(year)s/', 'LK/%(year)s/', 'ALT/%(year)s/', 'RPT/%(year)s/'},
        )
        crons = self.env['ir.cron'].search([
            ('name', 'like', 'Utility:%'),
        ])
        self.assertEqual(len(crons), 4)
        templates = self.env['mail.template'].search([
            ('name', 'like', 'Utility:%'),
        ])
        self.assertEqual(len(templates), 2)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'ir.attachment'),
        ]))
        addon_root = pathlib.Path(
            __import__(
                'odoo.addons.utility_management',
                fromlist=['__file__'],
            ).__file__
        ).parent
        self.assertFalse((addon_root / 'controllers').exists())
        self.assertEqual(self.env['utility.management.meter'].search_count([]), 0)

    def test_connection_without_provider(self):
        from odoo.addons.utility_management.services.meter_service import MeterService
        self.assertEqual(
            MeterService(self.env).test_connection(),
            {'ok': False, 'error': 'no_provider_connected'},
        )


if __name__ == '__main__':
    unittest.main()
