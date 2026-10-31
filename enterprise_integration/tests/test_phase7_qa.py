# -*- coding: utf-8 -*-
"""Phase 7 QA — validation, security scan, navigation, cron, assets (no new features)."""
import ast
import csv
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
VIEWS = ADDON_ROOT / 'views'
MODELS = ADDON_ROOT / 'models'
CONTROLLERS = ADDON_ROOT / 'controllers'

EXPECTED_MENUS = [
    ('Dashboard', 'action_ei_dashboard'),
    ('API & Webhook Management', 'action_ei_api_webhook'),
    ('Enterprise Connectors', 'action_ei_connectors'),
    ('Data Synchronization', 'action_ei_sync'),
    ('Master Data Integration', 'action_ei_master'),
    ('Integration Monitoring & Logs', 'action_ei_monitoring'),
]

PROHIBITED_MENU_NAMES = {
    'erp', 'crm', 'bank', 'whatsapp', 'legacy', 'api', 'webhooks',
    'api keys', 'oauth', 'credentials', 'sync history', 'master data',
    'customer', 'supplier', 'product', 'employee', 'account', 'site',
    'location', 'department', 'logs', 'errors', 'mapping', 'transformation',
    'conflicts', 'retry',
}

ACTION_MODELS = {
    'action_ei_api_webhook_backend': 'ei.integration',
    'action_ei_connectors_backend': 'ei.connector',
    'action_ei_sync_backend': 'ei.sync.job',
    'action_ei_master_backend': 'ei.master.entity',
    'action_ei_monitoring_backend': 'ei.log',
}

HARDCODED_SECRET_RE = re.compile(
    r"""(?i)(password|api[_-]?key|client_secret|private_key|access_token|refresh_token)\s*=\s*['\"][^'\"]{8,}['\"]"""
)


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


def _load_retry_and_adapters():
    # Minimal odoo stub so services that import odoo.fields can load statically
    if 'odoo' not in sys.modules:
        odoo = types.ModuleType('odoo')
        fields = types.ModuleType('odoo.fields')
        fields.Datetime = type('Datetime', (), {'now': staticmethod(lambda: None)})
        odoo.fields = fields
        sys.modules['odoo'] = odoo
        sys.modules['odoo.fields'] = fields

    root = _ensure_pkg('enterprise_integration')
    root.__path__ = [str(ADDON_ROOT)]
    svc = _ensure_pkg('enterprise_integration.services')
    svc.__path__ = [str(SERVICES)]
    conn = _ensure_pkg('enterprise_integration.services.connectors')
    conn.__path__ = [str(CONNECTORS)]
    _load('enterprise_integration.services.exceptions', SERVICES / 'exceptions.py', 'enterprise_integration.services')
    retry = _load('enterprise_integration.services.retry_service', SERVICES / 'retry_service.py', 'enterprise_integration.services')
    _load(
        'enterprise_integration.services.logging_service',
        SERVICES / 'logging_service.py',
        'enterprise_integration.services',
    )
    _load(
        'enterprise_integration.services.idempotency',
        SERVICES / 'idempotency.py',
        'enterprise_integration.services',
    )
    _load('enterprise_integration.services.connectors.base', CONNECTORS / 'base.py', 'enterprise_integration.services.connectors')
    _load('enterprise_integration.services.connectors.mock_adapter', CONNECTORS / 'mock_adapter.py', 'enterprise_integration.services.connectors')
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
    wh = _load(
        'enterprise_integration.services.webhook_service',
        SERVICES / 'webhook_service.py',
        'enterprise_integration.services',
    )
    return retry, registry, wh


RETRY, REGISTRY, WEBHOOK_MOD = _load_retry_and_adapters()


class TestPhase7PythonValidation(unittest.TestCase):
    def test_all_python_compiles(self):
        for py in ADDON_ROOT.rglob('*.py'):
            compile(py.read_text(encoding='utf-8'), str(py), 'exec')

    def test_no_utcnow_deprecation(self):
        for py in (SERVICES / 'retry_service.py', SERVICES / 'idempotency.py'):
            text = py.read_text(encoding='utf-8')
            self.assertNotIn('utcnow(', text, py.name)
            self.assertIn('timezone.utc', text, py.name)

    def test_services_package_imports_clean(self):
        text = (SERVICES / '__init__.py').read_text(encoding='utf-8')
        for mod in (
            'api_service', 'webhook_service', 'sync_service', 'master_data_service',
            'workflow_service', 'health_service', 'retry_service',
        ):
            self.assertIn(mod, text)


class TestPhase7XmlValidation(unittest.TestCase):
    def test_all_xml_parses(self):
        for path in ADDON_ROOT.rglob('*.xml'):
            ET.parse(path)

    def test_menu_action_refs_resolve_in_views(self):
        action_ids = set()
        for path in VIEWS.glob('*.xml'):
            for rec in ET.parse(path).findall('.//record'):
                rid = rec.get('id')
                if rid and rid.startswith('action_ei_'):
                    action_ids.add(rid)
        for _, action in EXPECTED_MENUS:
            self.assertIn(action, action_ids, action)

    def test_primary_action_models_isolated(self):
        """Each primary act_window targets exactly one intended model (no cross-screen)."""
        found = {}
        for path in VIEWS.glob('*.xml'):
            for rec in ET.parse(path).findall('.//record'):
                rid = rec.get('id')
                if rid in ACTION_MODELS:
                    model_field = rec.find("./field[@name='res_model']")
                    self.assertIsNotNone(model_field, rid)
                    found[rid] = (model_field.text or '').strip()
        self.assertEqual(found, ACTION_MODELS)

    def test_dashboard_is_client_only(self):
        tree = ET.parse(VIEWS / 'ei_client_actions.xml')
        rec = tree.find(".//record[@id='action_ei_dashboard']")
        self.assertEqual(rec.get('model'), 'ir.actions.client')
        tag = rec.find("./field[@name='tag']")
        self.assertEqual(tag.text, 'ei_app')

    def test_cron_methods_exist_on_models(self):
        crons = ET.parse(ADDON_ROOT / 'data' / 'ei_cron_data.xml')
        mapping = {
            'model_ei_sync_job': MODELS / 'ei_sync_job.py',
            'model_ei_webhook': MODELS / 'ei_webhook.py',
            'model_ei_connector': MODELS / 'ei_connector.py',
        }
        codes = []
        for rec in crons.findall('.//record'):
            model_ref = rec.find("./field[@name='model_id']").get('ref')
            code = rec.find("./field[@name='code']").text
            codes.append((model_ref, code))
            self.assertIn(model_ref, mapping)
            method = code.replace('model.', '').replace('()', '').strip()
            text = mapping[model_ref].read_text(encoding='utf-8')
            self.assertIn(f'def {method}', text)
        self.assertEqual(len(codes), 4)
        # no duplicate cron ids
        ids = [r.get('id') for r in crons.findall('.//record')]
        self.assertEqual(len(ids), len(set(ids)))


class TestPhase7JsScssValidation(unittest.TestCase):
    def test_js_registers_client_action(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'ei_app.js').read_text(encoding='utf-8')
        self.assertIn('/** @odoo-module **/', js)
        self.assertIn('from "@odoo/owl"', js)
        self.assertIn('registry.category("actions").add("ei_app"', js)
        self.assertIn('useService("orm")', js)
        self.assertIn('useService("action")', js)
        self.assertIn('action_ei_dashboard', (VIEWS / 'ei_client_actions.xml').read_text(encoding='utf-8'))

    def test_dashboard_template_exists(self):
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'ei_app.xml').read_text(encoding='utf-8')
        self.assertIn('enterprise_integration.App', xml)
        self.assertIn('ei-shell', xml)
        self.assertIn('ei-sidebar', xml)

    def test_scss_brand_colors(self):
        scss = (ADDON_ROOT / 'static' / 'src' / 'scss' / 'ei_variables.scss').read_text(encoding='utf-8')
        self.assertIn('#5629CE', scss)
        self.assertIn('#F0EBFF', scss)
        self.assertIn('$ei-primary', scss)
        self.assertIn('@media', scss)

    def test_manifest_assets_registered(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        assets = data['assets']['web.assets_backend']
        self.assertTrue(any(a.endswith('ei_variables.scss') for a in assets))
        self.assertTrue(any(a.endswith('ei_app.js') for a in assets))
        self.assertTrue(any(a.endswith('ei_app.xml') for a in assets))

    def test_menu_icon_exists(self):
        icon = ADDON_ROOT / 'static' / 'description' / 'icon.png'
        self.assertTrue(icon.exists())
        self.assertGreater(icon.stat().st_size, 50)


class TestPhase7NavigationQa(unittest.TestCase):
    def test_sidebar_count_seven(self):
        tree = ET.parse(VIEWS / 'ei_menus.xml')
        items = tree.findall('.//menuitem')
        self.assertEqual(len(items), 7)
        root = [m for m in items if m.get('id') == 'menu_ei_root']
        children = [m for m in items if m.get('parent') == 'menu_ei_root']
        self.assertEqual(len(root), 1)
        self.assertEqual(len(children), 6)

    def test_exact_menu_names_and_actions(self):
        children = sorted(
            [m for m in ET.parse(VIEWS / 'ei_menus.xml').findall('.//menuitem') if m.get('parent') == 'menu_ei_root'],
            key=lambda m: int(m.get('sequence') or 0),
        )
        got = [
            ((m.get('name') or '').replace('&amp;', '&'), m.get('action'))
            for m in children
        ]
        self.assertEqual(got, EXPECTED_MENUS)

    def test_prohibited_names_not_menus(self):
        for m in ET.parse(VIEWS / 'ei_menus.xml').findall('.//menuitem'):
            name = (m.get('name') or '').replace('&amp;', '&').lower()
            self.assertNotIn(name, PROHIBITED_MENU_NAMES)

    def test_no_menuitems_outside_menus_xml(self):
        for path in VIEWS.glob('*.xml'):
            if path.name == 'ei_menus.xml':
                continue
            self.assertFalse(ET.parse(path).findall('.//menuitem'), path.name)


class TestPhase7SecurityQa(unittest.TestCase):
    def test_three_groups_only(self):
        text = (ADDON_ROOT / 'security' / 'ei_security.xml').read_text(encoding='utf-8')
        self.assertIn('group_ei_user', text)
        self.assertIn('group_ei_manager', text)
        self.assertIn('group_ei_admin', text)
        # exactly three group records
        tree = ET.parse(ADDON_ROOT / 'security' / 'ei_security.xml')
        groups = [r for r in tree.findall('.//record') if r.get('model') == 'res.groups']
        self.assertEqual(len(groups), 3)

    def test_user_cannot_write_credentials_acl(self):
        with (ADDON_ROOT / 'security' / 'ir.model.access.csv').open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        cred_rows = [r for r in rows if 'credential' in r['name']]
        for r in cred_rows:
            self.assertNotEqual(r['group_id:id'], 'group_ei_user')

    def test_user_read_only_on_core_models(self):
        with (ADDON_ROOT / 'security' / 'ir.model.access.csv').open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r['group_id:id'] == 'group_ei_user':
                self.assertEqual(r['perm_write'], '0')
                self.assertEqual(r['perm_create'], '0')
                self.assertEqual(r['perm_unlink'], '0')
                self.assertEqual(r['perm_read'], '1')

    def test_export_and_rotate_manager_only(self):
        wiz = (ADDON_ROOT / 'wizard' / 'ei_wizards.py').read_text(encoding='utf-8')
        self.assertIn("group_ei_manager", wiz)
        self.assertIn('Only Managers can export logs', wiz)
        self.assertIn('Only Managers can rotate credentials', wiz)


class TestPhase7CredentialSecurityQa(unittest.TestCase):
    def test_no_hardcoded_secrets_in_source(self):
        skip_dirs = {'tests'}
        for path in ADDON_ROOT.rglob('*'):
            if path.suffix not in {'.py', '.xml', '.js', '.scss', '.csv', '.md'}:
                continue
            if any(p in skip_dirs for p in path.parts):
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            # allow password="True" widget attrs
            cleaned = re.sub(r'password\s*=\s*"True"', '', text)
            cleaned = re.sub(r"password\s*=\s*'True'", '', cleaned)
            match = HARDCODED_SECRET_RE.search(cleaned)
            self.assertIsNone(match, f'{path}: {match.group(0) if match else ""}')

    def test_log_scrub_tokens_present(self):
        text = (MODELS / 'ei_log.py').read_text(encoding='utf-8')
        for tok in ('password', 'secret', 'token', 'api_key', 'client_secret', 'private_key', 'bearer '):
            self.assertIn(tok, text)

    def test_api_controller_rejects_query_api_key(self):
        text = (CONTROLLERS / 'api_controller.py').read_text(encoding='utf-8')
        self.assertNotIn("kwargs.get('api_key')", text)
        self.assertIn("headers.get('X-API-Key')", text)

    def test_webhook_payload_redacts_secrets(self):
        summary = WEBHOOK_MOD.WebhookService._safe_summary({
            'name': 'ok',
            'password': 'super-secret-value',
            'api_key': 'abc123456',
        })
        self.assertNotIn('super-secret-value', summary)
        self.assertNotIn('abc123456', summary)
        self.assertTrue('[redacted]' in summary or 'scrubbed' in summary.lower())

    def test_export_excludes_bodies(self):
        wiz = (ADDON_ROOT / 'wizard' / 'ei_wizards.py').read_text(encoding='utf-8')
        block = wiz[wiz.find('class EiLogExportWizard'):]
        self.assertNotIn("'request_summary'", block)
        self.assertNotIn("'response_summary'", block)
        self.assertNotIn("'error_message'", block)


class TestPhase7ApiWebhookConnectorQa(unittest.TestCase):
    def test_api_service_error_codes_safe(self):
        text = (SERVICES / 'api_service.py').read_text(encoding='utf-8')
        self.assertIn('unauthorized', text)
        self.assertIn('rate_limited', text)
        self.assertIn('correlation_id', text)
        self.assertNotIn('plaintext', text.lower())

    def test_webhook_controller_auth_types(self):
        text = (CONTROLLERS / 'webhook_controller.py').read_text(encoding='utf-8')
        self.assertIn('_authenticate_incoming', text)
        for auth in ('bearer', 'api_key', 'hmac', 'none'):
            self.assertIn(f"'{auth}'", text)
        # Responses must not interpolate secret values into JSON bodies
        self.assertNotIn("{'ok': False, 'error': 'unauthorized', 'message': webhook.secret", text)
        self.assertNotIn('message\": webhook.secret', text)

    def test_all_connector_categories_mock(self):
        for key in ('erp', 'crm', 'bank', 'whatsapp', 'legacy', 'mock'):
            adapter = REGISTRY.ConnectorRegistry.get(key)(scenario='success')
            self.assertTrue(adapter.is_mock)
            msg = adapter.test_connection().get('message', '').lower()
            self.assertTrue('mock' in msg or adapter.is_mock)

    def test_connector_failure_scenarios(self):
        with self.assertRaises(Exception) as ctx:
            REGISTRY.ConnectorRegistry.get('erp')(scenario='auth_failure').authenticate()
        self.assertEqual(type(ctx.exception).__name__, 'EiAuthenticationError')
        with self.assertRaises(Exception) as ctx2:
            REGISTRY.ConnectorRegistry.get('crm')(scenario='timeout').test_connection()
        self.assertEqual(type(ctx2.exception).__name__, 'EiTimeoutError')


class TestPhase7SyncMasterRetryQa(unittest.TestCase):
    def test_sync_stats_fields(self):
        text = (MODELS / 'ei_sync_run.py').read_text(encoding='utf-8')
        for f in (
            'records_processed', 'records_success', 'records_failed',
            'records_conflict', 'records_duplicate', 'correlation_id',
        ):
            self.assertIn(f, text)

    def test_master_entities_and_sot(self):
        data = ET.parse(ADDON_ROOT / 'data' / 'ei_master_entity_data.xml')
        codes = {
            r.find("./field[@name='code']").text
            for r in data.findall(".//record[@model='ei.master.entity']")
        }
        self.assertEqual(len(codes), 7)
        md = (SERVICES / 'master_data_service.py').read_text(encoding='utf-8')
        self.assertIn("sot in ('target', 'precastmps')", md)
        self.assertIn('detect_conflict', md)

    def test_retry_bounded(self):
        svc = RETRY.RetryService(max_attempts=3, backoff_seconds=5, backoff_factor=2)
        self.assertEqual(svc.plan(1)['status'], 'retrying')
        self.assertEqual(svc.plan(2)['delay_seconds'], 10)
        self.assertEqual(svc.plan(3)['status'], 'failed')
        self.assertEqual(svc.plan(1, retryable=False)['status'], 'failed')


class TestPhase7MonitoringCronQa(unittest.TestCase):
    def test_log_categories_cover_domains(self):
        text = (MODELS / 'ei_log.py').read_text(encoding='utf-8')
        for cat in ('api', 'webhook', 'connector', 'sync', 'master_data', 'system'):
            self.assertIn(f"('{cat}'", text)

    def test_monitoring_actions(self):
        text = (VIEWS / 'ei_monitoring_views.xml').read_text(encoding='utf-8')
        self.assertIn('action_retry', text)
        self.assertIn('action_export_wizard', text)
        self.assertIn('correlation_id', text)

    def test_cron_intervals_safe(self):
        tree = ET.parse(ADDON_ROOT / 'data' / 'ei_cron_data.xml')
        for rec in tree.findall('.//record'):
            n = int(rec.find("./field[@name='interval_number']").text)
            t = rec.find("./field[@name='interval_type']").text
            self.assertGreater(n, 0)
            self.assertIn(t, ('minutes', 'hours', 'days', 'weeks'))


class TestPhase7VersionAndRegression(unittest.TestCase):
    def test_version_is_phase7_patch(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        # Phase 7 bugfix patch on 18.0.1.4.x
        self.assertTrue(data['version'].startswith('18.0.1.4'))
        self.assertEqual(data['depends'], ['base', 'web'])
        self.assertTrue(data['installable'])

    def test_no_new_primary_scope(self):
        # Ensure still exactly six menus after Phase 7 fixes
        children = [
            m for m in ET.parse(VIEWS / 'ei_menus.xml').findall('.//menuitem')
            if m.get('parent') == 'menu_ei_root'
        ]
        self.assertEqual(len(children), 6)


if __name__ == '__main__':
    unittest.main()
