# -*- coding: utf-8 -*-
"""Phase 5 OWL UI wiring tests."""
import ast
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = ADDON_ROOT / 'static' / 'src' / 'js'
XML_ROOT = ADDON_ROOT / 'static' / 'src' / 'xml'

SCREEN_IDS = [
    'dashboard',
    'alerts',
    'monitoring',
    'incidents',
    'emergency',
    'reports',
    'report_builder',
]

RPC_BY_SCREEN = {
    'dashboard': ['get_dashboard_data'],
    'alerts': ['get_alerts_data', 'run_alert_action'],
    'monitoring': ['get_monitoring_data'],
    'incidents': ['get_incidents_data', 'run_incident_action'],
    'emergency': ['get_emergency_data', 'run_emergency_action'],
    'reports': ['get_reports_data'],
    'report_builder': ['get_report_definitions', 'run_report', 'export_report'],
}


def _read(path):
    return path.read_text(encoding='utf-8')


class TestOwlUi(unittest.TestCase):
    def test_seven_screen_files_registered(self):
        app_js = _read(JS_ROOT / 'cc_app.js')
        self.assertIn('registry.category("actions").add("command_center_app"', app_js)
        self.assertEqual(len(re.findall(r'id: "', app_js)), 7)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, app_js)
            self.assertTrue((JS_ROOT / 'screens' / ('%s.js' % screen)).exists(), screen)
            self.assertTrue((XML_ROOT / 'screens' / ('%s.xml' % screen)).exists(), screen)
            self.assertIn('./screens/%s' % screen, app_js)

    def test_exactly_seven_sidebar_items(self):
        app_js = _read(JS_ROOT / 'cc_app.js')
        labels = re.findall(r'label: "([^"]+)"', app_js)
        self.assertEqual(labels, [
            'Dashboard',
            'Alerts',
            'Monitoring',
            'Incidents',
            'Emergency',
            'Reports',
            'Report Builder',
        ])
        app_xml = _read(XML_ROOT / 'cc_app.xml')
        self.assertIn('t-foreach="screens"', app_xml)
        self.assertNotIn('cc-top-nav', app_xml)
        self.assertIn('cc-breadcrumbs', app_xml)
        self.assertIn('Command Center', app_xml)

    def test_rpc_methods_wired(self):
        app_js = _read(JS_ROOT / 'cc_app.js')
        self.assertIn('get_session_context', app_js)
        for screen, methods in RPC_BY_SCREEN.items():
            text = _read(JS_ROOT / 'screens' / ('%s.js' % screen))
            for method in methods:
                self.assertIn('"%s"' % method, text)
            self.assertIn('cc.ui.api', text)
            self.assertIn('async refresh', text)
            self.assertIn('extractError', text)
            self.assertIn('loading', text)
            self.assertIn('error', text)

    def test_refresh_and_empty_states(self):
        expected_empty = {
            'dashboard': ['No recent activity', 'No sites'],
            'alerts': ['No alerts', 'Select an alert'],
            'monitoring': ['No sites'],
            'incidents': ['No incidents', 'Select an incident'],
            'emergency': ['No emergency alerts', 'Select an emergency'],
            'reports': ['No report rows'],
            'report_builder': ['No saved report definitions', 'No exports'],
        }
        for screen, phrases in expected_empty.items():
            xml = _read(XML_ROOT / 'screens' / ('%s.xml' % screen))
            self.assertIn('cc-loading', xml)
            self.assertIn('cc-error', xml)
            self.assertIn('Retry', xml)
            self.assertIn('Refresh', xml)
            for phrase in phrases:
                self.assertIn(phrase, xml, screen)

    def test_permission_aware_action_visibility(self):
        utils = _read(JS_ROOT / 'cc_utils.js')
        self.assertIn('export function alertActions', utils)
        self.assertIn('export function incidentActions', utils)
        self.assertIn('export function emergencyActions', utils)
        self.assertIn('session.is_manager', utils)
        self.assertIn('session.is_admin', utils)
        for action in ('acknowledge', 'investigate', 'assign', 'escalate', 'resolve', 'close', 'add_note', 'reopen', 'to_incident'):
            self.assertIn('"%s"' % action, utils)
        self.assertIn('"handle_overdue"', utils)
        alerts = _read(JS_ROOT / 'screens' / 'alerts.js')
        self.assertIn('visibleActions', alerts)
        self.assertIn('Assign self', alerts)
        incidents = _read(JS_ROOT / 'screens' / 'incidents.js')
        self.assertIn('canCreate', incidents)
        self.assertIn('session.is_manager', incidents)

    def test_no_fake_kpi_or_operational_rows(self):
        pattern = re.compile(
            r'(sites_total|sites_operational|alerts_active|incidents_open|emergencies_active|unresolved_overdue)\s*[:=]\s*[1-9]'
        )
        fake_rows = re.compile(r'\[\s*\{\s*name:\s*["\'](Site|Alert|Incident)')
        for path in (JS_ROOT / 'screens').glob('*.js'):
            text = _read(path)
            self.assertIsNone(pattern.search(text), path.name)
            self.assertIsNone(fake_rows.search(text), path.name)
            self.assertNotIn('placeholder', text.lower())
            self.assertNotIn('sample data', text.lower())
        dashboard = _read(JS_ROOT / 'screens' / 'dashboard.js')
        self.assertIn('data.kpis', dashboard)
        self.assertIn('kpis: null', dashboard)

    def test_filters_use_compact_payload(self):
        utils = _read(JS_ROOT / 'cc_utils.js')
        self.assertIn('export function compactFilters', utils)
        self.assertIn('value === undefined || value === null || value === ""', utils)
        for screen in ('alerts', 'monitoring', 'incidents', 'emergency', 'reports', 'report_builder'):
            text = _read(JS_ROOT / 'screens' / ('%s.js' % screen))
            self.assertIn('compactFilters', text)

    def test_exactly_eight_menus_and_seven_client_actions(self):
        menus = ET.parse(ADDON_ROOT / 'views' / 'cc_menus.xml').findall('.//menuitem')
        self.assertEqual(len(menus), 8)
        actions = ET.parse(ADDON_ROOT / 'views' / 'cc_client_actions.xml').findall("./record[@model='ir.actions.client']")
        self.assertEqual(len(actions), 7)
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['depends'], ['base', 'web'])

    def test_no_polling_or_forbidden_integrations(self):
        blob = ''
        for path in ADDON_ROOT.rglob('*'):
            if not path.is_file() or path.suffix.lower() in {'.png', '.pyc'}:
                continue
            if 'tests' in path.parts:
                continue
            blob += _read(path) if path.suffix in {'.js', '.xml', '.scss', '.py'} else ''
        self.assertNotIn('bus.bus', blob)
        self.assertNotIn('WebSocket', blob)
        self.assertNotIn('setInterval', blob)
        self.assertNotIn('fonts.googleapis', blob)
        self.assertNotIn('accounts.google', blob)
        self.assertNotIn('stitch.withgoogle', blob)


if __name__ == '__main__':
    unittest.main()
