# -*- coding: utf-8 -*-
"""Phase 4 service-layer unit tests (no Odoo runtime required)."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
SERVICES = ADDON_ROOT / 'services'
CONNECTORS = SERVICES / 'connectors'


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


def _load_services_stack():
    """Load services.* without importing enterprise_integration/__init__.py (needs odoo)."""
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
    # connectors
    base = _load(
        'enterprise_integration.services.connectors.base',
        CONNECTORS / 'base.py',
        'enterprise_integration.services.connectors',
    )
    mock = _load(
        'enterprise_integration.services.connectors.mock_adapter',
        CONNECTORS / 'mock_adapter.py',
        'enterprise_integration.services.connectors',
    )
    erp = _load(
        'enterprise_integration.services.connectors.erp_adapter',
        CONNECTORS / 'erp_adapter.py',
        'enterprise_integration.services.connectors',
    )
    crm = _load(
        'enterprise_integration.services.connectors.crm_adapter',
        CONNECTORS / 'crm_adapter.py',
        'enterprise_integration.services.connectors',
    )
    bank = _load(
        'enterprise_integration.services.connectors.bank_adapter',
        CONNECTORS / 'bank_adapter.py',
        'enterprise_integration.services.connectors',
    )
    whatsapp = _load(
        'enterprise_integration.services.connectors.whatsapp_adapter',
        CONNECTORS / 'whatsapp_adapter.py',
        'enterprise_integration.services.connectors',
    )
    legacy = _load(
        'enterprise_integration.services.connectors.legacy_adapter',
        CONNECTORS / 'legacy_adapter.py',
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
        'base': base,
        'mock': mock,
        'erp': erp,
        'crm': crm,
        'bank': bank,
        'whatsapp': whatsapp,
        'legacy': legacy,
        'registry': registry,
    }


STACK = _load_services_stack()


class TestRetryService(unittest.TestCase):
    def test_retry_then_fail(self):
        RetryService = STACK['retry'].RetryService
        svc = RetryService(max_attempts=3, backoff_seconds=10, backoff_factor=2)
        p1 = svc.plan(1, retryable=True)
        self.assertEqual(p1['status'], 'retrying')
        self.assertEqual(p1['delay_seconds'], 10)
        p3 = svc.plan(3, retryable=True)
        self.assertEqual(p3['status'], 'failed')

    def test_non_retryable(self):
        RetryService = STACK['retry'].RetryService
        plan = RetryService(max_attempts=5).plan(1, retryable=False)
        self.assertEqual(plan['status'], 'failed')


class TestTransformAndMapping(unittest.TestCase):
    def test_transforms(self):
        T = STACK['transform'].TransformService()
        self.assertEqual(T.apply(' AbC ', 'string_normalize'), 'abc')
        self.assertEqual(T.apply('2', 'to_int'), 2)
        self.assertEqual(T.apply('yes', 'to_bool'), True)
        self.assertEqual(T.apply('a', 'map', 'a:alpha,b:beta'), 'alpha')
        self.assertEqual(T.apply('x', 'format', 'ID-{value}'), 'ID-x')
        self.assertEqual(T.apply(None, 'default', 'N/A'), 'N/A')

    def test_rejects_unsafe_expression(self):
        T = STACK['transform'].TransformService()
        with self.assertRaises(ValueError):
            T.apply('1', 'expression', '__import__("os").system("x")')

    def test_mapping_service(self):
        M = STACK['mapping'].MappingService()
        lines = [
            {'source_field': 'name', 'target_field': 'full_name', 'transform_type': 'string_normalize', 'active': True},
            {'source_field': 'code', 'target_field': 'sku', 'transform_type': 'none', 'active': True},
        ]
        out = M.apply_mappings({'name': ' Acme ', 'code': 'C1'}, lines)
        self.assertEqual(out['full_name'], 'acme')
        self.assertEqual(out['sku'], 'C1')
        self.assertEqual(M.duplicate_key(out, ['sku', 'full_name']), 'C1|acme')


class TestConnectors(unittest.TestCase):
    def test_registry_keys(self):
        keys = set(STACK['registry'].ConnectorRegistry.keys())
        self.assertTrue({'mock', 'erp', 'crm', 'bank', 'whatsapp', 'legacy'} <= keys)

    def test_each_category_success(self):
        Registry = STACK['registry'].ConnectorRegistry
        for key in ('erp', 'crm', 'bank', 'whatsapp', 'legacy', 'mock'):
            adapter = Registry.get(key)(scenario='success')
            self.assertTrue(adapter.is_mock)
            self.assertTrue(adapter.authenticate()['ok'])
            self.assertTrue(adapter.test_connection()['ok'])
            self.assertTrue(adapter.health_check()['ok'])
            fetched = adapter.fetch('customer')
            self.assertTrue(fetched['ok'])
            self.assertTrue(adapter.push('customer', {'id': '1'})['ok'])

    def test_auth_failure_scenario(self):
        AuthErr = STACK['exceptions'].EiAuthenticationError
        adapter = STACK['registry'].ConnectorRegistry.get('erp')(scenario='auth_failure')
        with self.assertRaises(AuthErr):
            adapter.authenticate()

    def test_timeout_scenario(self):
        Timeout = STACK['exceptions'].EiTimeoutError
        adapter = STACK['mock'].MockAdapter(scenario='timeout')
        with self.assertRaises(Timeout):
            adapter.test_connection()

    def test_whatsapp_message_abstraction(self):
        wa = STACK['whatsapp'].WhatsAppAdapter(scenario='success')
        result = wa.send_message('911', 'hello')
        self.assertTrue(result['ok'])
        self.assertEqual(result['delivery_status'], 'accepted')
        self.assertEqual(result['mode'], 'mock')

    def test_legacy_protocol_extension_point(self):
        class FakeConn:
            settings_json = '{"protocol": "sftp", "mock_scenario": "success"}'

        adapter = STACK['legacy'].LegacyAdapter(connector=FakeConn())
        self.assertEqual(adapter.protocol(), 'sftp')
        result = adapter.test_connection()
        self.assertIn('sftp', result['message'])


class TestLogScrubRegression(unittest.TestCase):
    def test_ei_log_source_still_scrubs(self):
        text = (ADDON_ROOT / 'models' / 'ei_log.py').read_text(encoding='utf-8')
        self.assertIn('SECRET_TOKENS', text)
        self.assertIn('api-key', text)


class TestMenusUnchanged(unittest.TestCase):
    def test_six_menus(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'ei_menus.xml')
        children = [m for m in tree.findall('.//menuitem') if m.get('parent') == 'menu_ei_root']
        self.assertEqual(len(children), 6)


class TestServiceFilesPresent(unittest.TestCase):
    def test_service_modules_exist(self):
        required = [
            'exceptions.py', 'retry_service.py', 'transform_service.py',
            'mapping_service.py', 'api_service.py', 'webhook_service.py',
            'sync_service.py', 'master_data_service.py', 'health_service.py',
            'logging_service.py', 'idempotency.py', 'workflow_service.py',
        ]
        for name in required:
            self.assertTrue((SERVICES / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
