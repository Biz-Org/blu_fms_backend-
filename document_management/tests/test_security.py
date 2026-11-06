# -*- coding: utf-8 -*-
"""Phase 2 security foundation tests."""
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
@tagged('post_install', '-at_install', 'dm_security')
class TestDmSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def test_groups_exist(self):
        self.assertTrue(self.env.ref('document_management.group_dm_user'))
        self.assertTrue(self.env.ref('document_management.group_dm_manager'))
        self.assertTrue(self.env.ref('document_management.group_dm_admin'))

    def test_company_isolation_field(self):
        document = self.env['document.management.document'].create({'name': 'Sec Doc'})
        self.assertEqual(document.company_id, self.env.company)

    def test_attachment_not_public_by_default(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'dm-foundation.txt',
            'datas': 'dGVzdA==',
            'res_model': 'document.management.document',
            'public': False,
        })
        self.assertFalse(attachment.public)
        self.assertNotIn('/web/content/%s' % attachment.id, attachment.name or '')
