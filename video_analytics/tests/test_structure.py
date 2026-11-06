# -*- coding: utf-8 -*-
"""Phase 2 foundation tests for video_analytics."""
import ast
import csv
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    '__init__.py',
    '__manifest__.py',
    'models/__init__.py',
    'services/__init__.py',
    'services/cctv/__init__.py',
    'services/cctv/base.py',
    'services/cctv/stub.py',
    'security/va_security.xml',
    'security/ir.model.access.csv',
    'security/va_record_rules.xml',
    'views/va_client_actions.xml',
    'views/va_menus.xml',
    'data/va_sequence_data.xml',
    'static/description/icon.png',
    'static/src/js/va_app.js',
    'static/src/xml/va_app.xml',
    'static/src/scss/va_variables.scss',
    'tests/__init__.py',
    'tests/test_structure.py',
    'tests/test_models.py',
    'tests/test_security.py',
    'tests/test_services.py',
    'tests/test_ui_integration.py',
    'static/src/js/va_utils.js',
    'static/src/xml/va_shared.xml',
    'static/src/js/screens/va_dashboard.js',
    'static/src/js/screens/va_cctv.js',
    'static/src/js/screens/va_playback.js',
    'static/src/js/screens/va_detection.js',
    'static/src/js/screens/va_occupancy.js',
    'static/src/js/screens/va_alerts.js',
    'static/src/xml/screens/va_dashboard.xml',
    'static/src/xml/screens/va_cctv.xml',
    'static/src/xml/screens/va_playback.xml',
    'static/src/xml/screens/va_detection.xml',
    'static/src/xml/screens/va_occupancy.xml',
    'static/src/xml/screens/va_alerts.xml',
    'services/detection_ingest.py',
    'services/occupancy_ingest.py',
    'services/cctv/service.py',
    'models/va_mixin.py',
    'models/va_camera.py',
    'models/va_zone.py',
    'models/va_detection_rule.py',
    'models/va_detection.py',
    'models/va_event.py',
    'models/va_investigation_note.py',
    'models/va_occupancy_snapshot.py',
    'models/va_ui_api.py',
]

EXPECTED_CHILDREN = [
    ('Video Analytics Dashboard', 'action_va_dashboard', 'dashboard'),
    ('CCTV Integration & Live Streaming', 'action_va_cctv', 'cctv'),
    ('Video Event Playback & Investigation', 'action_va_playback', 'playback'),
    ('AI Detection & Zone Monitoring', 'action_va_detection', 'detection'),
    ('Occupancy & Crowd Monitoring', 'action_va_occupancy', 'occupancy'),
    ('Video-Based Alerts & Event Management', 'action_va_alerts', 'alerts'),
]

SCREEN_IDS = {'dashboard', 'cctv', 'playback', 'detection', 'occupancy', 'alerts'}

PROHIBITED_MENU_NAMES = {
    'event details', 'camera details', 'alert details', 'zone details',
    'investigation details', 'detection details', 'reports', 'settings',
    'configuration',
}

FORBIDDEN_DEPENDS = {
    'enterprise_integration', 'workflow_engine', 'auth_oauth', 'auth_signup',
}

FORBIDDEN_SOURCE_PATTERNS = [
    re.compile(r'stitch\.withgoogle', re.I),
    re.compile(r'fonts\.googleapis', re.I),
    re.compile(r'accounts\.google', re.I),
    re.compile(r'auth_oauth', re.I),
]

SKIP_SCAN_SUFFIXES = {'.png', '.pyc'}


class TestAddonStructure(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in REQUIRED_FILES:
            path = ADDON_ROOT / rel
            self.assertTrue(path.exists(), rel)

    def test_manifest(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['name'], 'Video Analytics')
        self.assertTrue(data['version'].startswith('18.0'))
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertEqual(data['depends'], ['base', 'web'])
        for dep in FORBIDDEN_DEPENDS:
            self.assertNotIn(dep, data['depends'])
        self.assertEqual(
            data['assets']['web.assets_backend'][0],
            'video_analytics/static/src/scss/va_variables.scss',
        )
        self.assertIn('video_analytics/static/src/js/va_app.js', data['assets']['web.assets_backend'])
        self.assertIn('video_analytics/static/src/js/screens/va_dashboard.js', data['assets']['web.assets_backend'])
        self.assertEqual(data['assets']['web.assets_backend'].count('video_analytics/static/src/js/va_app.js'), 1)
        for asset in data['assets']['web.assets_backend']:
            rel = asset.split('/', 1)[1]
            self.assertTrue((ADDON_ROOT / rel).exists(), asset)

    def test_domain_model_modules_imported(self):
        models_init = (ADDON_ROOT / 'models' / '__init__.py').read_text(encoding='utf-8')
        for name in (
            'va_mixin', 'va_camera', 'va_zone', 'va_detection_rule',
            'va_detection', 'va_event', 'va_investigation_note',
            'va_occupancy_snapshot', 'va_ui_api',
        ):
            self.assertIn('from . import %s' % name, models_init)
        self.assertNotIn('va.alert', models_init)
        self.assertNotIn('va_alert', models_init)

    def test_exactly_three_security_groups(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'va_security.xml')
        groups = {
            rec.get('id'): rec.find("./field[@name='name']").text
            for rec in tree.findall("./record[@model='res.groups']")
        }
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups['group_va_user'], 'Video Analytics User')
        self.assertEqual(groups['group_va_manager'], 'Video Analytics Manager')
        self.assertEqual(groups['group_va_admin'], 'Video Analytics Administrator')
        category = tree.find("./record[@id='module_category_video_analytics']")
        self.assertIsNotNone(category)
        self.assertEqual(category.find("./field[@name='name']").text, 'Video Analytics')

    def test_group_hierarchy(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'va_security.xml')
        manager = tree.find("./record[@id='group_va_manager']")
        admin = tree.find("./record[@id='group_va_admin']")
        self.assertIn('group_va_user', manager.find("./field[@name='implied_ids']").get('eval'))
        self.assertIn('group_va_manager', admin.find("./field[@name='implied_ids']").get('eval'))

    def test_access_csv_domain_models(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as handle:
            reader = csv.reader(handle)
            header = next(reader)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        self.assertEqual(
            header,
            ['id', 'name', 'model_id:id', 'group_id:id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
        )
        self.assertTrue(all(len(row) == 8 for row in rows))
        groups = {row[3] for row in rows}
        self.assertEqual(groups, {'group_va_user', 'group_va_manager', 'group_va_admin'})
        models = {row[2] for row in rows}
        self.assertIn('model_va_camera', models)
        self.assertIn('model_va_event', models)
        self.assertIn('model_va_ui_api', models)
        self.assertNotIn('model_va_alert', models)
        user_event = [row for row in rows if row[0] == 'access_va_event_user'][0]
        self.assertEqual(user_event[4:], ['1', '1', '0', '0'])
        user_detection = [row for row in rows if row[0] == 'access_va_detection_user'][0]
        self.assertEqual(user_detection[4:], ['1', '0', '0', '0'])

    def test_exactly_one_root_and_six_child_menus(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'va_menus.xml')
        menuitems = tree.findall('.//menuitem')
        self.assertEqual(len(menuitems), 7)
        root = [m for m in menuitems if m.get('id') == 'menu_va_root']
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].get('name'), 'Video Analytics')
        children = sorted(
            [m for m in menuitems if m.get('parent') == 'menu_va_root'],
            key=lambda m: int(m.get('sequence') or 0),
        )
        self.assertEqual(len(children), 6)
        names = [(m.get('name') or '').replace('&amp;', '&') for m in children]
        self.assertEqual(names, [n for n, _, _ in EXPECTED_CHILDREN])
        for menu in menuitems:
            name = (menu.get('name') or '').replace('&amp;', '&').lower()
            self.assertNotIn(name, PROHIBITED_MENU_NAMES)

    def test_no_extra_menus_in_views(self):
        all_menus = []
        for path in (ADDON_ROOT / 'views').glob('*.xml'):
            for menu in ET.parse(path).findall('.//menuitem'):
                all_menus.append(path.name)
        self.assertEqual(all_menus, ['va_menus.xml'] * 7)

    def test_single_client_action_tag_and_screens(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'va_client_actions.xml')
        records = tree.findall("./record[@model='ir.actions.client']")
        self.assertEqual(len(records), 6)
        screens = set()
        for rec in records:
            tag = rec.find("./field[@name='tag']")
            self.assertEqual(tag.text, 'video_analytics_app')
            self.assertEqual(rec.find("./field[@name='target']").text, 'current')
            params = rec.find("./field[@name='params']").get('eval')
            match = re.search(r"'screen':\s*'(\w+)'", params)
            self.assertIsNotNone(match, rec.get('id'))
            screens.add(match.group(1))
        self.assertEqual(screens, SCREEN_IDS)
        mapping = {
            (m.get('name') or '').replace('&amp;', '&'): m.get('action')
            for m in ET.parse(ADDON_ROOT / 'views' / 'va_menus.xml').findall('.//menuitem')
            if m.get('parent') == 'menu_va_root'
        }
        for name, action, _screen in EXPECTED_CHILDREN:
            self.assertEqual(mapping[name], action)

    def test_owl_shell_has_six_screen_ids(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'va_app.js').read_text(encoding='utf-8')
        self.assertIn('export class VideoAnalyticsApp', js)
        self.assertIn('video_analytics_app', js)
        self.assertNotIn('fonts.googleapis', js)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, js)

    def test_scss_tokens_and_prefix(self):
        scss = (ADDON_ROOT / 'static' / 'src' / 'scss' / 'va_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('#f4f5f8', scss)
        self.assertIn('.va-shell', scss)
        self.assertNotIn('fonts.googleapis', scss)
        self.assertNotIn('@import', scss)
        utils = (ADDON_ROOT / 'static' / 'src' / 'js' / 'va_utils.js').read_text(encoding='utf-8')
        self.assertIn('export function formatDatetime', utils)
        self.assertNotIn('fonts.googleapis', utils)

    def _load_stub_class(self):
        import importlib.util
        import sys
        import types
        pkg_name = 'va_cctv_iso'
        if pkg_name + '.stub' in sys.modules:
            return sys.modules[pkg_name + '.stub'].VaCctvStubAdapter
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(ADDON_ROOT / 'services' / 'cctv')]
        sys.modules[pkg_name] = pkg
        base_path = ADDON_ROOT / 'services' / 'cctv' / 'base.py'
        base_spec = importlib.util.spec_from_file_location(pkg_name + '.base', base_path)
        base_mod = importlib.util.module_from_spec(base_spec)
        sys.modules[pkg_name + '.base'] = base_mod
        base_spec.loader.exec_module(base_mod)
        stub_path = ADDON_ROOT / 'services' / 'cctv' / 'stub.py'
        stub_spec = importlib.util.spec_from_file_location(pkg_name + '.stub', stub_path)
        stub_mod = importlib.util.module_from_spec(stub_spec)
        sys.modules[pkg_name + '.stub'] = stub_mod
        stub_spec.loader.exec_module(stub_mod)
        return stub_mod.VaCctvStubAdapter

    def test_stub_adapter_has_no_network(self):
        stub = (ADDON_ROOT / 'services' / 'cctv' / 'stub.py').read_text(encoding='utf-8')
        lowered = stub.lower()
        for token in ('requests', 'urllib', 'http.client', 'import socket', 'http://', 'https://'):
            self.assertNotIn(token, lowered)
        adapter = self._load_stub_class()()
        result = adapter.test_connection()
        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'stub')
        stream = adapter.resolve_stream()
        self.assertFalse(stream['available'])

    def test_python_compiles(self):
        for py_path in ADDON_ROOT.rglob('*.py'):
            compile(py_path.read_text(encoding='utf-8'), str(py_path), 'exec')

    def test_xml_parses(self):
        for xml_path in ADDON_ROOT.rglob('*.xml'):
            ET.parse(xml_path)

    def test_no_forbidden_source_references(self):
        for path in ADDON_ROOT.rglob('*'):
            if not path.is_file() or path.suffix in SKIP_SCAN_SUFFIXES:
                continue
            if 'tests' in path.parts:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for pattern in FORBIDDEN_SOURCE_PATTERNS:
                self.assertIsNone(pattern.search(text), '%s matched %s' % (path, pattern.pattern))
            if path.name == '__manifest__.py':
                continue
            if 'enterprise_integration' in text and path.name != 'test_structure.py':
                self.fail('enterprise_integration referenced in %s' % path)
            if 'workflow_engine' in text and path.name != 'test_structure.py':
                self.fail('workflow_engine referenced in %s' % path)


try:
    from odoo.tests import TransactionCase, tagged
except ImportError:  # pragma: no cover
    TransactionCase = None
    tagged = None


if TransactionCase and tagged:

    @tagged('post_install', '-at_install', 'va_foundation')
    class TestVaInstalledFoundation(TransactionCase):
        def test_module_installed(self):
            module = self.env['ir.module.module'].search([('name', '=', 'video_analytics')], limit=1)
            self.assertTrue(module)
            self.assertEqual(module.state, 'installed')

        def test_groups_in_database(self):
            xmlids = [
                'video_analytics.group_va_user',
                'video_analytics.group_va_manager',
                'video_analytics.group_va_admin',
            ]
            for xmlid in xmlids:
                self.assertTrue(self.env.ref(xmlid))
            category = self.env.ref('video_analytics.module_category_video_analytics')
            self.assertEqual(category.name, 'Video Analytics')
            self.assertEqual(len(self.env['res.groups'].search([('category_id', '=', category.id)])), 3)

        def test_menus_in_database(self):
            root = self.env.ref('video_analytics.menu_va_root')
            children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)], order='sequence, id')
            self.assertEqual(len(children), 6)
            self.assertEqual(
                children.mapped('name'),
                [name for name, _action, _screen in EXPECTED_CHILDREN],
            )
            extra = self.env['ir.ui.menu'].search([
                ('id', 'child_of', root.id),
                ('id', '!=', root.id),
                ('id', 'not in', children.ids),
            ])
            self.assertFalse(extra)

        def test_client_actions_in_database(self):
            actions = self.env['ir.actions.client'].search([('tag', '=', 'video_analytics_app')])
            self.assertEqual(len(actions), 6)
            screens = set()
            for action in actions:
                params = action.params or {}
                screens.add(params.get('screen'))
            self.assertEqual(screens, SCREEN_IDS)
            window_data = self.env['ir.model.data'].search([
                ('module', '=', 'video_analytics'),
                ('model', '=', 'ir.actions.act_window'),
            ])
            self.assertFalse(window_data)

        def test_static_foundation_suite(self):
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddonStructure)
            result = unittest.TestResult()
            suite.run(result)
            self.assertFalse(result.errors, result.errors)
            self.assertFalse(result.failures, result.failures)
            self.assertGreaterEqual(result.testsRun, 15)


if __name__ == '__main__':
    unittest.main()
