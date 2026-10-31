# -*- coding: utf-8 -*-
"""Odoo TransactionCase tests for core domain models.

Requires Odoo 18 runtime:
  odoo-bin -d <db> -i enterprise_integration --test-enable --stop-after-init
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'ei_models')
class TestEiModels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Integration = cls.env['ei.integration']
        cls.Endpoint = cls.env['ei.api.endpoint']
        cls.Credential = cls.env['ei.api.credential']
        cls.Webhook = cls.env['ei.webhook']
        cls.Connector = cls.env['ei.connector']
        cls.SyncJob = cls.env['ei.sync.job']
        cls.MasterEntity = cls.env['ei.master.entity']
        cls.MasterMapping = cls.env['ei.master.mapping']
        cls.Log = cls.env['ei.log']

        cls.integration = cls.Integration.create({
            'name': 'Test Integration',
            'code': 'TEST-INT-001',
            'integration_type': 'hybrid',
            'provider_system': 'Mock System',
            'environment': 'development',
            'auth_method': 'api_key',
            'state': 'draft',
        })

    def test_integration_create_and_activate(self):
        self.assertEqual(self.integration.state, 'draft')
        self.integration.action_activate()
        self.assertEqual(self.integration.state, 'active')
        self.assertTrue(self.integration.active)

    def test_integration_code_unique(self):
        with self.assertRaises(Exception):
            self.Integration.create({
                'name': 'Dup',
                'code': 'TEST-INT-001',
            })

    def test_integration_base_url_constraint(self):
        with self.assertRaises(ValidationError):
            self.integration.write({'base_url': 'not-a-url'})

    def test_api_endpoint_path_constraint(self):
        with self.assertRaises(ValidationError):
            self.Endpoint.create({
                'name': 'Bad',
                'integration_id': self.integration.id,
                'path': '/leading-slash',
                'method': 'GET',
            })

    def test_api_endpoint_and_credential(self):
        endpoint = self.Endpoint.create({
            'name': 'Partners',
            'integration_id': self.integration.id,
            'path': 'partners',
            'method': 'GET',
            'state': 'active',
        })
        cred = self.Credential.create({
            'name': 'Key 1',
            'endpoint_id': endpoint.id,
            'plaintext_key': 'super-secret-key-value-123456',
        })
        self.assertTrue(cred.key_hash)
        self.assertNotEqual(cred.key_hash, 'super-secret-key-value-123456')
        self.assertTrue(cred.verify_key('super-secret-key-value-123456'))

    def test_webhook_outgoing_requires_url_when_active(self):
        wh = self.Webhook.create({
            'name': 'Out',
            'integration_id': self.integration.id,
            'code': 'wh-out-1',
            'direction': 'outgoing',
            'state': 'inactive',
        })
        with self.assertRaises(ValidationError):
            wh.write({'state': 'active'})

    def test_connector_categories_and_mock(self):
        for category in ('erp', 'crm', 'bank', 'whatsapp', 'legacy'):
            conn = self.Connector.create({
                'name': f'{category} mock',
                'integration_id': self.integration.id,
                'category': category,
                'provider_code': f'mock_{category}',
                'adapter_key': 'mock',
                'is_mock': True,
            })
            self.assertEqual(conn.category, category)
            conn.action_reconnect()
            self.assertEqual(conn.state, 'connected')

    def test_sync_job_requires_source_and_dest(self):
        with self.assertRaises(ValidationError):
            self.SyncJob.create({
                'name': 'Bad Job',
                'integration_id': self.integration.id,
                'entity_name': 'customer',
            })

    def test_sync_job_run_creates_run_and_log(self):
        src = self.Connector.create({
            'name': 'Src',
            'integration_id': self.integration.id,
            'category': 'erp',
            'provider_code': 'mock_src',
            'adapter_key': 'mock',
            'is_mock': True,
        })
        dst = self.Connector.create({
            'name': 'Dst',
            'integration_id': self.integration.id,
            'category': 'crm',
            'provider_code': 'mock_dst',
            'adapter_key': 'mock',
            'is_mock': True,
        })
        job = self.SyncJob.create({
            'name': 'Customers Sync',
            'integration_id': self.integration.id,
            'entity_name': 'customer',
            'source_connector_id': src.id,
            'dest_connector_id': dst.id,
            'state': 'active',
        })
        run = job._run_internal()
        self.assertIn(run.state, ('completed', 'partially_completed', 'failed'))
        self.assertTrue(run.record_ids)

    def test_master_mapping_systems_differ(self):
        entity = self.MasterEntity.search([('code', '=', 'customer')], limit=1)
        self.assertTrue(entity)
        with self.assertRaises(ValidationError):
            self.MasterMapping.create({
                'name': 'Bad Map',
                'entity_id': entity.id,
                'source_system': 'A',
                'target_system': 'A',
            })

    def test_log_scrubs_secrets_on_create(self):
        log = self.Log.ei_log(
            name='ok',
            category='api',
            level='success',
            request_summary='password=should-not-store',
            integration_id=self.integration.id,
        )
        self.assertIn('scrubbed', log.request_summary)
