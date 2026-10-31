# -*- coding: utf-8 -*-
"""Foundation structure checks. No database and no demo data."""
import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ADDON_ROOT = Path(__file__).resolve().parents[1]

SCREEN_IDS = [
    'dashboard',
    'requisitions',
    'rfqs',
    'comparison',
    'approval_matrix',
    'purchase_orders',
    'goods_receipts',
    'invoice_matching',
    'suppliers',
    'reports',
    'report_builder',
    'audit',
]

CHILD_MENUS = [
    ('Dashboard', 'action_pm_dashboard', 'dashboard', 'group_procurement_user'),
    ('Purchase Requisitions', 'action_pm_requisitions', 'requisitions', 'group_procurement_user'),
    ('RFQs & Quotations', 'action_pm_rfqs', 'rfqs', 'group_procurement_user'),
    ('Quotation Comparison', 'action_pm_comparison', 'comparison', 'group_procurement_user'),
    ('Approval Matrix', 'action_pm_approval_matrix', 'approval_matrix', 'group_procurement_manager'),
    ('Purchase Orders', 'action_pm_purchase_orders', 'purchase_orders', 'group_procurement_user'),
    ('Goods Receipts', 'action_pm_goods_receipts', 'goods_receipts', 'group_procurement_user'),
    ('Invoice Matching', 'action_pm_invoice_matching', 'invoice_matching', 'group_procurement_user'),
    ('Supplier Management', 'action_pm_suppliers', 'suppliers', 'group_procurement_user'),
    ('Procurement Reports', 'action_pm_reports', 'reports', 'group_procurement_user'),
    ('Report Builder & Export', 'action_pm_report_builder', 'report_builder', 'group_procurement_user'),
    ('Procurement Activity / Audit', 'action_pm_audit', 'audit', 'group_procurement_manager'),
]

BUSINESS_MODELS = [
    'procurement.management.requisition',
    'procurement.management.requisition.line',
    'procurement.management.rfq',
    'procurement.management.rfq.supplier',
    'procurement.management.quotation',
    'procurement.management.quotation.line',
    'procurement.management.approval.matrix',
    'procurement.management.approval.level',
    'procurement.management.approval.request',
    'procurement.management.approval.decision',
    'procurement.management.purchase.order',
    'procurement.management.purchase.order.line',
    'procurement.management.receipt',
    'procurement.management.receipt.line',
    'procurement.management.invoice.match',
    'procurement.management.invoice.match.line',
    'procurement.management.supplier.profile',
    'procurement.management.contract',
    'procurement.management.report.definition',
    'procurement.management.report.run',
    'procurement.management.audit.event',
]

SERVICE_FILES = [
    'requisition_service.py',
    'rfq_service.py',
    'comparison_service.py',
    'approval_service.py',
    'purchase_order_service.py',
    'receipt_service.py',
    'invoice_match_service.py',
    'supplier_service.py',
    'report_service.py',
    'audit_service.py',
    'notification_service.py',
]


class TestAddonStructure(unittest.TestCase):
    def test_manifest(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        self.assertEqual(data['name'], 'Procurement Management')
        self.assertEqual(data['version'], '18.0.1.0.0')
        self.assertEqual(data['category'], 'Productivity')
        self.assertEqual(data['author'], 'FMS')
        self.assertEqual(data['license'], 'LGPL-3')
        self.assertEqual(data['depends'], ['base', 'web', 'mail'])
        self.assertTrue(data['installable'])
        self.assertTrue(data['application'])
        self.assertFalse(data['auto_install'])
        self.assertNotIn('demo', data)
        assets = data['assets']['web.assets_backend']
        self.assertIn('procurement_management/static/src/js/pm_app.js', assets)
        self.assertIn('procurement_management/static/src/xml/pm_app.xml', assets)
        joined = '\n'.join(assets)
        self.assertNotIn('fonts.googleapis', joined)
        self.assertNotIn('cdn.', joined)

    def test_no_sibling_or_domain_dependency(self):
        data = ast.literal_eval((ADDON_ROOT / '__manifest__.py').read_text(encoding='utf-8'))
        forbidden = {
            'purchase', 'stock', 'account', 'product',
            'workflow_engine', 'document_management', 'command_center',
            'video_analytics', 'enterprise_integration',
        }
        self.assertFalse(forbidden & set(data['depends']))

    def test_thirteen_menus(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'pm_menus.xml')
        menus = tree.findall('.//menuitem')
        self.assertEqual(len(menus), 13)
        root = tree.find(".//menuitem[@id='menu_pm_root']")
        self.assertEqual(root.get('name'), 'Procurement')
        children = [m for m in menus if m.get('parent') == 'menu_pm_root']
        self.assertEqual(len(children), 12)
        children.sort(key=lambda item: int(item.get('sequence')))
        for menu, expected in zip(children, CHILD_MENUS):
            name, action, _screen, group = expected
            self.assertEqual(menu.get('name').replace('&amp;', '&'), name)
            self.assertEqual(menu.get('action'), action)
            self.assertTrue(menu.get('groups').endswith(group))

    def test_twelve_client_actions(self):
        tree = ET.parse(ADDON_ROOT / 'views' / 'pm_client_actions.xml')
        records = tree.findall("./record[@model='ir.actions.client']")
        self.assertEqual(len(records), 12)
        screens = []
        for record in records:
            self.assertEqual(record.find("./field[@name='tag']").text, 'procurement_management_app')
            context = record.find("./field[@name='context']").text
            params = record.find("./field[@name='params']").get('eval')
            screen = context.split("'")[3]
            self.assertIn("'screen': '%s'" % screen, params)
            screens.append(screen)
        self.assertEqual(screens, SCREEN_IDS)

    def test_owl_shell_screen_ids(self):
        js = (ADDON_ROOT / 'static' / 'src' / 'js' / 'pm_app.js').read_text(encoding='utf-8')
        xml = (ADDON_ROOT / 'static' / 'src' / 'xml' / 'pm_app.xml').read_text(encoding='utf-8')
        self.assertIn('export class ProcurementManagementApp', js)
        self.assertIn('procurement_management_app', js)
        self.assertIn('Utility Management', xml)
        self.assertIn('Procurement', xml)
        self.assertIn('pm-sidebar', xml)
        for screen in SCREEN_IDS:
            self.assertIn('id: "%s"' % screen, js)
        self.assertNotIn('fonts.googleapis', js + xml)
        self.assertNotIn('₹', js + xml)

    def test_four_groups(self):
        tree = ET.parse(ADDON_ROOT / 'security' / 'pm_security.xml')
        groups = tree.findall(".//record[@model='res.groups']")
        self.assertEqual(len(groups), 4)
        ids = [group.get('id') for group in groups]
        self.assertEqual(ids, [
            'group_procurement_user',
            'group_procurement_officer',
            'group_procurement_manager',
            'group_procurement_admin',
        ])
        admin = tree.find(".//record[@id='group_procurement_admin']")
        implied = admin.find("./field[@name='implied_ids']").get('eval')
        self.assertIn('group_procurement_manager', implied)

    def test_service_package_and_no_business_models(self):
        service_dir = ADDON_ROOT / 'services'
        for name in SERVICE_FILES:
            self.assertTrue((service_dir / name).exists(), name)
        model_text = (ADDON_ROOT / 'models' / 'ui_api.py').read_text(encoding='utf-8')
        self.assertIn("models.AbstractModel", model_text)
        self.assertIn("procurement.management.ui.api", model_text)
        self.assertIn('def health', model_text)
        for technical_name in BUSINESS_MODELS:
            self.assertNotIn("_name = '%s'" % technical_name, model_text)
        self.assertFalse((ADDON_ROOT / 'controllers').exists())
        self.assertFalse((ADDON_ROOT / 'demo').exists())

    def test_self_approval_remains_open(self):
        text = (ADDON_ROOT / 'services' / 'approval_service.py').read_text(encoding='utf-8')
        self.assertIn('OPEN', text)
        self.assertIn('Option A', text)
        self.assertIn('Option B', text)
