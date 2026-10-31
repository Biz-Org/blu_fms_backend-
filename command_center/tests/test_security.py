# -*- coding: utf-8 -*-
"""Phase 3 ACL, groups, and multi-company tests."""
import ast
import csv
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]

try:
    from odoo.exceptions import AccessError, UserError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    AccessError = UserError = Exception

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


class TestCcSecurityStatic(unittest.TestCase):
    def test_exactly_three_groups_and_hierarchy(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'cc_security.xml')
        groups = {
            rec.get('id'): rec
            for rec in tree.findall("./record[@model='res.groups']")
        }
        self.assertEqual(len(groups), 3)
        self.assertIn('group_cc_user', groups)
        self.assertIn('group_cc_manager', groups)
        self.assertIn('group_cc_admin', groups)
        user = groups['group_cc_user'].find("./field[@name='implied_ids']").get('eval')
        manager = groups['group_cc_manager'].find("./field[@name='implied_ids']").get('eval')
        admin = groups['group_cc_admin'].find("./field[@name='implied_ids']").get('eval')
        self.assertIn('base.group_user', user)
        self.assertIn('group_cc_user', manager)
        self.assertIn('group_cc_manager', admin)

    def test_acl_matrix_unchanged(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as handle:
            rows = {row['id']: row for row in csv.DictReader(handle)}
        self.assertEqual(
            [rows['access_cc_site_user'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '0', '0', '0'],
        )
        self.assertEqual(
            [rows['access_cc_site_manager'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '1', '1', '0'],
        )
        self.assertEqual(
            [rows['access_cc_site_admin'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '1', '1', '1'],
        )
        self.assertEqual(
            [rows['access_cc_alert_user'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '1', '1', '0'],
        )
        self.assertEqual(
            [rows['access_cc_incident_user'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '1', '1', '0'],
        )
        self.assertEqual(
            [rows['access_cc_escalation_history_manager'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '0', '0', '0'],
        )
        self.assertEqual(
            [rows['access_cc_investigation_note_user'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '0', '1', '0'],
        )
        self.assertEqual(
            [rows['access_cc_report_export_manager'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '0', '1', '0'],
        )
        self.assertEqual(
            [rows['access_cc_ui_api_admin'][k] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')],
            ['1', '0', '0', '0'],
        )

    def test_company_record_rules_unchanged(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'cc_record_rules.xml')
        rules = tree.findall("./record[@model='ir.rule']")
        self.assertEqual(len(rules), 8)
        domain = "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
        for rec in rules:
            self.assertEqual(rec.find("./field[@name='domain_force']").text, domain)
        xml = (ADDON_ROOT / 'security' / 'cc_record_rules.xml').read_text(encoding='utf-8')
        self.assertNotIn('model_cc_ui_api', xml)

    def test_manifest_depends_unchanged(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['depends'], ['base', 'web'])


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'cc_security')
class TestCcSecurityOdoo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.company_a = self.env.company
        self.company_b = self.env['res.company'].create({'name': 'CC Security Other'})
        self.group_user = self.env.ref('command_center.group_cc_user')
        self.group_manager = self.env.ref('command_center.group_cc_manager')
        self.group_admin = self.env.ref('command_center.group_cc_admin')
        self.user = self._make_user('cc_phase3_user', self.group_user, self.company_a)
        self.manager = self._make_user('cc_phase3_manager', self.group_manager, self.company_a)
        self.admin = self._make_user('cc_phase3_admin', self.group_admin, self.company_a)
        self.site_a = self.env['cc.site'].create({
            'code': 'SEC-A',
            'company_id': self.company_a.id,
        })
        self.site_b = self.env['cc.site'].create({
            'code': 'SEC-B',
            'company_id': self.company_b.id,
        })

    def _make_user(self, login, group, company):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, [group.id])],
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
        })

    def test_group_hierarchy_runtime(self):
        self.assertTrue(self.manager.has_group('command_center.group_cc_user'))
        self.assertTrue(self.admin.has_group('command_center.group_cc_manager'))
        self.assertTrue(self.admin.has_group('command_center.group_cc_user'))
        self.assertFalse(self.user.has_group('command_center.group_cc_manager'))

    def test_acl_user_cannot_create_site(self):
        with self.assertRaises(AccessError):
            self.env['cc.site'].with_user(self.user).create({'code': 'USER-SITE'})

    def test_acl_manager_can_create_site_not_unlink(self):
        site = self.env['cc.site'].with_user(self.manager).create({'code': 'MGR-SITE'})
        self.assertTrue(site.id)
        with self.assertRaises(AccessError):
            site.with_user(self.manager).unlink()

    def test_acl_admin_can_unlink_site(self):
        site = self.env['cc.site'].create({'code': 'ADM-SITE'})
        site.with_user(self.admin).unlink()
        self.assertFalse(site.exists())

    def test_note_append_only_and_admin_unlink(self):
        alert = self.env['cc.alert'].create({
            'alert_type': 'ops',
            'site_id': self.site_a.id,
        })
        note = self.env['cc.investigation.note'].with_user(self.user).create({
            'alert_id': alert.id,
            'body': 'Seen by operator',
        })
        with self.assertRaises(UserError):
            note.with_user(self.admin).write({'body': 'changed'})
        with self.assertRaises(AccessError):
            note.with_user(self.user).unlink()
        with self.assertRaises(AccessError):
            note.with_user(self.manager).unlink()
        note.with_user(self.admin).unlink()
        self.assertFalse(note.exists())

    def test_company_isolation(self):
        SiteUser = self.env['cc.site'].with_user(self.user)
        self.assertTrue(SiteUser.search([('id', '=', self.site_a.id)]))
        self.assertFalse(SiteUser.search([('id', '=', self.site_b.id)]))
        alert_b = self.env['cc.alert'].create({
            'alert_type': 'ops',
            'company_id': self.company_b.id,
            'site_id': self.site_b.id,
        })
        self.assertFalse(
            self.env['cc.alert'].with_user(self.user).search([('id', '=', alert_b.id)])
        )
