# -*- coding: utf-8 -*-
"""Static Phase 3 domain/security validation (no Odoo runtime required)."""
import ast
import csv
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ADDON_ROOT / 'models'

REQUIRED_MODELS = {
    'ei.integration',
    'ei.api.endpoint',
    'ei.api.credential',
    'ei.api.oauth.config',
    'ei.webhook',
    'ei.webhook.subscription',
    'ei.webhook.delivery',
    'ei.connector',
    'ei.connector.credential',
    'ei.connector.mapping',
    'ei.sync.job',
    'ei.sync.run',
    'ei.sync.record',
    'ei.master.entity',
    'ei.master.mapping',
    'ei.master.conflict',
    'ei.log',
}

INTEGRATION_REQUIRED_FIELDS = {
    'name', 'code', 'integration_type', 'provider_system', 'primary_connector_id',
    'environment', 'base_url', 'auth_method', 'state', 'health_state', 'site_ref',
    'active', 'external_ref',
}


def _model_names_from_source():
    names = set()
    for path in MODELS_DIR.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name) and target.id == '_name':
                                if isinstance(stmt.value, ast.Constant):
                                    names.add(stmt.value.value)
    return names


def _fields_in_file(path):
    text = path.read_text(encoding='utf-8')
    return set(re.findall(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*fields\.', text, re.M))


class TestPhase3DomainStatic(unittest.TestCase):
    def test_all_required_models_defined(self):
        names = _model_names_from_source()
        missing = REQUIRED_MODELS - names
        self.assertFalse(missing, f'Missing models: {missing}')

    def test_integration_has_phase3_fields(self):
        fields = _fields_in_file(MODELS_DIR / 'ei_integration.py')
        missing = INTEGRATION_REQUIRED_FIELDS - fields
        self.assertFalse(missing, f'ei.integration missing fields: {missing}')

    def test_connector_categories(self):
        text = (MODELS_DIR / 'ei_connector.py').read_text(encoding='utf-8')
        for cat in ("'erp'", "'crm'", "'bank'", "'whatsapp'", "'legacy'"):
            self.assertIn(cat, text)

    def test_master_entity_codes(self):
        text = (MODELS_DIR / 'ei_master_entity.py').read_text(encoding='utf-8')
        for code in (
            "'customer'", "'supplier'", "'product'", "'employee'",
            "'account'", "'site_location'", "'department'",
        ):
            self.assertIn(code, text)

    def test_log_scrubs_secrets(self):
        text = (MODELS_DIR / 'ei_log.py').read_text(encoding='utf-8')
        self.assertIn('SECRET_TOKENS', text)
        self.assertIn('_scrub', text)
        self.assertIn('master_data', text)

    def test_log_create_drops_banned_keys(self):
        text = (MODELS_DIR / 'ei_log.py').read_text(encoding='utf-8')
        self.assertIn("vals.pop(banned", text)

    def test_sql_constraints_present(self):
        for rel, path in [
            ('ei_integration_code_uniq', 'ei_integration.py'),
            ('ei_api_endpoint_path_method_uniq', 'ei_api_endpoint.py'),
            ('ei_webhook_code_uniq', 'ei_webhook.py'),
            ('ei_master_entity_code_uniq', 'ei_master_entity.py'),
        ]:
            text = (MODELS_DIR / path).read_text(encoding='utf-8')
            self.assertIn(rel, text)

    def test_credential_server_side_guards(self):
        api = (MODELS_DIR / 'ei_api_credential.py').read_text(encoding='utf-8')
        conn = (MODELS_DIR / 'ei_connector_credential.py').read_text(encoding='utf-8')
        self.assertIn('_check_credential_access', api)
        self.assertIn('key_hash', api)
        self.assertIn('_check_manager', conn)
        self.assertIn("row[key] = '********'", conn)

    def test_security_groups_exactly_three(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'ei_security.xml')
        groups = [
            r for r in tree.findall('.//record')
            if r.get('model') == 'res.groups'
        ]
        ids = {g.get('id') for g in groups}
        self.assertEqual(
            ids,
            {'group_ei_user', 'group_ei_manager', 'group_ei_admin'},
        )

    def test_acl_user_cannot_write_credentials(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        cred_user = [
            r for r in rows
            if 'credential' in r['model_id:id'] and r['group_id:id'] == 'group_ei_user'
        ]
        self.assertEqual(cred_user, [], 'Users must not have credential ACL rows')

    def test_acl_user_read_only_on_core(self):
        path = ADDON_ROOT / 'security' / 'ir.model.access.csv'
        with path.open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r['group_id:id'] == 'group_ei_user':
                self.assertEqual(r['perm_write'], '0', r)
                self.assertEqual(r['perm_create'], '0', r)
                self.assertEqual(r['perm_unlink'], '0', r)
                self.assertEqual(r['perm_read'], '1', r)

    def test_record_rules_exist(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'ei_record_rules.xml')
        rules = tree.findall('.//record')
        self.assertGreaterEqual(len(rules), 5)

    def test_menus_still_exactly_six(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'ei_menus.xml')
        children = [
            m for m in tree.findall('.//menuitem')
            if m.get('parent') == 'menu_ei_root'
        ]
        self.assertEqual(len(children), 6)


class TestLogScrubUnit(unittest.TestCase):
    """Pure-Python scrub behavior mirrored from ei.log without importing Odoo."""

    SECRET_TOKENS = (
        'password', 'secret', 'token', 'authorization', 'api_key', 'apikey',
        'api-key', 'client_secret', 'private_key', 'access_token', 'refresh_token',
        'bearer ',
    )

    def _scrub(self, text):
        if not text:
            return text
        lowered = str(text).lower()
        if any(token in lowered for token in self.SECRET_TOKENS):
            return '[scrubbed: potentially sensitive content omitted]'
        return text

    def test_scrubs_password(self):
        self.assertIn('scrubbed', self._scrub('user password=demo'))

    def test_scrubs_api_key(self):
        self.assertIn('scrubbed', self._scrub('X-API-Key: abc'))

    def test_allows_safe_text(self):
        self.assertEqual(self._scrub('sync completed ok'), 'sync completed ok')


if __name__ == '__main__':
    unittest.main()
