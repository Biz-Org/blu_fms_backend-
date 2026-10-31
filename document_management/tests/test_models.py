# -*- coding: utf-8 -*-
"""Phase 2 model registration tests."""
import unittest

try:
    from odoo.exceptions import UserError, ValidationError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    UserError = ValidationError = Exception

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


EXPECTED_MODELS = [
    'document.management.mixin',
    'document.management.document',
    'document.management.version',
    'document.management.category',
    'document.management.document.type',
    'document.management.folder',
    'document.management.tag',
    'document.management.favorite',
    'document.management.comment',
    'document.management.access.group',
    'document.management.access.rule',
    'document.management.share.link',
    'document.management.approval.request',
    'document.management.approval.step',
    'document.management.audit.event',
    'document.management.notification',
    'document.management.ai.provider',
    'document.management.ui.api',
]


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'dm_models')
class TestDmModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def test_models_registered(self):
        for name in EXPECTED_MODELS:
            self.assertIn(name, self.env.registry)
        self.assertTrue(self.env['document.management.mixin']._abstract)
        self.assertTrue(self.env['document.management.ai.provider']._abstract)
        self.assertTrue(self.env['document.management.ui.api']._transient)

    def test_company_fields(self):
        Document = self.env['document.management.document']
        self.assertIn('company_id', Document._fields)
        self.assertTrue(Document._check_company_auto)
        rec = Document.create({'name': 'Foundation Doc'})
        self.assertEqual(rec.company_id, self.env.company)
        self.assertTrue(rec.code.startswith('DM'))
        self.assertEqual(rec.state, 'draft')
        self.assertEqual(rec.access_level, 'role_restricted')
        self.assertTrue(rec.active)
        self.assertEqual(rec.expiry_status, 'none')

    def test_type_requires_approval_copied(self):
        doc_type = self.env['document.management.document.type'].create({
            'name': 'Skip Type',
            'requires_approval': False,
        })
        document = self.env['document.management.document'].create({
            'name': 'Skip Doc',
            'type_id': doc_type.id,
        })
        self.assertFalse(document.requires_approval)

    def test_ai_provider_unconfigured(self):
        provider = self.env['document.management.ai.provider']
        self.assertFalse(provider.is_configured())
        with self.assertRaises(UserError):
            provider.search('query', [], {})

    def test_no_catalog_seed(self):
        screenshot_names = ['Policies', 'Contracts', 'Vendors', 'Municipal']
        self.assertFalse(self.env['document.management.category'].search([
            ('name', 'in', screenshot_names),
        ]))
        self.assertFalse(self.env['document.management.document.type'].search([
            ('name', 'in', ['Policy', 'Contract']),
        ]))
