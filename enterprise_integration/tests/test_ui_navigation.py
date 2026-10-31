# -*- coding: utf-8 -*-
"""Phase 5 UI navigation / sidebar / action mapping validation."""
import ast
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
VIEWS = ADDON_ROOT / 'views'

EXPECTED_MENUS = [
    ('Dashboard', 'action_ei_dashboard'),
    ('API & Webhook Management', 'action_ei_api_webhook'),
    ('Enterprise Connectors', 'action_ei_connectors'),
    ('Data Synchronization', 'action_ei_sync'),
    ('Master Data Integration', 'action_ei_master'),
    ('Integration Monitoring & Logs', 'action_ei_monitoring'),
]

PROHIBITED_PRIMARY_NAMES = {
    'erp', 'crm', 'bank', 'whatsapp', 'legacy', 'api', 'webhooks', 'api keys',
    'oauth', 'credentials', 'sync jobs', 'sync history', 'customer', 'supplier',
    'product', 'employee', 'account', 'site', 'location', 'department', 'errors',
    'mappings', 'transformations', 'conflicts', 'retries', 'settings',
}


class TestPhase5Navigation(unittest.TestCase):
    def _primary_menus(self):
        tree = ET.parse(VIEWS / 'ei_menus.xml')
        return [
            m for m in tree.findall('.//menuitem')
            if m.get('parent') == 'menu_ei_root'
        ]

    def test_exactly_six_primary_menus(self):
        self.assertEqual(len(self._primary_menus()), 6)

    def test_menu_names_and_order(self):
        children = sorted(self._primary_menus(), key=lambda m: int(m.get('sequence') or 0))
        names = [(m.get('name') or '').replace('&amp;', '&') for m in children]
        self.assertEqual(names, [n for n, _ in EXPECTED_MENUS])

    def test_menu_action_mapping(self):
        mapping = {
            (m.get('name') or '').replace('&amp;', '&'): m.get('action')
            for m in self._primary_menus()
        }
        for name, action in EXPECTED_MENUS:
            self.assertEqual(mapping[name], action, name)

    def test_no_prohibited_primary_menu_names(self):
        for m in self._primary_menus():
            name = (m.get('name') or '').replace('&amp;', '&').lower()
            self.assertNotIn(name, PROHIBITED_PRIMARY_NAMES)

    def test_no_extra_menuitems_in_any_view(self):
        all_menus = []
        for path in VIEWS.glob('*.xml'):
            for m in ET.parse(path).findall('.//menuitem'):
                all_menus.append((path.name, m.get('id'), m.get('parent'), m.get('name')))
        for fname, mid, parent, name in all_menus:
            self.assertEqual(fname, 'ei_menus.xml', f'Unexpected menuitem in {fname}: {mid}')
        self.assertEqual(len(all_menus), 7)

    def test_primary_actions_defined_once(self):
        action_ids = {a for _, a in EXPECTED_MENUS}
        found = {}
        for path in VIEWS.glob('*.xml'):
            text = path.read_text(encoding='utf-8')
            for aid in action_ids:
                if re.search(rf'id="{aid}"', text):
                    found.setdefault(aid, []).append(path.name)
        for aid in action_ids:
            self.assertEqual(len(found.get(aid, [])), 1, f'{aid} definitions: {found.get(aid)}')

    def test_primary_actions_are_ei_app_client(self):
        tree = ET.parse(VIEWS / 'ei_client_actions.xml')
        for _, aid in EXPECTED_MENUS:
            rec = tree.find(f".//record[@id='{aid}']")
            self.assertIsNotNone(rec, aid)
            self.assertEqual(rec.get('model'), 'ir.actions.client')
            tag = rec.find("./field[@name='tag']")
            self.assertEqual(tag.text, 'ei_app')

    def test_shell_assets_exist(self):
        self.assertTrue((ADDON_ROOT / 'static/src/js/ei_app.js').exists())
        self.assertTrue((ADDON_ROOT / 'static/src/xml/ei_app.xml').exists())
        self.assertTrue((ADDON_ROOT / 'static/src/scss/ei_variables.scss').exists())

    def test_scss_brand_colors_and_full_shell(self):
        scss = (ADDON_ROOT / 'static/src/scss/ei_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('.ei-shell', scss)
        self.assertIn('.ei-sidebar', scss)
        self.assertIn('height: 100%', scss)
        self.assertIn('display: grid', scss)

    def test_ei_app_js_registers_action(self):
        js = (ADDON_ROOT / 'static/src/js/ei_app.js').read_text(encoding='utf-8')
        self.assertIn('registry.category("actions").add("ei_app"', js)
        self.assertIn('enterprise_integration.App', js)

    def test_manifest_assets(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        assets = data['assets']['web.assets_backend']
        self.assertTrue(any('ei_app.js' in a for a in assets))
        self.assertTrue(any('ei_app.xml' in a for a in assets))
        self.assertTrue(any('ei_variables.scss' in a for a in assets))


if __name__ == '__main__':
    unittest.main()
