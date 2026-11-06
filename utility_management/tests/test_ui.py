# -*- coding: utf-8 -*-
import pathlib

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

SOURCE_TITLES = (
    'Smart Meter Dashboard',
    'Meter Inventory',
    'Add/Configure Meter',
    'Meter Details & Connectivity History',
    'Electricity Monitoring',
    'Real-Time / Building-wise Electricity',
    'Electricity Consumption Details & Trends',
    'Water Consumption Details & Trends',
    'Tank & Distribution Monitoring',
    'Water Monitoring Dashboard',
    'Gas Meter & Safety Monitoring',
    'Gas Monitoring',
    'Gas Consumption Details & Trends',
    'Power Source Dashboard',
    'Grid & Generator Monitoring',
    'Power Source History & Usage',
    'Consumption Details / Analysis',
    'Overall Consumption Dashboard',
    'Consumption Comparison & Trends',
    'Meter Reading List',
    'Add/Record Meter Reading',
    'Leak Detection Dashboard',
    'Meter Reading Details',
    'Active Leak / Incident List',
    'Leak Incident Details',
    'Utility Alerts Dashboard',
    'Alerts List',
    'Alert Details',
    'Utility Reports Dashboard',
    'Report Builder',
    'Report Detail',
)

API_METHODS = (
    'get_dashboard', 'list_meters', 'save_meter', 'get_meter', 'list_connectivity',
    'test_meter_connection', 'set_meter_status', 'get_electricity_overview',
    'get_electricity_buildings', 'get_electricity_trends', 'get_water_trends',
    'get_water_tanks', 'get_water_overview', 'get_gas_safety', 'get_gas_overview',
    'get_gas_trends', 'get_power_overview', 'list_power_sources',
    'transition_power_source', 'get_power_history', 'get_consumption_analysis',
    'get_consumption_overview', 'get_consumption_comparison', 'list_readings',
    'create_reading', 'attach_reading_photo', 'get_reading', 'verify_reading',
    'invalidate_reading', 'correct_reading', 'get_leak_overview', 'list_leaks',
    'get_leak', 'assign_leak', 'transition_leak', 'add_leak_action',
    'get_alert_overview', 'list_alerts', 'get_alert', 'acknowledge_alert',
    'start_alert', 'resolve_alert', 'close_alert', 'list_alert_rules',
    'save_alert_rule', 'get_report_overview', 'list_report_definitions',
    'save_report_definition', 'run_report', 'get_report_run', 'get_settings',
    'save_settings', 'list_scopes', 'save_scope',
)


@tagged('post_install', '-at_install', 'utility_ui')
class TestUtilityUi(TransactionCase):

    def test_thirty_one_screens_stay_inside_twelve_actions(self):
        addon = pathlib.Path(
            __import__('odoo.addons.utility_management', fromlist=['__file__']).__file__
        ).parent
        script = (addon / 'static' / 'src' / 'js' / 'utility_app.js').read_text(encoding='utf-8')
        template = (addon / 'static' / 'src' / 'xml' / 'utility_app.xml').read_text(encoding='utf-8')
        for title in SOURCE_TITLES:
            self.assertIn(title, script)
        self.assertEqual(script.count('parent:'), 31)
        self.assertIn('data-page', template)
        self.assertIn('Loading', template)
        self.assertIn('No records yet.', template)
        self.assertIn('role="alert"', template)
        actions = self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'ir.actions.client'),
        ])
        menus = self.env['ir.model.data'].search([
            ('module', '=', 'utility_management'),
            ('model', '=', 'ir.ui.menu'),
        ])
        self.assertEqual(len(actions), 12)
        self.assertEqual(len(menus), 13)
        api = self.env['utility.management.ui.api']
        for method in API_METHODS:
            self.assertTrue(hasattr(api, method))

    def test_screens_use_real_api_payloads_and_permissions(self):
        api = self.env['utility.management.ui.api']
        dashboard = api.get_dashboard({})
        self.assertIn('total', dashboard)
        self.assertIn('counts', dashboard)
        self.assertIsInstance(api.list_meters({}), list)
        self.assertIsInstance(api.list_readings({}), list)
        self.assertIsInstance(api.get_electricity_overview({}), dict)
        self.assertIsInstance(api.get_water_overview({}), dict)
        self.assertIsInstance(api.get_gas_overview({}), dict)
        self.assertIsInstance(api.get_power_overview({}), dict)
        self.assertIn('electricity', api.get_consumption_overview({}))
        self.assertIn('definitions', api.get_report_overview())
        settings = api.get_settings()
        self.assertIn('verification_required', settings)
        staff = self.env['res.users'].create({
            'name': 'Utility UI Staff',
            'login': 'utility_ui_staff',
            'groups_id': [(6, 0, [self.env.ref('utility_management.group_utility_staff').id])],
        })
        staff_api = api.with_user(staff)
        self.assertFalse(staff_api.health()['is_facility_manager'])
        self.assertIsInstance(staff_api.list_meters({}), list)
        with self.assertRaises(AccessError):
            staff_api.save_meter({'name': 'Denied', 'meter_code': 'UI-1', 'utility_type': 'gas'})
        with self.assertRaises(AccessError):
            staff_api.save_settings({'verification_required': False})
        with self.assertRaises(AccessError):
            staff_api.save_alert_rule({'name': 'Denied', 'rule_type': 'threshold'})
        definition = api.save_report_definition({
            'name': 'UI electricity',
            'report_type': 'electricity_consumption',
            'grouping': 'day',
        })
        failed = api.run_report(definition['id'], 'pdf')
        if failed['execution_state'] == 'completed':
            payload = api.download_private_file(failed['attachment_id'])
            self.assertTrue(payload['datas'])
        else:
            self.assertEqual(failed['execution_state'], 'failed')
            self.assertTrue(failed['error_message'])
            self.assertFalse(failed['attachment_id'])
        csv_run = api.run_report(definition['id'], 'csv')
        self.assertEqual(csv_run['execution_state'], 'completed')
        downloaded = api.download_private_file(csv_run['attachment_id'])
        self.assertIn('datas', downloaded)
        self.assertNotIn('url', downloaded)
