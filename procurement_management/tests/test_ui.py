# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.procurement_management.tests.test_domain import BUSINESS_MODELS, ProcurementCase


@tagged('post_install', '-at_install')
class TestProcurementUi(ProcurementCase):
    def _api(self, user):
        return self.env['procurement.management.ui.api'].with_user(user)

    def test_screens_stay_authorized_and_empty(self):
        user_api = self._api(self.user)
        dashboard = user_api.get_dashboard()
        self.assertEqual(dashboard['total_spend'], 0.0)
        self.assertEqual(dashboard['pending_requisitions'], 0)
        self.assertEqual(dashboard['open_rfqs'], 0)
        self.assertEqual(dashboard['open_purchase_orders'], 0)
        self.assertEqual(dashboard['pending_receipts'], 0)
        self.assertEqual(dashboard['invoice_exceptions'], 0)
        self.assertEqual(dashboard['spend_series'], [])
        self.assertEqual(dashboard['recent_orders'], [])
        self.assertEqual(dashboard['priority'], [])
        self.assertEqual(user_api.get_requisitions(), [])
        self.assertEqual(user_api.get_rfqs(), [])
        self.assertEqual(user_api.get_purchase_orders(), [])
        self.assertEqual(user_api.get_goods_receipts(), [])
        self.assertEqual(user_api.get_invoice_matches(), [])
        self.assertEqual(user_api.get_suppliers(), [])
        self.assertEqual(user_api.get_reports(), [])
        comparison = user_api.get_comparison_screen()
        self.assertEqual(comparison['rows'], [])
        self.assertFalse(comparison['recommended_quotation_id'])
        builder = user_api.get_report_builder()
        self.assertEqual(builder['definitions'], [])
        self.assertIn('pdf', builder['formats'])
        home = user_api.get_report_home()
        self.assertEqual(len(home['categories']), 5)
        self.assertEqual(sum(item['count'] for item in home['categories']), 0)
        self.assertEqual(home['recent'], [])
        navigation = user_api.get_navigation()
        self.assertFalse(navigation['approval_matrix'])
        self.assertFalse(navigation['audit'])
        with self.assertRaises(AccessError):
            user_api.get_approval_matrices()
        with self.assertRaises(AccessError):
            user_api.get_audit()
        with self.assertRaises(AccessError):
            user_api.get_matrix_detail(1)

        root = self.env.ref('procurement_management.menu_pm_root')
        self.assertEqual(self.env['ir.ui.menu'].search_count([('parent_id', '=', root.id)]), 12)
        self.assertEqual(self.env['ir.actions.client'].search_count([
            ('tag', '=', 'procurement_management_app'),
        ]), 12)
        self.assertEqual(self.env['ir.module.module'].search([
            ('name', '=', 'procurement_management'),
        ]).state, 'installed')
        for name in BUSINESS_MODELS:
            self.assertFalse(self.env[name]._abstract)
        self.assertTrue(self.env['procurement.management.ui.api']._abstract)
        self.assertEqual(self.env['ir.sequence'].search_count([
            ('code', 'in', [
                'procurement.management.requisition',
                'procurement.management.rfq',
                'procurement.management.purchase.order',
                'procurement.management.receipt',
                'procurement.management.invoice.match',
                'procurement.management.contract',
            ]),
        ]), 6)

    def test_requisition_commands_use_the_server(self):
        api = self._api(self.user)
        detail = api.save_requisition({
            'title': 'UI filters',
            'department': 'Facilities',
            'property_project': 'Tower A',
            'category': 'General',
            'justification': 'Needed',
            'lines': [{
                'description': 'Air filter',
                'quantity': 2,
                'unit_text': 'ea',
                'price_unit': 25,
            }],
        })
        self.assertEqual(detail['state'], 'draft')
        self.assertTrue(detail['actions']['submit'])
        self.assertFalse(detail['actions']['approve'])
        with self.assertRaises(UserError):
            api.requisition_command(detail['id'], 'approve')
        self.assertEqual(api.get_requisition_detail(detail['id'])['state'], 'draft')
        with self.assertRaises(AccessError):
            self._api(self.other).get_requisition_detail(detail['id'])
        try:
            api.requisition_command(detail['id'], 'submit')
        except UserError as error:
            self.assertIn('matrix', str(error).lower())
        else:
            self.fail('Submit without a matrix must return the server error.')
        self.assertEqual(api.get_requisition_detail(detail['id'])['state'], 'draft')

        self._matrix()
        submitted = api.requisition_command(detail['id'], 'submit')
        self.assertEqual(submitted['state'], 'pending')
        self.assertFalse(submitted['actions']['approve'])
        approved = self._api(self.manager).requisition_command(detail['id'], 'approve', 'ok')
        self.assertEqual(approved['state'], 'approved')
        rows = api.get_requisitions(search='UI filters')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state'], 'approved')

    def test_operational_screens_use_server_dtos(self):
        self._matrix()
        api = self._api(self.officer)
        rfq = api.save_rfq({
            'description': 'UI RFQ',
            'department': 'Facilities',
            'commercial_weight': 40,
            'technical_weight': 60,
            'partner_ids': [self.partner.id, self.partner_b.id],
        })
        api.rfq_command(rfq['id'], 'issue')
        self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq['id'],
            'partner_id': self.partner.id,
            'freight_amount': 20,
            'commercial_score': 8,
            'technical_score': 4,
            'line_ids': [(0, 0, {
                'description': 'Option A',
                'quantity': 1,
                'price_unit': 100,
            })],
        })
        cheaper = self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq['id'],
            'partner_id': self.partner_b.id,
            'commercial_score': 5,
            'technical_score': 5,
            'line_ids': [(0, 0, {
                'description': 'Option B',
                'quantity': 1,
                'price_unit': 110,
            })],
        })
        api.rfq_command(rfq['id'], 'evaluate')
        screen = api.get_comparison_screen(rfq['id'])
        self.assertEqual(screen['recommended_quotation_id'], cheaper.id)
        self.assertEqual(screen['commercial_weight'], 40)
        self.assertEqual(len(screen['rows']), 2)
        self.assertTrue(screen['rows'][0]['lines'])
        selected = api.comparison_select(cheaper.id, 'Lowest landed cost')
        self.assertEqual(selected['selection_result'], 'pending')
        self.assertEqual(selected['selection_status'], 'pending')
        self.assertNotEqual(cheaper.state, 'selected')
        self.assertEqual(api.get_rfq_detail(rfq['id'])['state'], 'under_evaluation')
        self.assertTrue(api.get_rfqs(search='UI RFQ'))

        group = self.env.ref('procurement_management.group_procurement_manager')
        matrix = self._api(self.manager).save_matrix({
            'name': 'UI Matrix',
            'department': 'Facilities',
            'mode': 'sequential',
            'levels': [{
                'approver_group_id': group.id,
                'required_signoff': True,
                'escalation_hours': 24,
                'escalation_group_id': group.id,
            }],
        })
        self.assertEqual(matrix['state'], 'draft')
        self.assertEqual(matrix['levels'][0]['approver_group_id'], group.id)
        self.assertTrue(self._api(self.manager).get_approval_matrices())

        order = self.env['procurement.management.purchase.order'].with_user(self.officer).create({
            'partner_id': self.partner.id,
            'department': 'Facilities',
            'line_ids': [(0, 0, {
                'description': 'Valve',
                'quantity': 1,
                'price_unit': 15,
            })],
        })
        detail = api.get_purchase_order_detail(order.id)
        self.assertEqual(detail['state'], 'draft')
        self.assertEqual(detail['display_status'], 'draft')
        self.assertTrue(detail['lines'])
        printed = api.print_purchase_order(order.id)
        if printed.get('ok'):
            import base64
            self.assertTrue(base64.b64decode(printed['datas']).startswith(b'%PDF'))
        else:
            self.assertIn('unavailable', (printed.get('error') or '').lower())
        self.assertTrue(api.get_purchase_orders(search=order.name))

        receipt = self.env['procurement.management.receipt'].with_user(self.officer).create({
            'order_id': order.id,
            'partner_id': order.partner_id.id,
            'company_id': order.company_id.id,
            'line_ids': [(0, 0, {
                'order_line_id': order.line_ids.id,
                'description': 'Valve',
                'ordered_qty': 1,
            })],
        })
        receipt_detail = api.get_receipt_detail(receipt.id)
        self.assertEqual(receipt_detail['state'], 'expected')
        self.assertEqual(receipt_detail['lines'][0]['remaining_qty'], 1)
        self.assertTrue(api.get_goods_receipts())

        match = self.env['procurement.management.invoice.match'].with_user(self.officer).create({
            'supplier_invoice_number': 'INV-UI-%s' % self._testMethodName,
            'partner_id': order.partner_id.id,
            'order_id': order.id,
            'company_id': order.company_id.id,
            'invoice_amount': 15,
            'line_ids': [(0, 0, {
                'description': 'Valve',
                'order_line_id': order.line_ids.id,
                'po_qty': 1,
                'receipt_qty': 0,
                'invoice_qty': 1,
                'po_price': 15,
                'invoice_price': 15,
            })],
        })
        invoice = api.get_invoice_detail(match.id)
        self.assertEqual(invoice['lines'][0]['po_qty'], 1)
        self.assertEqual(invoice['lines'][0]['invoice_qty'], 1)
        self.assertFalse(invoice['duplicate_flag'])
        self.assertTrue(api.get_invoice_matches())

        supplier = api.save_supplier({
            'partner_id': self.partner.id,
            'vendor_code': 'UI-1',
            'category': 'Mechanical',
            'state': 'preferred',
        })
        self.assertEqual(supplier['state'], 'preferred')
        self.assertTrue(api.get_suppliers(search='UI-1'))

        manager = self._api(self.manager)
        definition_id = manager.save_report_definition({
            'name': 'UI Spend',
            'report_type': 'spend',
            'metrics': 'amount',
        })
        preview = manager.report_preview(definition_id)
        self.assertIn('Reference', preview['columns'])
        self.assertIsInstance(preview['rows'], list)
        exported = manager.report_export(definition_id, 'csv')
        self.assertTrue(exported['ok'])
        self.assertTrue(exported['datas'])
        pdf = manager.report_export(definition_id, 'pdf')
        if pdf.get('ok'):
            import base64
            self.assertTrue(base64.b64decode(pdf['datas']).startswith(b'%PDF'))
        else:
            self.assertIn('unavailable', (pdf.get('error') or '').lower())
        with self.assertRaises(AccessError):
            self._api(self.user).report_preview(definition_id)

        events = manager.get_audit()
        self.assertTrue(events)
        self.assertIn('timestamp', events[0])
        self.assertTrue(manager.export_audit()['ok'])
        meta = manager.get_audit_meta()
        self.assertGreater(meta['total'], 0)
