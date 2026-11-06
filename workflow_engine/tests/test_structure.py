# -*- coding: utf-8 -*-
"""Structure / installation tests for the Workflow Engine addon."""
import ast
import csv
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]


class TestAddonStructure(unittest.TestCase):
    def test_manifest_exists_and_version(self):
        manifest_path = ADDON_ROOT / '__manifest__.py'
        self.assertTrue(manifest_path.exists())
        data = ast.literal_eval(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(data['name'], 'Workflow Engine')
        self.assertEqual(data['version'], '18.0.1.7.0')
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertEqual(data['depends'], ['base', 'web', 'mail'])
        self.assertNotIn('enterprise_integration', data['depends'])
        self.assertNotIn('queue_job', data['depends'])

    def test_manifest_loads_escalation_cron(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertIn('data/we_cron_data.xml', data['data'])

    def test_manifest_does_not_load_extra_crons_only_escalation_file(self):
        cron_xml = (ADDON_ROOT / 'data' / 'we_cron_data.xml').read_text(encoding='utf-8')
        self.assertIn('ir_cron_we_process_escalations', cron_xml)
        self.assertEqual(cron_xml.count('model="ir.cron"'), 1)

    def test_exactly_eight_menuitems(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'we_menus.xml')
        menuitems = tree.findall('.//menuitem')
        self.assertEqual(len(menuitems), 8)
        root = [m for m in menuitems if m.get('id') == 'menu_we_root']
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].get('name'), 'Workflow Engine')
        children = [m for m in menuitems if m.get('parent') == 'menu_we_root']
        self.assertEqual(len(children), 7)

    def test_all_xml_parses(self):
        for xml_path in ADDON_ROOT.rglob('*.xml'):
            ET.parse(xml_path)

    def test_access_csv_valid(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as handle:
            reader = csv.reader(handle)
            header = next(reader)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        self.assertEqual(
            header,
            ['id', 'name', 'model_id:id', 'group_id:id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
        )
        self.assertGreaterEqual(len(rows), 18)
        groups = {row[3] for row in rows}
        self.assertEqual(groups, {'group_we_user', 'group_we_manager', 'group_we_admin'})
        self.assertTrue(all(len(row) == 8 for row in rows))

    def test_security_groups(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'we_security.xml')
        groups = {
            rec.get('id'): rec.find("./field[@name='name']").text
            for rec in tree.findall("./record[@model='res.groups']")
        }
        self.assertEqual(groups['group_we_user'], 'Workflow Engine User')
        self.assertEqual(groups['group_we_manager'], 'Workflow Engine Manager')
        self.assertEqual(groups['group_we_admin'], 'Workflow Engine Administrator')
        self.assertEqual(len(groups), 3)

    def test_python_files_compile(self):
        for py_path in ADDON_ROOT.rglob('*.py'):
            compile(py_path.read_text(encoding='utf-8'), str(py_path), 'exec')

    def test_domain_models_imported(self):
        models_init = (ADDON_ROOT / 'models' / '__init__.py').read_text(encoding='utf-8')
        for name in (
            'workflow_definition', 'workflow_version', 'workflow_node', 'workflow_edge',
            'workflow_trigger', 'workflow_template', 'approval_hierarchy', 'approval_level',
            'approver', 'conditional_rule', 'workflow_execution', 'execution_step',
            'workflow_task', 'approval_request', 'escalation_rule', 'escalation_event',
            'notification_log', 'audit_event', 'we_ui_api',
        ):
            self.assertIn('from . import %s' % name, models_init)

    def test_no_cron_in_manifest_data(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        # Only the escalation cron data file is allowed.
        cron_files = [item for item in data['data'] if 'cron' in item]
        self.assertEqual(cron_files, ['data/we_cron_data.xml'])
        self.assertNotIn('enterprise_integration', data['depends'])


if __name__ == '__main__':
    unittest.main()
