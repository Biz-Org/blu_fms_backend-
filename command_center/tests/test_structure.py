# -*- coding: utf-8 -*-
"""Phase 2 foundation tests for command_center."""
import ast
import csv
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CHILDREN = [
    ('Command Center Dashboard', 'action_cc_dashboard', 'dashboard'),
    ('Central Alert Management', 'action_cc_alerts', 'alerts'),
    ('Multi-Site & Real-Time Monitoring', 'action_cc_monitoring', 'monitoring'),
    ('Incident Dashboard', 'action_cc_incidents', 'incidents'),
    ('Emergency Alerts & Escalation', 'action_cc_emergency', 'emergency'),
    ('Command Center Reports', 'action_cc_reports', 'reports'),
    ('Command Center Report Builder & Export', 'action_cc_report_builder', 'report_builder'),
]

SCREEN_IDS = {
    'dashboard',
    'alerts',
    'monitoring',
    'incidents',
    'emergency',
    'reports',
    'report_builder',
}

FORBIDDEN_DEPENDS = {
    'video_analytics',
    'workflow_engine',
    'enterprise_integration',
    'mail',
    'auth_oauth',
    'queue_job',
}

FORBIDDEN_SOURCE_PATTERNS = [
    re.compile(r'stitch\.withgoogle', re.I),
    re.compile(r'fonts\.googleapis', re.I),
    re.compile(r'accounts\.google', re.I),
    re.compile(r'cdn\.', re.I),
    re.compile(r'auth_oauth', re.I),
]


class TestAddonStructure(unittest.TestCase):
    def test_manifest_exists(self):
        self.assertTrue((ADDON_ROOT / '__manifest__.py').exists())

    def test_manifest_version_and_depends(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['name'], 'Command Center')
        self.assertEqual(data['version'], '18.0.1.0.0')
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertFalse(data.get('auto_install'))
        self.assertEqual(data['depends'], ['base', 'web'])
        for dep in FORBIDDEN_DEPENDS:
            self.assertNotIn(dep, data['depends'])
        self.assertEqual(
            data['data'],
            [
                'security/cc_security.xml',
                'security/ir.model.access.csv',
                'security/cc_record_rules.xml',
                'data/cc_sequence_data.xml',
                'views/cc_client_actions.xml',
                'views/cc_menus.xml',
            ],
        )
        assets = data['assets']['web.assets_backend']
        self.assertEqual(assets[0], 'command_center/static/src/scss/cc_variables.scss')
        self.assertEqual(
            assets,
            [
                'command_center/static/src/scss/cc_variables.scss',
                'command_center/static/src/scss/cc_screens.scss',
                'command_center/static/src/js/cc_utils.js',
                'command_center/static/src/js/screens/dashboard.js',
                'command_center/static/src/js/screens/alerts.js',
                'command_center/static/src/js/screens/monitoring.js',
                'command_center/static/src/js/screens/incidents.js',
                'command_center/static/src/js/screens/emergency.js',
                'command_center/static/src/js/screens/reports.js',
                'command_center/static/src/js/screens/report_builder.js',
                'command_center/static/src/js/cc_app.js',
                'command_center/static/src/xml/cc_app.xml',
                'command_center/static/src/xml/screens/dashboard.xml',
                'command_center/static/src/xml/screens/alerts.xml',
                'command_center/static/src/xml/screens/monitoring.xml',
                'command_center/static/src/xml/screens/incidents.xml',
                'command_center/static/src/xml/screens/emergency.xml',
                'command_center/static/src/xml/screens/reports.xml',
                'command_center/static/src/xml/screens/report_builder.xml',
            ],
        )
        self.assertEqual(assets.count('command_center/static/src/js/cc_app.js'), 1)

    def test_forbidden_sibling_dependencies_absent(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertNotIn('video_analytics', data['depends'])
        self.assertNotIn('workflow_engine', data['depends'])
        self.assertNotIn('enterprise_integration', data['depends'])
        self.assertNotIn('mail', data['depends'])

    def test_exactly_eight_menus(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'cc_menus.xml')
        menuitems = tree.findall('.//menuitem')
        self.assertEqual(len(menuitems), 8)
        root = [m for m in menuitems if m.get('id') == 'menu_cc_root']
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].get('name'), 'Command Center')
        self.assertEqual(root[0].get('sequence'), '55')
        self.assertEqual(root[0].get('web_icon'), 'command_center,static/description/icon.png')
        children = [m for m in menuitems if m.get('parent') == 'menu_cc_root']
        self.assertEqual(len(children), 7)

    def test_exactly_seven_child_menu_names(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'cc_menus.xml')
        children = sorted(
            [m for m in tree.findall('.//menuitem') if m.get('parent') == 'menu_cc_root'],
            key=lambda m: int(m.get('sequence') or 0),
        )
        names = [(m.get('name') or '').replace('&amp;', '&') for m in children]
        self.assertEqual(names, [name for name, _action, _screen in EXPECTED_CHILDREN])
        xmlids = [m.get('id') for m in children]
        self.assertEqual(xmlids, [
            'menu_cc_dashboard',
            'menu_cc_alerts',
            'menu_cc_monitoring',
            'menu_cc_incidents',
            'menu_cc_emergency',
            'menu_cc_reports',
            'menu_cc_report_builder',
        ])
        for menu in tree.findall('.//menuitem'):
            self.assertEqual(menu.get('groups'), 'command_center.group_cc_user')

    def test_exactly_seven_client_actions(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'cc_client_actions.xml')
        records = tree.findall("./record[@model='ir.actions.client']")
        self.assertEqual(len(records), 7)
        screens = set()
        for rec in records:
            tag = rec.find("./field[@name='tag']")
            self.assertEqual(tag.text, 'command_center_app')
            self.assertEqual(rec.find("./field[@name='target']").text, 'current')
            context = rec.find("./field[@name='context']").text or ''
            params = rec.find("./field[@name='params']").get('eval')
            ctx_match = re.search(r"'cc_screen':\s*'(\w+)'", context)
            param_match = re.search(r"'screen':\s*'(\w+)'", params)
            self.assertIsNotNone(ctx_match, rec.get('id'))
            self.assertIsNotNone(param_match, rec.get('id'))
            self.assertEqual(ctx_match.group(1), param_match.group(1))
            screens.add(param_match.group(1))
        self.assertEqual(screens, SCREEN_IDS)

    def test_all_seven_screen_ids_exist(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'cc_app.js').read_text(encoding='utf-8')
        self.assertIn('export class CommandCenterApp', js)
        self.assertIn('command_center_app', js)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, js)

    def test_css_prefix_cc(self):
        scss = (ADDON_ROOT / 'static' / 'src' / 'scss' / 'cc_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('#f4f5f8', scss)
        self.assertIn('.cc-shell', scss)
        self.assertIn('ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif', scss)
        self.assertNotIn('fonts.googleapis', scss)
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'cc_app.xml').read_text(encoding='utf-8')
        self.assertIn('cc-shell', xml)
        self.assertIn('cc-sidebar', xml)
        self.assertIn('cc-nav-item', xml)

    def test_security_groups_exactly_three(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'cc_security.xml')
        groups = {
            rec.get('id'): rec.find("./field[@name='name']").text
            for rec in tree.findall("./record[@model='res.groups']")
        }
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups['group_cc_user'], 'Command Center User')
        self.assertEqual(groups['group_cc_manager'], 'Command Center Manager')
        self.assertEqual(groups['group_cc_admin'], 'Command Center Administrator')

    def test_sequence_xmlids_exactly_three(self):
        tree = ET.parse(ADDON_ROOT / 'data' / 'cc_sequence_data.xml')
        records = tree.findall("./record[@model='ir.sequence']")
        self.assertEqual(len(records), 3)
        xmlids = {rec.get('id') for rec in records}
        self.assertEqual(xmlids, {'seq_cc_site', 'seq_cc_alert', 'seq_cc_incident'})
        codes = {}
        for rec in records:
            code = rec.find("./field[@name='code']").text
            prefix = rec.find("./field[@name='prefix']").text
            padding = rec.find("./field[@name='padding']").text
            codes[rec.get('id')] = (code, prefix, padding)
        self.assertEqual(codes['seq_cc_site'], ('cc.site', 'CC-SITE', '5'))
        self.assertEqual(codes['seq_cc_alert'], ('cc.alert', 'CC-ALT', '5'))
        self.assertEqual(codes['seq_cc_incident'], ('cc.incident', 'CC-INC', '5'))

    def test_access_csv_matrix(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as handle:
            reader = csv.reader(handle)
            header = next(reader)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        self.assertEqual(
            header,
            ['id', 'name', 'model_id:id', 'group_id:id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
        )
        groups = {row[3] for row in rows}
        self.assertEqual(groups, {'group_cc_user', 'group_cc_manager', 'group_cc_admin'})
        by_id = {row[0]: row for row in rows}
        self.assertEqual(by_id['access_cc_site_user'][4:], ['1', '0', '0', '0'])
        self.assertEqual(by_id['access_cc_site_manager'][4:], ['1', '1', '1', '0'])
        self.assertEqual(by_id['access_cc_site_admin'][4:], ['1', '1', '1', '1'])
        self.assertEqual(by_id['access_cc_alert_user'][4:], ['1', '1', '1', '0'])
        self.assertEqual(by_id['access_cc_incident_user'][4:], ['1', '1', '1', '0'])
        self.assertEqual(by_id['access_cc_escalation_history_manager'][4:], ['1', '0', '0', '0'])
        self.assertEqual(by_id['access_cc_investigation_note_user'][4:], ['1', '0', '1', '0'])
        self.assertEqual(by_id['access_cc_report_export_manager'][4:], ['1', '0', '1', '0'])
        self.assertEqual(by_id['access_cc_ui_api_user'][4:], ['1', '0', '0', '0'])
        self.assertEqual(by_id['access_cc_ui_api_admin'][4:], ['1', '0', '0', '0'])

    def test_record_rules_company_only(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'cc_record_rules.xml')
        rules = tree.findall("./record[@model='ir.rule']")
        self.assertEqual(len(rules), 8)
        domain = "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
        for rec in rules:
            self.assertEqual(rec.find("./field[@name='domain_force']").text, domain)
        xml = (ADDON_ROOT / 'security' / 'cc_record_rules.xml').read_text(encoding='utf-8')
        self.assertNotIn('model_cc_ui_api', xml)

    def test_python_files_compile(self):
        for py_path in ADDON_ROOT.rglob('*.py'):
            compile(py_path.read_text(encoding='utf-8'), str(py_path), 'exec')

    def test_no_forbidden_external_sources(self):
        for path in ADDON_ROOT.rglob('*'):
            if not path.is_file() or path.suffix.lower() in {'.png', '.pyc'}:
                continue
            if 'tests' in path.parts:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for pattern in FORBIDDEN_SOURCE_PATTERNS:
                self.assertIsNone(pattern.search(text), '%s in %s' % (pattern.pattern, path))

    def test_no_fake_operational_data(self):
        data_xml = (ADDON_ROOT / 'data' / 'cc_sequence_data.xml').read_text(encoding='utf-8')
        self.assertNotIn('model="cc.alert"', data_xml)
        self.assertNotIn('model="cc.incident"', data_xml)
        self.assertNotIn('model="cc.site"', data_xml)
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'cc_app.js').read_text(encoding='utf-8')
        self.assertNotIn('kpis', js)
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'cc_app.xml').read_text(encoding='utf-8')
        self.assertNotIn('No operational data', xml)
        self.assertIn('DashboardScreen', xml)
        for path in (ADDON_ROOT / 'static' / 'src' / 'js' / 'screens').glob('*.js'):
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'sites_total\s*[:=]\s*[1-9]')
            self.assertNotRegex(text, r'alerts_active\s*[:=]\s*[1-9]')
            self.assertNotIn('bus.bus', text)
            self.assertNotIn('WebSocket', text)

    def test_phase2_services_have_no_engines(self):
        for name in ('alert_service.py', 'incident_service.py', 'escalation_service.py', 'report_service.py', 'va_adapter.py'):
            text = (ADDON_ROOT / 'services' / name).read_text(encoding='utf-8')
            self.assertNotIn('ir.cron', text)
            self.assertNotIn('va.event', text)
            self.assertNotIn('workflow.engine', text)


if __name__ == '__main__':
    unittest.main()
