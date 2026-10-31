# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

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


@tagged('post_install', '-at_install')
class TestProcurementFoundation(TransactionCase):
    def test_module_installed_with_frozen_dependencies(self):
        module = self.env['ir.module.module'].search([
            ('name', '=', 'procurement_management'),
        ])
        self.assertEqual(module.state, 'installed')
        depends = set(module.dependencies_id.mapped('name'))
        self.assertEqual(depends, {'base', 'web', 'mail'})

    def test_four_groups_and_implied_chain(self):
        user = self.env.ref('procurement_management.group_procurement_user')
        officer = self.env.ref('procurement_management.group_procurement_officer')
        manager = self.env.ref('procurement_management.group_procurement_manager')
        admin = self.env.ref('procurement_management.group_procurement_admin')
        category = self.env.ref('procurement_management.module_category_procurement_management')
        groups = self.env['res.groups'].search([('category_id', '=', category.id)])
        self.assertEqual(groups, user | officer | manager | admin)
        self.assertIn(user, officer.implied_ids)
        self.assertIn(officer, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)
        self.assertEqual(admin.name, 'Procurement Administrator')

    def test_thirteen_menus_and_twelve_actions(self):
        root = self.env.ref('procurement_management.menu_pm_root')
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])
        self.assertEqual(len(children), 12)
        self.assertEqual(root.name, 'Procurement')
        actions = self.env['ir.actions.client'].search([
            ('tag', '=', 'procurement_management_app'),
        ])
        self.assertEqual(len(actions), 12)
        screens = []
        for action in actions.sorted(key=lambda item: item.id):
            screen = (action.params or {}).get('screen')
            self.assertIn(screen, SCREEN_IDS)
            screens.append(screen)
        self.assertEqual(sorted(screens), sorted(SCREEN_IDS))

    def test_ui_api_health_and_business_models(self):
        payload = self.env['procurement.management.ui.api'].health()
        self.assertEqual(payload, {'ok': True, 'module': 'procurement_management'})
        self.assertTrue(self.env['procurement.management.ui.api']._abstract)
        for name in BUSINESS_MODELS:
            self.assertIn(name, self.env.registry)
            self.assertFalse(self.env[name]._abstract)
