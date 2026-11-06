# -*- coding: utf-8 -*-
"""Phase 2 service contract tests."""
import unittest

try:
    from odoo.exceptions import UserError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    from odoo.addons.document_management.services.file_service import DocumentFileService
    from odoo.addons.document_management.services.document_service import DocumentService
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    UserError = Exception
    DocumentFileService = DocumentService = None

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
@tagged('post_install', '-at_install', 'dm_services')
class TestDmServices(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def test_file_validation_rejects_bad_type_and_size(self):
        service = DocumentFileService(self.env)
        bad_type = service.validate_upload('secret.exe', 'application/octet-stream', 100)
        self.assertFalse(bad_type['ok'])
        too_big = service.validate_upload('file.pdf', 'application/pdf', 51 * 1024 * 1024)
        self.assertFalse(too_big['ok'])
        ok = service.validate_upload('file.pdf', 'application/pdf', 1024)
        self.assertTrue(ok['ok'])

    def test_dashboard_contract(self):
        data = DocumentService(self.env).get_dashboard_data()
        self.assertIn('documents_total', data['kpis'])
        self.assertIsInstance(data['kpis']['documents_total'], int)
        self.assertEqual(data['distribution'], [])
        self.assertIn('recent', data)

    def test_ai_search_unconfigured(self):
        payload = self.env['document.management.ui.api'].ai_search('query', {})
        self.assertFalse(payload['configured'])
        self.assertFalse(payload['available'])
        self.assertEqual(payload['message'], 'AI Search is not configured')
        self.assertEqual(payload['citations'], [])
        self.assertEqual(payload['sources'], [])
        self.assertEqual(payload['related'], [])
        self.assertFalse(payload['answer'])

    def test_write_methods_create_documents(self):
        api = self.env['document.management.ui.api']
        with self.assertRaises(UserError):
            api.create_draft({}, None)
        draft = api.create_draft({'name': 'Service Draft'}, None)
        self.assertEqual(draft['state'], 'draft')
        self.assertFalse(draft.get('duplicate'))
