# -*- coding:    utf-8 -*-
"""Odoo TransactionCase tests for Phase 4 services.

Requires Odoo 18:
  odoo-bin -d <db> -u enterprise_integration --test-enable --stop-after-init
"""
import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'ei_services')
class TestEiServices(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration = cls.env['ei.integration'].create({
            'name': 'Svc Integration',
            'code': 'SVC-INT-001',
            'state': 'active',
        })
        cls.erp = cls.env['ei.connector'].create({
            'name': 'Mock ERP',
            'integration_id': cls.integration.id,
            'category': 'erp',
            'provider_code': 'mock_erp',
            'adapter_key': 'erp',
            'is_mock': True,
            'settings_json': json.dumps({'mock_scenario': 'success'}),
        })
        cls.crm = cls.env['ei.connector'].create({
            'name': 'Mock CRM',
            'integration_id': cls.integration.id,
            'category': 'crm',
            'provider_code': 'mock_crm',
            'adapter_key': 'crm',
            'is_mock': True,
        })

    def test_api_auth_and_idempotency(self):
        from odoo.addons.enterprise_integration.services.api_service import ApiService
        endpoint = self.env['ei.api.endpoint'].create({
            'name': 'Items',
            'integration_id': self.integration.id,
            'path': 'items',
            'method': 'POST',
            'state': 'active',
            'auth_type': 'api_key',
        })
        cred = self.env['ei.api.credential'].create({
            'name': 'Svc Key',
            'endpoint_id': endpoint.id,
            'plaintext_key': 'phase4-api-key-value-0001',
        })
        svc = ApiService(self.env)
        bad = svc.handle_request(endpoint, 'POST', payload={}, api_key='wrong')
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['error'], 'unauthorized')

        ok = svc.handle_request(
            endpoint, 'POST', payload={'a': 1},
            api_key='phase4-api-key-value-0001',
            idempotency_key='idem-1',
        )
        self.assertTrue(ok['ok'])
        replay = svc.handle_request(
            endpoint, 'POST', payload={'a': 1},
            api_key='phase4-api-key-value-0001',
            idempotency_key='idem-1',
        )
        self.assertTrue(replay.get('idempotent_replay'))
        self.assertTrue(cred.key_hash)

    def test_webhook_incoming_idempotency_and_outgoing_retry(self):
        from odoo.addons.enterprise_integration.services.webhook_service import WebhookService
        wh_in = self.env['ei.webhook'].create({
            'name': 'In',
            'integration_id': self.integration.id,
            'code': 'svc-in-1',
            'direction': 'incoming',
            'state': 'active',
        })
        svc = WebhookService(self.env)
        first = svc.receive_incoming(wh_in, {'event': 'x'}, idempotency_key='wh-1')
        second = svc.receive_incoming(wh_in, {'event': 'x'}, idempotency_key='wh-1')
        self.assertTrue(first['ok'])
        self.assertTrue(second.get('idempotent_replay'))

        wh_out = self.env['ei.webhook'].create({
            'name': 'Out Fail',
            'integration_id': self.integration.id,
            'code': 'svc-out-fail',
            'direction': 'outgoing',
            'url': 'https://example.invalid/fail',
            'state': 'active',
            'retry_max': 2,
            'retry_backoff': 1,
        })
        delivery = svc.enqueue_outgoing(wh_out, {'hello': 'world'}, event_type='demo')
        svc._deliver_one(delivery)
        self.assertEqual(delivery.status, 'retrying')
        svc._deliver_one(delivery)
        self.assertEqual(delivery.status, 'failed')

    def test_connector_health_and_categories(self):
        from odoo.addons.enterprise_integration.services.health_service import HealthService
        from odoo.addons.enterprise_integration.services.connectors.registry import ConnectorRegistry
        for key in ('erp', 'crm', 'bank', 'whatsapp', 'legacy'):
            self.assertIn(key, ConnectorRegistry.keys())
        result = HealthService(self.env).check_connector(self.erp)
        self.assertTrue(result['ok'])
        self.assertEqual(self.erp.health_state, 'healthy')

    def test_sync_pipeline_mapping_duplicate_conflict(self):
        job = self.env['ei.sync.job'].create({
            'name': 'Svc Sync',
            'integration_id': self.integration.id,
            'entity_name': 'customer',
            'source_connector_id': self.erp.id,
            'dest_connector_id': self.crm.id,
            'direction': 'one_way',
            'mode': 'full',
            'trigger': 'manual',
            'state': 'active',
            'duplicate_policy': 'skip',
            'conflict_policy': 'manual',
        })
        self.env['ei.connector.mapping'].create({
            'sync_job_id': job.id,
            'source_field': 'name',
            'target_field': 'full_name',
            'transform_type': 'string_normalize',
        })
        run = job._run_internal()
        self.assertIn(run.state, ('completed', 'partially_completed'))
        self.assertTrue(run.record_ids)
        self.assertTrue(self.env['ei.log'].search([
            ('category', '=', 'sync'),
            ('correlation_id', '=', run.correlation_id),
        ]))

    def test_master_data_all_entities_and_conflict_resolve(self):
        from odoo.addons.enterprise_integration.services.master_data_service import MasterDataService
        svc = MasterDataService(self.env)
        for code in MasterDataService.ENTITY_CODES:
            entity = self.env['ei.master.entity'].search([('code', '=', code)], limit=1)
            self.assertTrue(entity, code)
            mapping = self.env['ei.master.mapping'].create({
                'name': f'{code} map',
                'entity_id': entity.id,
                'integration_id': self.integration.id,
                'source_system': 'EXT',
                'target_system': 'PrecastMPS',
                'source_of_truth': 'source',
                'source_connector_id': self.erp.id,
                'target_connector_id': self.crm.id,
            })
            result = svc.synchronize_mapping(mapping)
            self.assertIn(result['state'], ('synced', 'updated', 'conflict'))

        # conflict + resolve
        entity = self.env['ei.master.entity'].search([('code', '=', 'customer')], limit=1)
        mapping = self.env['ei.master.mapping'].create({
            'name': 'Conflict Map',
            'entity_id': entity.id,
            'source_system': 'A',
            'target_system': 'B',
            'source_of_truth': 'manual',
        })
        conflict = svc.detect_conflict(mapping, '{"a":1}', '{"a":2}')
        svc.resolve(conflict, 'keep source', self.env.user)
        self.assertEqual(conflict.state, 'resolved')
        self.assertEqual(mapping.state, 'synced')

    def test_log_redaction(self):
        log = self.env['ei.log'].ei_log(
            name='safe',
            category='api',
            level='failed',
            request_summary='Authorization: Bearer super-secret',
            error_message='client_secret=xyz',
        )
        self.assertIn('scrubbed', log.request_summary)
        self.assertIn('scrubbed', log.error_message)
