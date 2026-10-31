# -*- coding: utf-8 -*-
"""Phase 2 menu/action/RPC integration tests."""
import json
import unittest

try:
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'dm_ui')
class TestDmUiIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def test_session_and_empty_rpc(self):
        api = self.env['document.management.ui.api']
        session = api.get_session_context()
        self.assertIn('uid', session)
        self.assertIn('is_user', session)
        dashboard = api.get_dashboard_data()
        self.assertIn('documents_total', dashboard['kpis'])
        self.assertIn('recent', dashboard)
        blob = json.dumps(dashboard, default=str).lower()
        self.assertNotIn('sample', blob)
        self.assertNotIn('placeholder', blob)
        repository = api.get_repository_data()
        self.assertIn('items', repository)
        approval = api.get_approval_board()
        self.assertIn('rows', approval)
        audit = api.get_audit_data()
        self.assertIn('rows', audit)

    def test_actions_and_menus_loaded(self):
        self.assertTrue(self.env.ref('document_management.action_dm_dashboard'))
        self.assertTrue(self.env.ref('document_management.menu_dm_root'))
        actions = self.env['ir.actions.client'].search([
            ('tag', '=', 'document_management_app'),
        ])
        self.assertEqual(len(actions), 8)
        menus = self.env['ir.ui.menu'].search([
            ('name', 'in', [
                'Document Management Dashboard',
                'Document Repository',
                'Document Upload',
                'Document Details',
                'Access Control & Sharing',
                'Approval & Expiry',
                'Document Search',
                'Activity & Audit',
            ]),
        ])
        self.assertGreaterEqual(len(menus), 8)
