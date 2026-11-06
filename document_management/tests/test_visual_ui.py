# -*- coding: utf-8 -*-
"""Phase 5 visual UI structure tests."""
import ast
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = ADDON_ROOT / 'static' / 'src' / 'js'
XML_ROOT = ADDON_ROOT / 'static' / 'src' / 'xml'

SCREEN_IDS = [
    'dashboard', 'repository', 'upload', 'details',
    'access', 'approval', 'workflow', 'search', 'audit',
]


class TestVisualUi(unittest.TestCase):
    def test_eight_primary_screens_only(self):
        app_js = (JS_ROOT / 'dm_app.js').read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r'id: "', app_js)), 9)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, app_js)

    def test_no_settings_or_extra_nav(self):
        app_xml = (XML_ROOT / 'dm_app.xml').read_text(encoding='utf-8')
        self.assertNotIn('Settings', app_xml)
        self.assertNotIn('Reports', app_xml)
        self.assertNotIn('Analytics', app_xml)
        self.assertNotIn('Utility Pro', app_xml)

    def test_visual_regions_exist(self):
        expected = {
            'dashboard': ['Total Documents', 'Storage Used', 'Pending Approval', 'Expiring Soon', 'Document Distribution', 'Status Summary', 'Quick Actions', 'Recent Documents'],
            'repository': ['All Documents', 'My Documents', 'Shared', 'Recent', 'Favorites', 'Archived', 'Municipal', 'Comments ('],
            'upload': ['Drag &amp; Drop files here', 'Document Details', 'Access Settings', 'Lifecycle'],
            'details': ['Overview', 'Version History', 'Approval', 'Access', 'Activity', 'Document Preview', 'PDF'],
            'access': ['Permission Matrix', 'Add User', 'Add Group', 'Share Link'],
            'approval': ['Pending Approval', 'Approved', 'Expiring Soon', 'Expired', 'Approve Document'],
            'workflow': ['Document Workflow', 'Invoice Approval', 'Create New Workflow', 'Workflow Details', 'Intake', 'Approve/Share'],
            'search': ['Keyword Search', 'AI/RAG Search', 'AI Search is not configured'],
            'audit': ['Activity Events', 'Uploads', 'Downloads', 'Shares', 'No audit events'],
        }
        for screen, phrases in expected.items():
            xml = (XML_ROOT / 'screens' / ('%s.xml' % screen)).read_text(encoding='utf-8')
            for phrase in phrases:
                self.assertIn(phrase, xml, '%s missing %s' % (screen, phrase))

    def test_xml_parses(self):
        for path in XML_ROOT.rglob('*.xml'):
            ET.parse(path)

    def test_manifest_unchanged(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['depends'], ['base', 'web'])


if __name__ == '__main__':
    unittest.main()
