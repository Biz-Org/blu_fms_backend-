# -*- coding: utf-8 -*-
"""Structure / foundation tests runnable with or without full Odoo transaction cases.

When Odoo test runner is available, TransactionCase tests exercise models & security.
"""
import ast
import csv
import os
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]


class TestAddonStructure(unittest.TestCase):
    def test_manifest_exists_and_version(self):
        manifest_path = ADDON_ROOT / '__manifest__.py'
        self.assertTrue(manifest_path.exists())
        data = ast.literal_eval(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(data['version'], '18.0.1.4.7')
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertEqual(data['depends'], ['base', 'web'])

    def test_exactly_six_primary_menus(self):
        menus_xml = ADDON_ROOT / 'views' / 'ei_menus.xml'
        tree = ET.parse(menus_xml)
        menuitems = tree.findall('.//menuitem')
        root = [m for m in menuitems if m.get('id') == 'menu_ei_root']
        self.assertEqual(len(root), 1)
        children = [m for m in menuitems if m.get('parent') == 'menu_ei_root']
        self.assertEqual(len(children), 6)
        names = {m.get('name') for m in children}
        expected = {
            'Dashboard',
            'API & Webhook Management',
            'Enterprise Connectors',
            'Data Synchronization',
            'Master Data Integration',
            'Integration Monitoring & Logs',
        }
        # XML may escape & as &amp; in attribute via parser
        normalized = set()
        for n in names:
            normalized.add(n.replace('&amp;', '&'))
        self.assertEqual(normalized, expected)

    def test_menu_action_mapping(self):
        menus_xml = ADDON_ROOT / 'views' / 'ei_menus.xml'
        tree = ET.parse(menus_xml)
        mapping = {
            m.get('name').replace('&amp;', '&'): m.get('action')
            for m in tree.findall('.//menuitem')
            if m.get('parent') == 'menu_ei_root'
        }
        self.assertEqual(mapping['Dashboard'], 'action_ei_dashboard')
        self.assertEqual(mapping['API & Webhook Management'], 'action_ei_api_webhook')
        self.assertEqual(mapping['Enterprise Connectors'], 'action_ei_connectors')
        self.assertEqual(mapping['Data Synchronization'], 'action_ei_sync')
        self.assertEqual(mapping['Master Data Integration'], 'action_ei_master')
        self.assertEqual(mapping['Integration Monitoring & Logs'], 'action_ei_monitoring')

    def test_no_prohibited_menu_names(self):
        menus_xml = ADDON_ROOT / 'views' / 'ei_menus.xml'
        tree = ET.parse(menus_xml)
        names = [
            (m.get('name') or '').replace('&amp;', '&').lower()
            for m in tree.findall('.//menuitem')
        ]
        prohibited = {
            'erp', 'crm', 'bank', 'whatsapp', 'legacy', 'api keys', 'oauth',
            'credentials', 'sync history', 'customer', 'supplier', 'product',
            'employee', 'account', 'site', 'department', 'errors', 'field mapping',
            'conflicts', 'transformation',
        }
        for name in names:
            self.assertNotIn(name, prohibited)
            # also ensure prohibited tokens are not standalone menu titles
            for p in prohibited:
                if name == p:
                    self.fail(f'Prohibited menu name: {name}')

    def test_all_xml_parses(self):
        for xml_path in ADDON_ROOT.rglob('*.xml'):
            if 'static' in xml_path.parts and xml_path.name.endswith('.xml'):
                # QWeb templates may use OWL attrs; still should parse as XML
                pass
            ET.parse(xml_path)

    def test_access_csv_header(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        self.assertEqual(
            header,
            ['id', 'name', 'model_id:id', 'group_id:id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
        )

    def test_python_files_compile(self):
        for py in ADDON_ROOT.rglob('*.py'):
            source = py.read_text(encoding='utf-8')
            compile(source, str(py), 'exec')


if __name__ == '__main__':
    unittest.main()
