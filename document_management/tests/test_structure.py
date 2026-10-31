# -*- coding: utf-8 -*-
"""Phase 2 foundation tests for document_management."""
import ast
import csv
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CHILDREN = [
    ('Document Management Dashboard', 'action_dm_dashboard', 'dashboard'),
    ('Document Repository', 'action_dm_repository', 'repository'),
    ('Document Upload', 'action_dm_upload', 'upload'),
    ('Document Details', 'action_dm_details', 'details'),
    ('Access Control & Sharing', 'action_dm_access', 'access'),
    ('Approval & Expiry', 'action_dm_approval', 'approval'),
    ('Document Workflow', 'action_dm_workflow', 'workflow'),
    ('Document Search', 'action_dm_search', 'search'),
    ('Activity & Audit', 'action_dm_audit', 'audit'),
]

SCREEN_IDS = {
    'dashboard',
    'repository',
    'upload',
    'details',
    'access',
    'approval',
    'workflow',
    'search',
    'audit',
}

FORBIDDEN_DEPENDS = {
    'video_analytics',
    'workflow_engine',
    'enterprise_integration',
    'command_center',
    'mail',
    'hr',
    'documents',
    'knowledge',
    'auth_oauth',
    'queue_job',
}

FORBIDDEN_SOURCE_PATTERNS = [
    re.compile(r'stitch\.withgoogle', re.I),
    re.compile(r'fonts\.googleapis', re.I),
    re.compile(r'accounts\.google', re.I),
    re.compile(r'cdn\.', re.I),
    re.compile(r'auth_oauth', re.I),
    re.compile(r'openai', re.I),
    re.compile(r'gemini', re.I),
]


class TestAddonStructure(unittest.TestCase):
    def test_manifest_exists(self):
        self.assertTrue((ADDON_ROOT / '__manifest__.py').exists())

    def test_manifest_version_and_depends(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['name'], 'Document Management')
        self.assertEqual(data['version'], '18.0.1.0.31')
        self.assertEqual(data['category'], 'Productivity')
        self.assertEqual(data['author'], 'FMS')
        self.assertEqual(data['license'], 'LGPL-3')
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertFalse(data.get('auto_install'))
        self.assertEqual(data['depends'], ['base', 'web'])
        for dep in FORBIDDEN_DEPENDS:
            self.assertNotIn(dep, data['depends'])
        self.assertEqual(
            data['data'],
            [
                'security/dm_security.xml',
                'security/ir.model.access.csv',
                'security/dm_record_rules.xml',
                'data/dm_sequence_data.xml',
                'views/dm_client_actions.xml',
                'views/dm_menus.xml',
            ],
        )
        assets = data['assets']['web.assets_backend']
        self.assertEqual(assets[0], 'document_management/static/src/scss/dm_variables.scss')
        self.assertEqual(assets.count('document_management/static/src/js/dm_app.js'), 1)

    def test_exactly_nine_menus(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'dm_menus.xml')
        menuitems = tree.findall('.//menuitem')
        self.assertEqual(len(menuitems), 10)
        root = [m for m in menuitems if m.get('id') == 'menu_dm_root']
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].get('name'), 'Document Management')
        self.assertEqual(root[0].get('sequence'), '60')
        self.assertEqual(root[0].get('web_icon'), 'document_management,static/description/icon.png')
        children = [m for m in menuitems if m.get('parent') == 'menu_dm_root']
        self.assertEqual(len(children), 9)

    def test_exactly_eight_child_menu_names(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'dm_menus.xml')
        children = sorted(
            [m for m in tree.findall('.//menuitem') if m.get('parent') == 'menu_dm_root'],
            key=lambda m: int(m.get('sequence') or 0),
        )
        names = [(m.get('name') or '').replace('&amp;', '&') for m in children]
        self.assertEqual(names, [name for name, _action, _screen in EXPECTED_CHILDREN])
        for menu in tree.findall('.//menuitem'):
            self.assertEqual(menu.get('groups'), 'document_management.group_dm_user')

    def test_exactly_eight_client_actions(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'dm_client_actions.xml')
        records = tree.findall("./record[@model='ir.actions.client']")
        self.assertEqual(len(records), 9)
        screens = set()
        for rec in records:
            tag = rec.find("./field[@name='tag']")
            self.assertEqual(tag.text, 'document_management_app')
            self.assertEqual(rec.find("./field[@name='target']").text, 'current')
            context = rec.find("./field[@name='context']").text or ''
            params = rec.find("./field[@name='params']").get('eval')
            ctx_match = re.search(r"'dm_screen':\s*'(\w+)'", context)
            param_match = re.search(r"'screen':\s*'(\w+)'", params)
            self.assertIsNotNone(ctx_match, rec.get('id'))
            self.assertIsNotNone(param_match, rec.get('id'))
            self.assertEqual(ctx_match.group(1), param_match.group(1))
            screens.add(param_match.group(1))
        self.assertEqual(screens, SCREEN_IDS)

    def test_all_eight_screen_ids_exist(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'dm_app.js').read_text(encoding='utf-8')
        self.assertIn('export class DocumentManagementApp', js)
        self.assertIn('document_management_app', js)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, js)

    def test_css_prefix_dm(self):
        scss = (ADDON_ROOT / 'static' / 'src' / 'scss' / 'dm_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('.dm-shell', scss)
        self.assertNotIn('fonts.googleapis', scss)
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'dm_app.xml').read_text(encoding='utf-8')
        self.assertIn('dm-shell', xml)
        self.assertIn('dm-sidebar', xml)
        self.assertNotIn('Utility Pro', xml)

    def test_security_groups_exactly_three(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'dm_security.xml')
        groups = {
            rec.get('id'): rec.find("./field[@name='name']").text
            for rec in tree.findall("./record[@model='res.groups']")
        }
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups['group_dm_user'], 'Document Management User')
        self.assertEqual(groups['group_dm_manager'], 'Document Management Manager')
        self.assertEqual(groups['group_dm_admin'], 'Document Management Administrator')

    def test_sequence_xmlid(self):
        tree = ET.parse(ADDON_ROOT / 'data' / 'dm_sequence_data.xml')
        records = tree.findall("./record[@model='ir.sequence']")
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.get('id'), 'seq_dm_document')
        self.assertEqual(rec.find("./field[@name='code']").text, 'document.management.document')
        self.assertEqual(rec.find("./field[@name='prefix']").text, 'DM')

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
        self.assertEqual(groups, {'group_dm_user', 'group_dm_manager', 'group_dm_admin'})
        by_id = {row[0]: row for row in rows}
        self.assertEqual(by_id['access_dm_document_user'][4:], ['1', '1', '1', '0'])
        self.assertEqual(by_id['access_dm_document_admin'][4:], ['1', '1', '1', '1'])
        self.assertEqual(by_id['access_dm_audit_event_user'][4:], ['1', '0', '0', '0'])
        self.assertEqual(by_id['access_dm_ui_api_user'][4:], ['1', '0', '0', '0'])

    def test_python_files_compile(self):
        for py_path in ADDON_ROOT.rglob('*.py'):
            compile(py_path.read_text(encoding='utf-8'), str(py_path), 'exec')

    def test_xml_files_parse(self):
        for xml_path in ADDON_ROOT.rglob('*.xml'):
            ET.parse(xml_path)

    def test_no_forbidden_external_sources(self):
        for path in ADDON_ROOT.rglob('*'):
            if not path.is_file() or path.suffix.lower() in {'.png', '.pyc'}:
                continue
            if 'tests' in path.parts:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for pattern in FORBIDDEN_SOURCE_PATTERNS:
                self.assertIsNone(pattern.search(text), '%s in %s' % (pattern.pattern, path))

    def test_no_debug_leftovers_in_frontend(self):
        leftovers = re.compile(r'console\.(log|debug|info)\(')
        for path in (ADDON_ROOT / 'static' / 'src').rglob('*'):
            if path.suffix.lower() not in {'.js', '.xml', '.scss'}:
                continue
            text = path.read_text(encoding='utf-8')
            self.assertIsNone(leftovers.search(text), path)
            self.assertNotIn('TODO', text, path)
            self.assertNotIn('t-raw', text, path)
            self.assertNotIn('innerHTML', text, path)

    def test_no_seed_operational_data(self):
        data_xml = (ADDON_ROOT / 'data' / 'dm_sequence_data.xml').read_text(encoding='utf-8')
        self.assertNotIn('model="document.management.document"', data_xml)
        self.assertNotIn('model="document.management.category"', data_xml)
        self.assertNotIn('model="document.management.document.type"', data_xml)
        self.assertNotIn('model="document.management.folder"', data_xml)
        self.assertNotIn('model="document.management.tag"', data_xml)
        self.assertNotIn('Policies', data_xml)
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'dm_app.js').read_text(encoding='utf-8')
        self.assertNotIn('Utility Pro', js)

    def test_required_model_files_exist(self):
        names = [
            'dm_mixin.py', 'dm_document.py', 'dm_version.py', 'dm_category.py',
            'dm_document_type.py', 'dm_folder.py', 'dm_tag.py', 'dm_favorite.py',
            'dm_comment.py', 'dm_access_group.py', 'dm_access_rule.py',
            'dm_share_link.py', 'dm_approval_request.py', 'dm_approval_step.py',
            'dm_audit_event.py', 'dm_notification.py', 'dm_ai_provider.py',
            'dm_ui_api.py',
        ]
        for name in names:
            self.assertTrue((ADDON_ROOT / 'models' / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
