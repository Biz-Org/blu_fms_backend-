# -*- coding: utf-8 -*-
"""Phase 2 menu / client-action / asset validation."""
import ast
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
VIEWS = ADDON_ROOT / 'views'

EXPECTED_MENUS = [
    ('Dashboard', 'action_we_dashboard', 'dashboard'),
    ('Workflow Builder', 'action_we_builder', 'builder'),
    ('Workflow Templates', 'action_we_templates', 'templates'),
    ('Approval & Rule Management', 'action_we_approvals', 'approvals'),
    ('Task & Execution Management', 'action_we_tasks', 'tasks'),
    ('Notifications & Approval Tracking', 'action_we_notifications', 'notifications'),
    ('Workflow Analytics & Reports', 'action_we_analytics', 'analytics'),
]

PROHIBITED_PRIMARY_NAMES = {
    'nodes', 'triggers', 'conditions', 'approvals', 'tasks', 'escalations',
    'notifications', 'executions', 'logs', 'versions', 'settings',
    'reports', 'configuration', 'report configuration',
}


class TestPhase2Navigation(unittest.TestCase):
    def _primary_menus(self):
        tree = ET.parse(VIEWS / 'we_menus.xml')
        return [
            m for m in tree.findall('.//menuitem')
            if m.get('parent') == 'menu_we_root'
        ]

    def test_exactly_seven_primary_menus(self):
        self.assertEqual(len(self._primary_menus()), 7)

    def test_menu_names_and_order(self):
        children = sorted(self._primary_menus(), key=lambda m: int(m.get('sequence') or 0))
        names = [(m.get('name') or '').replace('&amp;', '&') for m in children]
        self.assertEqual(names, [n for n, _, _ in EXPECTED_MENUS])

    def test_menu_action_mapping(self):
        mapping = {
            (m.get('name') or '').replace('&amp;', '&'): m.get('action')
            for m in self._primary_menus()
        }
        for name, action, _screen in EXPECTED_MENUS:
            self.assertEqual(mapping[name], action, name)

    def test_no_prohibited_primary_menu_names(self):
        for menu in self._primary_menus() + [
            m for m in ET.parse(VIEWS / 'we_menus.xml').findall('.//menuitem')
            if m.get('id') == 'menu_we_root'
        ]:
            name = (menu.get('name') or '').replace('&amp;', '&').lower()
            self.assertNotIn(name, PROHIBITED_PRIMARY_NAMES)

    def test_no_extra_menuitems_in_any_view(self):
        all_menus = []
        for path in VIEWS.glob('*.xml'):
            for menu in ET.parse(path).findall('.//menuitem'):
                all_menus.append((path.name, menu.get('id')))
        for fname, _mid in all_menus:
            self.assertEqual(fname, 'we_menus.xml')
        self.assertEqual(len(all_menus), 8)

    def test_primary_actions_are_same_client_tag(self):
        tree = ET.parse(VIEWS / 'we_client_actions.xml')
        for _name, action_id, screen in EXPECTED_MENUS:
            rec = tree.find(f".//record[@id='{action_id}']")
            self.assertIsNotNone(rec, action_id)
            self.assertEqual(rec.get('model'), 'ir.actions.client')
            tag = rec.find("./field[@name='tag']")
            self.assertEqual(tag.text, 'workflow_engine_app')
            target = rec.find("./field[@name='target']")
            self.assertEqual(target.text, 'current')
            params = rec.find("./field[@name='params']")
            self.assertIsNotNone(params)
            self.assertIn(f"'{screen}'", params.get('eval') or '')

    def test_shell_assets_exist(self):
        self.assertTrue((ADDON_ROOT / 'static/src/js/we_app.js').exists())
        self.assertTrue((ADDON_ROOT / 'static/src/xml/we_app.xml').exists())
        self.assertTrue((ADDON_ROOT / 'static/src/scss/we_variables.scss').exists())

    def test_scss_brand_colors_and_shell(self):
        scss = (ADDON_ROOT / 'static/src/scss/we_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('.we-shell', scss)
        self.assertIn('.we-sidebar', scss)

    def test_we_app_js_registers_action(self):
        js = (ADDON_ROOT / 'static/src/js/we_app.js').read_text(encoding='utf-8')
        self.assertIn('registry.category("actions").add("workflow_engine_app"', js)
        self.assertIn('workflow_engine.App', js)
        self.assertIn('class WorkflowEngineApp', js)
        for _name, _action, screen in EXPECTED_MENUS:
            self.assertIn(f'id: "{screen}"', js)

    def test_no_horizontal_duplicate_nav(self):
        xml = (ADDON_ROOT / 'static/src/xml/we_app.xml').read_text(encoding='utf-8')
        self.assertIn('we-sidebar', xml)
        self.assertNotIn('we-horizontal-nav', xml)
        self.assertIn('WeDashboard', xml)
        self.assertIn('WeBuilder', xml)
        self.assertNotIn('Phase 2 Foundation', xml)

    def test_manifest_assets(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        assets = data['assets']['web.assets_backend']
        self.assertTrue(any('we_app.js' in item for item in assets))
        self.assertTrue(any('we_app.xml' in item for item in assets))
        self.assertTrue(any('we_variables.scss' in item for item in assets))
        self.assertTrue(any('we_builder.js' in item for item in assets))
        self.assertTrue(any('we_dashboard.xml' in item for item in assets))
        this.assertEqual(data['version'], '18.0.1.8.2')

    def test_seven_screen_components_exist(self):
        js_dir = ADDON_ROOT / 'static/src/js/screens'
        xml_dir = ADDON_ROOT / 'static/src/xml/screens'
        for name in (
            'we_dashboard', 'we_builder', 'we_templates', 'we_approvals',
            'we_tasks', 'we_notifications', 'we_analytics',
        ):
            self.assertTrue((js_dir / f'{name}.js').exists(), name)
            self.assertTrue((xml_dir / f'{name}.xml').exists(), name)


if __name__ == '__main__':
    unittest.main()
