# -*- coding: utf-8 -*-
"""Phase 6 end-to-end workflow static tests (no Odoo runtime required).

Covers wiring, workflow orchestration, mock connectors, sync/master/monitoring
contracts, correlation IDs, retry policy, and six-menu regression.
"""
import ast
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
SERVICES = ADDON_ROOT / 'services'
CONNECTORS = SERVICES / 'connectors'
MODELS = ADDON_ROOT / 'models'
VIEWS = ADDON_ROOT / 'views'


def _ensure_pkg(name):
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = []
        sys.modules[name] = pkg
    return sys.modules[name]


def _load(modname, path, package=None):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    if package:
        mod.__package__ = package
    spec.loader.exec_module(mod)
    return mod


def _load_stack():
    root_pkg = _ensure_pkg('enterprise_integration')
    root_pkg.__path__ = [str(ADDON_ROOT)]
    svc_pkg = _ensure_pkg('enterprise_integration.services')
    svc_pkg.__path__ = [str(SERVICES)]
    conn_pkg = _ensure_pkg('enterprise_integration.services.connectors')
    conn_pkg.__path__ = [str(CONNECTORS)]

    exceptions = _load(
        'enterprise_integration.services.exceptions',
        SERVICES / 'exceptions.py',
        'enterprise_integration.services',
    )
    retry = _load(
        'enterprise_integration.services.retry_service',
        SERVICES / 'retry_service.py',
        'enterprise_integration.services',
    )
    transform = _load(
        'enterprise_integration.services.transform_service',
        SERVICES / 'transform_service.py',
        'enterprise_integration.services',
    )
    mapping = _load(
        'enterprise_integration.services.mapping_service',
        SERVICES / 'mapping_service.py',
        'enterprise_integration.services',
    )
    _load(
        'enterprise_integration.services.connectors.base',
        CONNECTORS / 'base.py',
        'enterprise_integration.services.connectors',
    )
    _load(
        'enterprise_integration.services.connectors.mock_adapter',
        CONNECTORS / 'mock_adapter.py',
        'enterprise_integration.services.connectors',
    )
    for name in ('erp', 'crm', 'bank', 'whatsapp', 'legacy'):
        _load(
            f'enterprise_integration.services.connectors.{name}_adapter',
            CONNECTORS / f'{name}_adapter.py',
            'enterprise_integration.services.connectors',
        )
    registry = _load(
        'enterprise_integration.services.connectors.registry',
        CONNECTORS / 'registry.py',
        'enterprise_integration.services.connectors',
    )
    return {
        'exceptions': exceptions,
        'retry': retry,
        'transform': transform,
        'mapping': mapping,
        'registry': registry,
    }


STACK = _load_stack()

EXPECTED_MENUS = {
    'Dashboard': 'action_ei_dashboard',
    'API & Webhook Management': 'action_ei_api_webhook',
    'Enterprise Connectors': 'action_ei_connectors',
    'Data Synchronization': 'action_ei_sync',
    'Master Data Integration': 'action_ei_master',
    'Integration Monitoring & Logs': 'action_ei_monitoring',
}

MASTER_ENTITIES = (
    'customer', 'supplier', 'product', 'employee',
    'account', 'site_location', 'department',
)

MOCK_SCENARIOS = (
    'success', 'auth_failure', 'timeout', 'connection_failure',
    'server_error', 'invalid_response', 'empty', 'duplicate_event',
)


class TestPhase6VersionAndMenus(unittest.TestCase):
    def test_version_bumped(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['version'], '18.0.1.4.7')

    def test_exactly_six_menus_unchanged(self):
        tree = ET.parse(VIEWS / 'ei_menus.xml')
        children = [m for m in tree.findall('.//menuitem') if m.get('parent') == 'menu_ei_root']
        self.assertEqual(len(children), 6)
        mapping = {
            (m.get('name') or '').replace('&amp;', '&'): m.get('action')
            for m in children
        }
        self.assertEqual(mapping, EXPECTED_MENUS)

    def test_no_new_primary_menus_anywhere(self):
        menus = []
        for path in VIEWS.glob('*.xml'):
            for m in ET.parse(path).findall('.//menuitem'):
                menus.append((path.name, m.get('id')))
        self.assertEqual(len(menus), 7)
        self.assertTrue(all(f == 'ei_menus.xml' for f, _ in menus))


class TestPhase6WorkflowWiring(unittest.TestCase):
    def test_workflow_service_exists(self):
        self.assertTrue((SERVICES / 'workflow_service.py').exists())
        text = (SERVICES / 'workflow_service.py').read_text(encoding='utf-8')
        for method in (
            'test_api_endpoint', 'test_connector', 'run_sync',
            'sync_master', 'enqueue_webhook', 'process_webhook_queue',
            'process_inbound', '_validate_inbound_payload',
        ):
            self.assertIn(f'def {method}', text)
        self.assertIn('pipeline_validate', text)
        self.assertIn('Validate', text)
        self.assertIn('Transform', text)

    def test_services_init_imports_workflow(self):
        text = (SERVICES / '__init__.py').read_text(encoding='utf-8')
        self.assertIn('workflow_service', text)

    def test_api_endpoint_workflow_methods(self):
        text = (MODELS / 'ei_api_endpoint.py').read_text(encoding='utf-8')
        for method in ('action_activate', 'action_deactivate', 'action_test_endpoint', '_validate_for_activation'):
            self.assertIn(f'def {method}', text)
        self.assertIn('WorkflowService', text)
        self.assertIn('ei.log', text)
        self.assertIn('pipeline_sync_job_id', text)

    def test_webhook_workflow_methods(self):
        text = (MODELS / 'ei_webhook.py').read_text(encoding='utf-8')
        for method in (
            'action_activate', 'action_deactivate', 'action_test_endpoint', 'action_enqueue_outgoing',
        ):
            self.assertIn(f'def {method}', text)
        self.assertIn('pipeline_sync_job_id', text)

    def test_webhook_delivery_retry_executes(self):
        text = (MODELS / 'ei_webhook_delivery.py').read_text(encoding='utf-8')
        self.assertIn('def action_retry', text)
        self.assertIn('_deliver_one', text)
        self.assertIn('Maximum retry attempts', text)

    def test_connector_workflow_methods(self):
        text = (MODELS / 'ei_connector.py').read_text(encoding='utf-8')
        for method in (
            'action_test_connection', 'action_health_check', 'action_enable',
            'action_disable', 'action_reconnect',
        ):
            self.assertIn(f'def {method}', text)
        self.assertIn('MOCK', text)
        self.assertIn('HealthService', text)

    def test_sync_job_realtime_and_cron(self):
        text = (MODELS / 'ei_sync_job.py').read_text(encoding='utf-8')
        self.assertIn('realtime_pending', text)
        self.assertIn('action_trigger_realtime', text)
        self.assertIn('_cron_run_scheduled_jobs', text)
        self.assertIn('_cron_process_realtime_jobs', text)
        self.assertIn('realtime_pending', text)

    def test_master_mapping_sync_and_sot(self):
        text = (MODELS / 'ei_master_mapping.py').read_text(encoding='utf-8')
        self.assertIn('action_sync_now', text)
        self.assertIn('_validate_sot_direction', text)
        self.assertIn('WorkflowService', text)

    def test_log_retry_and_export(self):
        text = (MODELS / 'ei_log.py').read_text(encoding='utf-8')
        self.assertIn('def action_retry', text)
        self.assertIn('def action_export_wizard', text)
        self.assertIn('correlation_id', text)
        self.assertIn('SECRET_TOKENS', text)


class TestPhase6UIBackendButtons(unittest.TestCase):
    def test_api_test_button_in_views(self):
        text = (VIEWS / 'ei_api_webhook_views.xml').read_text(encoding='utf-8')
        self.assertIn('action_test_endpoint', text)
        self.assertIn('action_enqueue_outgoing', text)

    def test_master_sync_now_button(self):
        text = (VIEWS / 'ei_master_data_views.xml').read_text(encoding='utf-8')
        self.assertIn('action_sync_now', text)

    def test_sync_run_stats_and_realtime(self):
        text = (VIEWS / 'ei_sync_views.xml').read_text(encoding='utf-8')
        self.assertIn('records_success', text)
        self.assertIn('action_trigger_realtime', text)
        self.assertIn('realtime_pending', text)

    def test_dashboard_live_orm_kpis(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'ei_app.js').read_text(encoding='utf-8')
        for model in (
            'ei.integration', 'ei.connector', 'ei.log', 'ei.sync.run',
        ):
            self.assertIn(f'"{model}"', js)
        for action in (
            'action_ei_api_webhook', 'action_ei_connectors', 'action_ei_sync',
            'action_ei_master', 'action_ei_monitoring',
        ):
            self.assertIn(action, js)
        self.assertIn('PIPELINE_STAGES', js)
        self.assertIn('PIPELINE_ROWS', js)
        self.assertIn('pipeline_validate', js)
        self.assertIn('External system', js)
        self.assertIn('API/Webhook', js)
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'ei_app.xml').read_text(encoding='utf-8')
        self.assertIn('ei-pipeline-flow', xml)
        self.assertIn('pipelineRows', xml)
        self.assertIn('pipelineStage(node.id).label', xml)

    def test_wizard_supports_api_test(self):
        wiz = (ADDON_ROOT / 'wizard' / 'ei_wizards.py').read_text(encoding='utf-8')
        self.assertIn("('api', 'API Endpoint')", wiz)
        self.assertIn('WorkflowService', wiz)
        self.assertIn('never logged', wiz.lower())
        self.assertIn('HealthService', wiz)


class TestPhase6MockConnectors(unittest.TestCase):
    def test_all_categories_are_mock(self):
        Registry = STACK['registry'].ConnectorRegistry
        for key in ('erp', 'crm', 'bank', 'whatsapp', 'legacy', 'mock'):
            adapter = Registry.get(key)(scenario='success')
            self.assertTrue(adapter.is_mock, key)
            self.assertIn('mock', adapter.test_connection()['message'].lower())

    def test_mock_scenarios_covered(self):
        Registry = STACK['registry'].ConnectorRegistry
        Auth = STACK['exceptions'].EiAuthenticationError
        Timeout = STACK['exceptions'].EiTimeoutError
        Conn = STACK['exceptions'].EiConnectionError
        Server = STACK['exceptions'].EiServerError
        Integ = STACK['exceptions'].EiIntegrationError
        Dup = STACK['exceptions'].EiDuplicateError

        ok = Registry.get('mock')(scenario='success')
        self.assertTrue(ok.authenticate()['ok'])

        with self.assertRaises(Auth):
            Registry.get('erp')(scenario='auth_failure').authenticate()
        with self.assertRaises(Timeout):
            Registry.get('crm')(scenario='timeout').test_connection()
        with self.assertRaises(Conn):
            Registry.get('bank')(scenario='connection_failure').authenticate()
        with self.assertRaises(Server):
            Registry.get('whatsapp')(scenario='server_error').authenticate()
        with self.assertRaises(Integ):
            Registry.get('legacy')(scenario='invalid_response').authenticate()

        empty = Registry.get('mock')(scenario='empty').fetch('customer')
        self.assertEqual(empty['records'], [])

        with self.assertRaises(Dup):
            Registry.get('mock')(scenario='duplicate_event').fetch('customer')

        # document expected scenario names used by UI settings_json
        for scenario in MOCK_SCENARIOS:
            self.assertTrue(scenario)


class TestPhase6SyncAndMasterContracts(unittest.TestCase):
    def test_sync_service_tracks_all_stats(self):
        text = (SERVICES / 'sync_service.py').read_text(encoding='utf-8')
        for token in (
            'records_success', 'records_failed', 'records_conflict',
            'records_duplicate', 'partially_completed', 'correlation_id',
        ):
            self.assertIn(token, text)

    def test_sync_record_has_correlation(self):
        text = (MODELS / 'ei_sync_record.py').read_text(encoding='utf-8')
        self.assertIn('correlation_id', text)

    def test_master_sot_prevents_overwrite(self):
        text = (SERVICES / 'master_data_service.py').read_text(encoding='utf-8')
        self.assertIn("sot in ('target', 'precastmps')", text)
        self.assertIn('_from_sot', text)
        self.assertIn('detect_conflict', text)
        for code in MASTER_ENTITIES:
            # entity codes referenced via ENTITY_CODES
            self.assertIn(f"'{code}'", text)

    def test_master_entity_data_seed(self):
        tree = ET.parse(ADDON_ROOT / 'data' / 'ei_master_entity_data.xml')
        codes = {
            rec.find("./field[@name='code']").text
            for rec in tree.findall(".//record[@model='ei.master.entity']")
        }
        self.assertEqual(codes, set(MASTER_ENTITIES))

    def test_master_demo_mappings_seed(self):
        tree = ET.parse(ADDON_ROOT / 'data' / 'ei_master_demo_data.xml')
        maps = tree.findall(".//record[@model='ei.master.mapping']")
        conflicts = tree.findall(".//record[@model='ei.master.conflict']")
        self.assertGreaterEqual(len(maps), 3)
        names = {r.find("./field[@name='name']").text for r in maps}
        self.assertIn('B2B Customers', names)
        self.assertIn('Retail Customers', names)
        self.assertGreaterEqual(len(conflicts), 1)
        manifest = (ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8')
        self.assertIn('ei_master_demo_data.xml', manifest)

    def test_mapping_and_transform_pipeline(self):
        M = STACK['mapping'].MappingService()
        T = STACK['transform'].TransformService()
        mapped = M.apply_mappings(
            {'name': ' Acme ', 'qty': '3'},
            [
                {
                    'source_field': 'name', 'target_field': 'full_name',
                    'transform_type': 'string_normalize', 'active': True,
                },
                {
                    'source_field': 'qty', 'target_field': 'quantity',
                    'transform_type': 'to_int', 'active': True,
                },
            ],
        )
        self.assertEqual(mapped['full_name'], 'acme')
        self.assertEqual(mapped['quantity'], 3)
        self.assertEqual(T.apply('yes', 'to_bool'), True)


class TestPhase6RetryAndErrors(unittest.TestCase):
    def test_retry_respects_max_and_backoff(self):
        RetryService = STACK['retry'].RetryService
        svc = RetryService(max_attempts=3, backoff_seconds=10, backoff_factor=2)
        p1 = svc.plan(1, retryable=True)
        self.assertEqual(p1['status'], 'retrying')
        self.assertEqual(p1['delay_seconds'], 10)
        p2 = svc.plan(2, retryable=True)
        self.assertEqual(p2['delay_seconds'], 20)
        p3 = svc.plan(3, retryable=True)
        self.assertEqual(p3['status'], 'failed')
        self.assertIsNone(p3['next_retry_at'])

    def test_exception_classes_for_error_workflow(self):
        exc = STACK['exceptions']
        for name in (
            'EiAuthenticationError', 'EiConnectionError', 'EiTimeoutError',
            'EiServerError', 'EiValidationError', 'EiDuplicateError',
            'EiIntegrationError',
        ):
            self.assertTrue(hasattr(exc, name))


class TestPhase6MonitoringAndCredentials(unittest.TestCase):
    def test_export_wizard_safe_fields_only(self):
        wiz = (ADDON_ROOT / 'wizard' / 'ei_wizards.py').read_text(encoding='utf-8')
        self.assertIn('correlation_id', wiz)
        # must not dump request_summary / response_summary / secrets into export
        export_block = wiz[wiz.find('class EiLogExportWizard'):]
        self.assertNotIn("'request_summary'", export_block)
        self.assertNotIn("'response_summary'", export_block)
        self.assertNotIn('password', export_block.lower().split('action_export')[1][:800])

    def test_credential_models_mask_secrets(self):
        api = (MODELS / 'ei_api_credential.py').read_text(encoding='utf-8')
        self.assertIn('key_hash', api)
        self.assertIn('secret_display', api)
        self.assertIn('_check_credential_access', api)
        conn = (MODELS / 'ei_connector_credential.py').read_text(encoding='utf-8')
        self.assertIn('secret_display', conn)

    def test_monitoring_view_has_retry_export(self):
        text = (VIEWS / 'ei_monitoring_views.xml').read_text(encoding='utf-8')
        self.assertIn('action_retry', text)
        self.assertIn('action_export_wizard', text)
        self.assertIn('correlation_id', text)


class TestPhase6ControllersStillPresent(unittest.TestCase):
    def test_api_and_webhook_controllers(self):
        api = (ADDON_ROOT / 'controllers' / 'api_controller.py').read_text(encoding='utf-8')
        wh = (ADDON_ROOT / 'controllers' / 'webhook_controller.py').read_text(encoding='utf-8')
        self.assertIn('/ei/api/v1', api)
        self.assertIn('/ei/webhook', wh)
        self.assertIn('ApiService', api)
        self.assertIn('WebhookService', wh)


class TestPhase6PythonCompiles(unittest.TestCase):
    def test_all_python_compiles(self):
        for py in ADDON_ROOT.rglob('*.py'):
            compile(py.read_text(encoding='utf-8'), str(py), 'exec')

    def test_all_xml_parses(self):
        for xml_path in ADDON_ROOT.rglob('*.xml'):
            ET.parse(xml_path)


if __name__ == '__main__':
    unittest.main()
