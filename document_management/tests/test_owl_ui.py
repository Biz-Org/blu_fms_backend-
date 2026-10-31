# -*- coding: utf-8 -*-
"""Phase 2 OWL UI foundation tests."""
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = ADDON_ROOT / 'static' / 'src' / 'js'
XML_ROOT = ADDON_ROOT / 'static' / 'src' / 'xml'

SCREEN_IDS = [
    'dashboard',
    'repository',
    'upload',
    'details',
    'access',
    'approval',
    'workflow',
    'search',
    'audit',
]


def _read(path):
    return path.read_text(encoding='utf-8')


class TestOwlUi(unittest.TestCase):
    def test_eight_screen_files_registered(self):
        app_js = _read(JS_ROOT / 'dm_app.js')
        self.assertIn('registry.category("actions").add("document_management_app"', app_js)
        self.assertEqual(len(re.findall(r'id: "', app_js)), 9)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, app_js)
            self.assertTrue((JS_ROOT / 'screens' / ('%s.js' % screen)).exists(), screen)
            self.assertTrue((XML_ROOT / 'screens' / ('%s.xml' % screen)).exists(), screen)
            self.assertIn('./screens/%s' % screen, app_js)

    def test_sidebar_has_eight_items(self):
        app_js = _read(JS_ROOT / 'dm_app.js')
        labels = re.findall(r'label: "([^"]+)"', app_js)
        self.assertEqual(labels, [
            'DM Dashboard',
            'DM Repository',
            'DM Upload',
            'DM Details',
            'DM Access Control',
            'DM Approval & Expiry',
            'DM Workflow',
            'DM AI Search',
            'DM Audit',
        ])
        app_xml = _read(XML_ROOT / 'dm_app.xml')
        self.assertIn('t-foreach="screens"', app_xml)
        self.assertIn('Document Management', app_xml)
        self.assertNotIn('Utility Pro', app_xml)

    def test_refresh_loading_empty_error_states(self):
        expected_empty = {
            'dashboard': ['No documents yet'],
            'repository': ['No documents'],
            'upload': ['Ready to upload'],
            'details': ['Select a document from the repository'],
            'access': ['Select a document to manage access'],
            'approval': ['No approval or expiry items'],
            'workflow': ['No workflows'],
            'search': ['AI Search is not configured', 'No search results'],
            'audit': ['No audit events'],
        }
        for screen, phrases in expected_empty.items():
            xml = _read(XML_ROOT / 'screens' / ('%s.xml' % screen))
            self.assertIn('dm-loading', xml)
            self.assertIn('dm-error', xml)
            self.assertIn('Retry', xml)
            self.assertIn('Refresh', xml)
            for phrase in phrases:
                self.assertIn(phrase, xml, screen)

    def test_no_fake_kpi_or_operational_rows(self):
        pattern = re.compile(r'(documents_total|pending_approval|expiring_soon)\s*[:=]\s*[1-9]')
        for path in (JS_ROOT / 'screens').glob('*.js'):
            text = _read(path)
            self.assertIsNone(pattern.search(text), path.name)
            self.assertNotIn('sample data', text.lower())
            self.assertNotIn('4286', text)
        dashboard = _read(JS_ROOT / 'screens' / 'dashboard.js')
        self.assertIn('data.kpis', dashboard)
        self.assertIn('kpis: null', dashboard)

    def test_templates_parse(self):
        for path in XML_ROOT.rglob('*.xml'):
            ET.parse(path)

    def test_no_forbidden_integrations(self):
        blob = ''
        for path in ADDON_ROOT.rglob('*'):
            if not path.is_file() or path.suffix.lower() in {'.png', '.pyc'}:
                continue
            if 'tests' in path.parts:
                continue
            if path.suffix in {'.js', '.xml', '.scss', '.py'}:
                blob += _read(path)
        self.assertNotIn('bus.bus', blob)
        self.assertNotIn('WebSocket', blob)
        self.assertNotIn('setInterval', blob)
        self.assertNotIn('fonts.googleapis', blob)
        self.assertNotIn('stitch.withgoogle', blob)
        self.assertNotIn('Utility Pro', blob)


if __name__ == '__main__':
    unittest.main()
