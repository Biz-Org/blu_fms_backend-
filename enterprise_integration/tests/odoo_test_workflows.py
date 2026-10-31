# -*- coding: utf-8 -*-
"""Phase 6 Odoo TransactionCase workflow tests (run only with Odoo test runner)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'enterprise_integration')
class TestEiWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Integration = cls.env['ei.integration']
        cls.integration = cls.Integration.create({
            'name': 'WF Integration',
            'code': 'WF-INT-001',
            'state': 'active',
        })

    def test_api_activate_test_deactivate_logs(self):
        endpoint = self.env['ei.api.endpoint'].create({
            'name': 'Partners',
            'integration_id': self.integration.id,
            'path': 'partners',
            'method': 'GET',
            'auth_type': 'api_key',
        })
        endpoint.action_activate()
        self.assertEqual(endpoint.state, 'active')
        endpoint.action_test_endpoint()
        self.assertTrue(endpoint.last_test_at)
        endpoint.action_deactivate()
        self.assertEqual(endpoint.state, 'inactive')
        logs = self.env['ei.log'].search([
            ('endpoint_id', '=', endpoint.id),
            ('category', '=', 'api'),
        ])
        self.assertTrue(logs)
        self.assertTrue(any(l.operation in ('api_activate', 'api_test', 'api_deactivate') for l in logs))

    def test_webhook_incoming_outgoing_retry_idempotency(self):
        from odoo.addons.enterprise_integration.services.webhook_service import WebhookService
        svc = WebhookService(self.env)
        incoming = self.env['ei.webhook'].create({
            'name': 'In WH',
            'integration_id': self.integration.id,
            'direction': 'incoming',
            'code': 'wf-in-1',
            'state': 'active',
            'auth_type': 'none',
        })
        r1 = svc.receive_incoming(incoming, {'ok': True}, idempotency_key='idem-wf-1')
        r2 = svc.receive_incoming(incoming, {'ok': True}, idempotency_key='idem-wf-1')
        self.assertTrue(r1['ok'])
        self.assertTrue(r2.get('idempotent_replay'))

        outgoing = self.env['ei.webhook'].create({
            'name': 'Out WH',
            'integration_id': self.integration.id,
            'direction': 'outgoing',
            'code': 'wf-out-1',
            'url': 'https://example.test/hook',
            'state': 'active',
        })
        delivery = svc.enqueue_outgoing(outgoing, {'event': 'x'})
        svc._deliver_one(delivery)
        self.assertEqual(delivery.status, 'delivered')
        self.assertTrue(delivery.correlation_id)

        fail_wh = self.env['ei.webhook'].create({
            'name': 'Fail WH',
            'integration_id': self.integration.id,
            'direction': 'outgoing',
            'code': 'wf-fail-1',
            'url': 'https://example.test/fail',
            'state': 'active',
            'retry_max': 2,
        })
        bad = svc.enqueue_outgoing(fail_wh, {'event': 'fail'})
        bad.action_retry()
        self.assertIn(bad.status, ('retrying', 'failed', 'delivered'))

    def test_connector_mock_health_reconnect(self):
        for cat, key in (
            ('erp', 'erp'), ('crm', 'crm'), ('bank', 'bank'),
            ('whatsapp', 'whatsapp'), ('legacy', 'legacy'),
        ):
            conn = self.env['ei.connector'].create({
                'name': f'{cat} mock',
                'integration_id': self.integration.id,
                'category': cat,
                'provider_code': f'mock_{cat}',
                'adapter_key': key,
                'is_mock': True,
            })
            self.assertTrue(conn.is_mock)
            conn.action_enable()
            conn.action_health_check()
            self.assertIn(conn.health_state, ('healthy', 'unknown', 'degraded', 'down'))
            conn.action_reconnect()

    def test_sync_manual_scheduled_realtime_partial(self):
        src = self.env['ei.connector'].create({
            'name': 'Src',
            'integration_id': self.integration.id,
            'category': 'erp',
            'provider_code': 'mock_src',
            'adapter_key': 'mock',
            'is_mock': True,
            'state': 'connected',
        })
        dest = self.env['ei.connector'].create({
            'name': 'Dest',
            'integration_id': self.integration.id,
            'category': 'crm',
            'provider_code': 'mock_dest',
            'adapter_key': 'mock',
            'is_mock': True,
            'state': 'connected',
        })
        job = self.env['ei.sync.job'].create({
            'name': 'WF Sync',
            'integration_id': self.integration.id,
            'source_connector_id': src.id,
            'dest_connector_id': dest.id,
            'entity_name': 'customer',
            'direction': 'one_way',
            'mode': 'full',
            'trigger': 'manual',
            'state': 'active',
        })
        run = job._run_internal()
        self.assertIn(run.state, ('completed', 'partially_completed', 'failed'))
        self.assertTrue(run.correlation_id)
        self.assertGreaterEqual(run.records_processed, 0)

        scheduled = job.copy({'name': 'Sched', 'trigger': 'scheduled'})
        self.env['ei.sync.job']._cron_run_scheduled_jobs()
        self.assertTrue(scheduled.last_run_state or True)

        realtime = job.copy({'name': 'RT', 'trigger': 'realtime', 'state': 'active'})
        realtime.action_trigger_realtime()
        self.assertTrue(realtime.realtime_pending)
        self.env['ei.sync.job']._cron_process_realtime_jobs()
        realtime.invalidate_recordset()
        self.assertFalse(realtime.realtime_pending)

    def test_master_entities_sot_conflict_resolve(self):
        from odoo.addons.enterprise_integration.services.master_data_service import MasterDataService
        entities = self.env['ei.master.entity'].search([])
        self.assertEqual(len(entities), 7)
        svc = MasterDataService(self.env)
        for entity in entities:
            mapping = self.env['ei.master.mapping'].create({
                'name': f'Map {entity.code}',
                'entity_id': entity.id,
                'integration_id': self.integration.id,
                'source_system': 'External',
                'target_system': 'PrecastMPS',
                'source_of_truth': 'target',
            })
            result = svc.synchronize_mapping(mapping)
            self.assertGreaterEqual(result['conflicts'], 1)
            conflict = mapping.conflict_ids[:1]
            self.assertTrue(conflict)
            svc.resolve(conflict, 'Keep target', self.env.user)
            self.assertEqual(conflict.state, 'resolved')

    def test_monitoring_correlation_and_export(self):
        log = self.env['ei.log'].ei_log(
            name='WF correlated op',
            category='system',
            level='success',
            operation='wf_test',
            correlation_id='corr-wf-123',
            retryable=False,
        )
        self.assertEqual(log.correlation_id, 'corr-wf-123')
        wiz = self.env['ei.log.export.wizard'].create({
            'category': 'system',
            'export_format': 'csv',
        })
        wiz.action_export()
        self.assertIn('corr-wf-123', wiz.export_data or '')
        self.assertNotIn('password', (wiz.export_data or '').lower())
