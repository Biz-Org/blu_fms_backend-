# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.procurement_management.services.approval_service import ApprovalService
from odoo.addons.procurement_management.services.comparison_service import ComparisonService
from odoo.addons.procurement_management.services.audit_service import AuditService

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


@tagged('post_install', '-at_install')
class ProcurementCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = self._make_user('user', 'group_procurement_user')
        self.other = self._make_user('other', 'group_procurement_user')
        self.officer = self._make_user('officer', 'group_procurement_officer')
        self.manager = self._make_user('manager', 'group_procurement_manager')
        self.admin = self._make_user('admin', 'group_procurement_admin')
        self.partner = self.env['res.partner'].create({
            'name': 'Supplier %s' % self._testMethodName,
            'email': 'supplier@example.com',
        })
        self.partner_b = self.env['res.partner'].create({
            'name': 'Supplier B %s' % self._testMethodName,
            'email': 'supplier-b@example.com',
        })

    def _make_user(self, role, xml_id, extra_groups=None):
        groups = [
            self.env.ref('base.group_user').id,
            self.env.ref('procurement_management.%s' % xml_id).id,
        ]
        for group in extra_groups or []:
            groups.append(group.id)
        return self.env['res.users'].create({
            'name': 'PM %s %s' % (role, self._testMethodName),
            'login': 'pm_%s_%s' % (role, self._testMethodName),
            'email': 'pm_%s_%s@example.com' % (role, self._testMethodName),
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, groups)],
        })

    def _matrix(self, group=None, min_value=0, max_value=0, department=False,
                property_location=False, category=False, sequence=10, mode='sequential',
                required=True, escalation_hours=48, escalation_group=None, levels=None):
        matrix = self.env['procurement.management.approval.matrix'].create({
            'name': 'Matrix %s %s' % (sequence, self._testMethodName),
            'min_value': min_value,
            'max_value': max_value,
            'department': department,
            'property_location': property_location,
            'category': category,
            'sequence': sequence,
        })
        if levels is None:
            levels = [{
                'approver_group_id': (group or self.env.ref(
                    'procurement_management.group_procurement_manager'
                )).id,
                'required_signoff': required,
                'mode': mode,
                'sequence': 10,
                'escalation_hours': escalation_hours,
                'escalation_group_id': escalation_group.id if escalation_group else False,
            }]
        for level in levels:
            level = dict(level, matrix_id=matrix.id)
            self.env['procurement.management.approval.level'].create(level)
        matrix.action_activate()
        return matrix

    def _requisition(self, user=None, department='Facilities', price=50, quantity=2):
        return self.env['procurement.management.requisition'].with_user(user or self.user).create({
            'title': 'Filters',
            'department': department,
            'property_project': 'Tower A',
            'category': 'General',
            'justification': 'Replacement',
            'line_ids': [(0, 0, {
                'description': 'Air filter',
                'quantity': quantity,
                'unit_text': 'ea',
                'price_unit': price,
                'cost_center': 'CC-1',
            })],
        })

    def _approve_requisition(self, requisition):
        requisition.action_submit()
        request = self._pending(requisition, 'requisition')
        request.with_user(self.manager).action_approve('ok')
        return request

    def _pending(self, document, purpose):
        return self.env['procurement.management.approval.request'].search([
            ('res_model', '=', document._name),
            ('res_id', '=', document.id),
            ('purpose', '=', purpose),
            ('state', '=', 'pending'),
        ], limit=1)

    def _order(self, delivery=None, quantity=10, price=10):
        return self.env['procurement.management.purchase.order'].with_user(self.officer).create({
            'partner_id': self.partner.id,
            'department': 'Facilities',
            'property_project': 'Tower A',
            'delivery_date': delivery,
            'line_ids': [(0, 0, {
                'description': 'Goods',
                'quantity': quantity,
                'unit_text': 'ea',
                'price_unit': price,
                'cost_center': 'CC-1',
            })],
        })

    def _approved_order(self, **kwargs):
        self._matrix()
        order = self._order(**kwargs)
        order.action_submit()
        self._pending(order, 'purchase_order').with_user(self.manager).action_approve('ok')
        return order


@tagged('post_install', '-at_install')
class TestProcurementStructureDomain(ProcurementCase):
    def test_models_sequences_rules_and_acl(self):
        for name in BUSINESS_MODELS:
            self.assertIn(name, self.env.registry)
            self.assertFalse(self.env[name]._abstract)
        self.assertTrue(self.env['procurement.management.ui.api']._abstract)
        codes = {
            'procurement.management.requisition': 'REQ-%(year)s-',
            'procurement.management.rfq': 'RFQ-%(year)s-',
            'procurement.management.purchase.order': 'PO-%(year)s-',
            'procurement.management.receipt': 'GR-%(year)s-',
            'procurement.management.invoice.match': 'INV-%(year)s-',
            'procurement.management.contract': 'MSA-%(year)s-',
        }
        for code, prefix in codes.items():
            sequence = self.env['ir.sequence'].search([('code', '=', code)], limit=1)
            self.assertTrue(sequence, code)
            self.assertEqual(sequence.padding, 4)
            self.assertEqual(sequence.prefix, prefix)
        audit_access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'procurement.management.audit.event'),
        ])
        self.assertTrue(audit_access)
        self.assertFalse(any(audit_access.mapped('perm_create')))
        self.assertFalse(any(audit_access.mapped('perm_write')))
        self.assertFalse(any(audit_access.mapped('perm_unlink')))
        decision_access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'procurement.management.approval.decision'),
        ])
        self.assertFalse(any(decision_access.mapped('perm_create')))
        self.assertTrue(self.env.ref('procurement_management.rule_pm_requisition_company'))
        self.assertTrue(self.env.ref('procurement_management.rule_pm_requisition_user'))
        self.assertTrue(self.env.ref('procurement_management.ir_cron_pm_escalate'))
        self.assertTrue(self.env.ref('procurement_management.ir_cron_pm_scheduled_reports'))

    def test_empty_screen_dtos(self):
        api = self.env['procurement.management.ui.api'].with_user(self.user)
        dashboard = api.get_dashboard()
        self.assertEqual(dashboard['recent_orders'], [])
        self.assertEqual(dashboard['priority'], [])
        self.assertEqual(dashboard['total_spend'], 0)
        self.assertEqual(dashboard['pending_requisitions'], 0)
        self.assertEqual(api.get_requisitions(), [])
        self.assertEqual(api.get_rfqs(), [])
        comparison = api.get_comparison()
        self.assertEqual(comparison['rows'], [])
        self.assertFalse(comparison['recommended_quotation_id'])
        self.assertEqual(api.get_purchase_orders(), [])
        self.assertEqual(api.get_goods_receipts(), [])
        self.assertEqual(api.get_invoice_matches(), [])
        self.assertEqual(api.get_suppliers(), [])
        self.assertEqual(api.get_reports(), [])
        builder = api.get_report_builder()
        self.assertEqual(builder['definitions'], [])
        self.assertEqual(builder['formats'], ['csv', 'xlsx', 'pdf'])
        with self.assertRaises(AccessError):
            api.get_approval_matrices()
        with self.assertRaises(AccessError):
            api.get_audit()
        self.assertEqual(
            self.env['procurement.management.ui.api'].with_user(self.manager).get_audit(),
            [],
        )
        self.assertEqual(
            self.env['procurement.management.ui.api'].with_user(self.manager).get_approval_matrices(),
            [],
        )


@tagged('post_install', '-at_install')
class TestRequisitionWorkflow(ProcurementCase):
    def test_requisition_lifecycle_and_conversion(self):
        self._matrix()
        requisition = self._requisition()
        self.assertRegex(requisition.name, r'^REQ-\d{4}-\d{4}$')
        self.assertEqual(requisition.state, 'draft')
        self.assertEqual(requisition.amount_total, 100)
        with self.assertRaises(UserError):
            requisition.write({'state': 'approved'})
        self._approve_requisition(requisition)
        self.assertEqual(requisition.state, 'approved')

        rejected = self._requisition()
        rejected.action_submit()
        self._pending(rejected, 'requisition').with_user(self.manager).action_reject('no')
        self.assertEqual(rejected.state, 'rejected')

        returned = self._requisition()
        returned.action_submit()
        self._pending(returned, 'requisition').with_user(self.manager).action_return('fix')
        self.assertEqual(returned.state, 'returned')
        returned.action_submit()
        self.assertEqual(returned.state, 'pending')

        cancelled = self._requisition()
        cancelled.action_cancel()
        self.assertEqual(cancelled.state, 'cancelled')

        pending = self._requisition()
        pending.action_submit()
        pending.action_cancel()
        self.assertEqual(pending.state, 'cancelled')
        self.assertFalse(self._pending(pending, 'requisition'))

        rfq = requisition.with_user(self.officer).action_convert_rfq()
        self.assertEqual(requisition.state, 'converted')
        self.assertEqual(requisition.converted_model, rfq._name)
        self.assertIn('Air filter', rfq.description)
        self.assertRegex(rfq.name, r'^RFQ-\d{4}-\d{4}$')
        with self.assertRaises(UserError):
            requisition.with_user(self.officer).action_convert_rfq()

        other = self._requisition()
        other.action_submit()
        self._pending(other, 'requisition').with_user(self.manager).action_approve('ok')
        order = other.with_user(self.officer).action_convert_po(self.partner)
        self.assertEqual(other.state, 'converted')
        self.assertEqual(len(order.line_ids), 1)
        self.assertEqual(order.line_ids.description, 'Air filter')
        self.assertEqual(order.amount_total, 100)
        self.assertRegex(order.name, r'^PO-\d{4}-\d{4}$')
        with self.assertRaises(UserError):
            other.with_user(self.officer).action_convert_po(self.partner)
        visible = self.env['procurement.management.purchase.order'].with_user(self.user).search([
            ('id', '=', order.id),
        ])
        self.assertEqual(visible, order)

    def test_requester_cannot_submit_or_convert_someone_else(self):
        self._matrix()
        requisition = self._requisition()
        with self.assertRaises(AccessError):
            requisition.with_user(self.other).read(['name'])
        from odoo.addons.procurement_management.services.requisition_service import RequisitionService
        try:
            RequisitionService(self.env(user=self.other.id)).submit(requisition.sudo())
        except AccessError as error:
            self.assertIn('requester', str(error).lower())
        else:
            self.fail('A different user must not submit the requisition.')
        denied = self.env['procurement.management.audit.event'].search([
            ('reference', '=', requisition.name),
            ('status', '=', 'denied'),
        ])
        self.assertTrue(denied)
        self.assertEqual(requisition.state, 'draft')
        requisition.action_submit()
        self._pending(requisition, 'requisition').with_user(self.manager).action_approve('ok')
        with self.assertRaises(AccessError):
            requisition.with_user(self.user).action_convert_rfq()


@tagged('post_install', '-at_install')
class TestRfqQuotation(ProcurementCase):
    def test_rfq_responses_evaluation_and_close(self):
        rfq = self.env['procurement.management.rfq'].with_user(self.officer).create({
            'description': 'Filters',
            'estimated_value': 100,
            'supplier_ids': [
                (0, 0, {'partner_id': self.partner.id}),
                (0, 0, {'partner_id': self.partner_b.id}),
            ],
        })
        self.assertEqual(rfq.commercial_weight, 40)
        self.assertEqual(rfq.technical_weight, 60)
        self.assertEqual(rfq.response_count, 0)
        with self.assertRaises(ValidationError):
            rfq.write({'commercial_weight': 10, 'technical_weight': 10})
        rfq.action_issue()
        self.assertEqual(rfq.state, 'issued')
        self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq.id,
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'description': 'Air filter',
                'quantity': 2,
                'unit_text': 'ea',
                'price_unit': 40,
            })],
        })
        self.assertEqual(rfq.response_count, 1)
        self.assertEqual(rfq.state, 'partially_responded')
        self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq.id,
            'partner_id': self.partner_b.id,
            'line_ids': [(0, 0, {
                'description': 'Air filter',
                'quantity': 2,
                'unit_text': 'ea',
                'price_unit': 30,
            })],
        })
        self.assertEqual(rfq.state, 'supplier_responded')
        rfq.action_start_evaluation()
        self.assertEqual(rfq.state, 'under_evaluation')
        rfq.action_close()
        self.assertEqual(rfq.state, 'closed')
        with self.assertRaises(UserError):
            rfq.write({'description': 'changed'})

        draft = self.env['procurement.management.rfq'].with_user(self.officer).create({
            'description': 'Cancel me',
        })
        draft.action_cancel()
        self.assertEqual(draft.state, 'cancelled')

    def test_scoring_recommendation_and_selection(self):
        self._matrix()
        rfq = self.env['procurement.management.rfq'].with_user(self.officer).create({
            'department': 'Facilities',
            'property_project': 'Tower A',
            'category': 'General',
            'supplier_ids': [
                (0, 0, {'partner_id': self.partner.id}),
                (0, 0, {'partner_id': self.partner_b.id}),
            ],
        })
        rfq.action_issue()
        expensive = self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq.id,
            'partner_id': self.partner.id,
            'commercial_score': 8,
            'technical_score': 4,
            'freight_amount': 20,
            'line_ids': [(0, 0, {
                'description': 'Option A',
                'quantity': 1,
                'unit_text': 'ea',
                'price_unit': 100,
            })],
        })
        cheaper = self.env['procurement.management.quotation'].with_user(self.officer).create({
            'rfq_id': rfq.id,
            'partner_id': self.partner_b.id,
            'commercial_score': 5,
            'technical_score': 5,
            'line_ids': [(0, 0, {
                'description': 'Option B',
                'quantity': 1,
                'unit_text': 'ea',
                'price_unit': 110,
            })],
        })
        self.assertAlmostEqual(expensive.weighted_score, 5.6)
        self.assertEqual(expensive.amount_total, 120)
        self.assertEqual(cheaper.amount_total, 110)
        rfq.action_start_evaluation()
        service = ComparisonService(self.env)
        self.assertEqual(service.recommend(rfq), cheaper)
        service.update_weights(rfq, 50, 50)
        self.assertAlmostEqual(expensive.weighted_score, 6.0)
        dto = self.env['procurement.management.ui.api'].with_user(self.officer).get_comparison(rfq.id)
        self.assertEqual(dto['recommended_quotation_id'], cheaper.id)
        self.assertEqual(len(dto['rows']), 2)
        request = service.select_supplier(cheaper)
        self.assertEqual(request.state, 'pending')
        self.assertEqual(rfq.selection_status, 'pending')
        self.assertNotEqual(cheaper.state, 'selected')
        request.with_user(self.manager).action_approve('selected')
        self.assertEqual(cheaper.state, 'selected')
        self.assertEqual(rfq.selection_status, 'effective')
        self.assertEqual(rfq.selected_quotation_id, cheaper)


@tagged('post_install', '-at_install')
class TestApprovalRuntime(ProcurementCase):
    def test_matrix_matching_specificity_sequence_and_id(self):
        broad = self._matrix(sequence=5)
        specific = self._matrix(sequence=20, department=' Facilities ')
        earlier = self._matrix(sequence=5, department='facilities')
        service = ApprovalService(self.env)
        matched = service.match(self.env.company, 100, 'facilities', 'Tower A', 'General')
        self.assertEqual(matched, earlier)
        self.assertNotEqual(matched, broad)
        self.assertNotEqual(matched, specific)
        other = service.match(self.env.company, 100, 'Other', '', '')
        self.assertEqual(other, broad)
        capped = self._matrix(sequence=1, max_value=50, department='Capped')
        self.assertNotEqual(service.match(self.env.company, 80, 'Capped', '', ''), capped)
        first = self._matrix(sequence=40, department='TieDept')
        second = self._matrix(sequence=40, department='TieDept')
        self.assertEqual(service.match(self.env.company, 100, 'TieDept', '', ''), first)
        self.assertNotEqual(second, first)

    def test_no_matrix_rejects_the_action(self):
        requisition = self._requisition()
        try:
            requisition.action_submit()
        except UserError as error:
            self.assertIn('matrix', str(error).lower())
        else:
            self.fail('A missing approval matrix must reject the action.')
        self.assertEqual(requisition.state, 'draft')
        denied = self.env['procurement.management.audit.event'].search([
            ('reference', '=', requisition.display_name),
            ('status', '=', 'denied'),
        ])
        self.assertTrue(denied)

    def test_sequential_parallel_signoff_and_escalation(self):
        second_group = self.env['res.groups'].create({'name': 'PM Second %s' % self._testMethodName})
        second_user = self._make_user('second', 'group_procurement_officer', extra_groups=[second_group])
        sequential = self._matrix(levels=[
            {
                'sequence': 10,
                'approver_group_id': self.env.ref('procurement_management.group_procurement_manager').id,
                'required_signoff': True,
                'mode': 'sequential',
                'escalation_hours': 48,
            },
            {
                'sequence': 20,
                'approver_group_id': second_group.id,
                'required_signoff': True,
                'mode': 'sequential',
                'escalation_hours': 48,
            },
        ])
        requisition = self._requisition()
        requisition.action_submit()
        request = self._pending(requisition, 'requisition')
        self.assertEqual(request.matrix_id, sequential)
        with self.assertRaises(AccessError):
            request.with_user(second_user).action_approve('too soon')
        request.with_user(self.manager).action_approve('first')
        self.assertEqual(request.state, 'pending')
        self.assertEqual(requisition.state, 'pending')
        request.with_user(second_user).action_approve('second')
        self.assertEqual(request.state, 'approved')
        self.assertEqual(requisition.state, 'approved')

        parallel = self._matrix(sequence=1, mode='parallel', levels=[
            {
                'sequence': 10,
                'approver_group_id': self.env.ref('procurement_management.group_procurement_manager').id,
                'required_signoff': True,
                'mode': 'parallel',
                'escalation_hours': 48,
            },
            {
                'sequence': 20,
                'approver_group_id': second_group.id,
                'required_signoff': True,
                'mode': 'parallel',
                'escalation_hours': 48,
            },
        ])
        parallel_req = self._requisition(department='Parallel')
        # Force this document onto the parallel matrix by deactivating the sequential one.
        sequential.action_deactivate()
        parallel_req.action_submit()
        parallel_request = self._pending(parallel_req, 'requisition')
        self.assertEqual(parallel_request.matrix_id, parallel)
        parallel_request.with_user(self.manager).action_approve('one')
        self.assertEqual(parallel_request.state, 'pending')
        parallel_request.with_user(second_user).action_approve('two')
        self.assertEqual(parallel_req.state, 'approved')

        parallel.action_deactivate()
        self._matrix(sequence=1, required=False)
        skipped = self._requisition(department='Skipped')
        skipped.action_submit()
        self.assertEqual(skipped.state, 'approved')

        self.env['procurement.management.approval.matrix'].search([
            ('state', '=', 'active'),
        ]).action_deactivate()
        escalation_group = self.env['res.groups'].create({
            'name': 'PM Escalate %s' % self._testMethodName,
        })
        self._matrix(escalation_hours=0, escalation_group=escalation_group)
        waiting = self._requisition(department='Escalate')
        waiting.action_submit()
        waiting_request = self._pending(waiting, 'requisition')
        first_decision = waiting_request.decision_ids
        self.assertEqual(first_decision.hop, 0)
        self.env['procurement.management.approval.decision']._cron_escalate()
        self.assertEqual(first_decision.decision, 'escalated')
        hopped = waiting_request.decision_ids.filtered(lambda row: row.hop == 1)
        self.assertEqual(len(hopped), 1)
        self.assertEqual(hopped.group_id, escalation_group)
        self.assertEqual(hopped.decision, 'pending')
        self.env['procurement.management.approval.decision']._cron_escalate()
        self.assertEqual(len(waiting_request.decision_ids.filtered(lambda row: row.hop == 1)), 1)
        self.assertTrue(self.env['procurement.management.audit.event'].search([
            ('reference', '=', waiting_request.name),
            ('after_value', '=', 'escalated'),
        ]))

    def test_self_approval_stays_configurable(self):
        param = self.env['ir.config_parameter'].sudo()
        self._matrix()
        requisition = self._requisition(user=self.manager)
        requisition.action_submit()
        request = self._pending(requisition, 'requisition')
        param.set_param('procurement_management.self_approval', 'A')
        try:
            request.with_user(self.manager).action_approve('self')
        except AccessError as error:
            self.assertIn('cannot approve', str(error).lower())
        else:
            self.fail('Policy A must block self-approval.')
        self.assertEqual(requisition.state, 'pending')
        self.assertTrue(self.env['procurement.management.audit.event'].search([
            ('reference', '=', request.name),
            ('status', '=', 'denied'),
        ]))
        param.set_param('procurement_management.self_approval', 'B')
        request.with_user(self.manager).action_approve('self')
        self.assertEqual(requisition.state, 'approved')
        param.set_param('procurement_management.self_approval', 'C')
        another = self._requisition(user=self.manager)
        another.action_submit()
        with self.assertRaises(UserError):
            self._pending(another, 'requisition').with_user(self.manager).action_approve('bad')


@tagged('post_install', '-at_install')
class TestPurchaseReceiptInvoice(ProcurementCase):
    def test_purchase_order_workflow_partial_and_overdue(self):
        today = fields.Date.context_today(self.env.user)
        order = self._approved_order(delivery=today + timedelta(days=2))
        self.assertEqual(order.state, 'approved')
        with self.assertRaises(UserError):
            self._order().action_issue()
        order.line_ids.write({'price_unit': 12})
        self.assertEqual(order.state, 'pending')
        with self.assertRaises(UserError):
            order.action_issue()
        self._pending(order, 'purchase_order').with_user(self.manager).action_approve('amended')
        self.assertEqual(order.state, 'approved')
        order.action_issue()
        self.assertEqual(order.state, 'issued')
        self.assertEqual(order.receipt_ids.state, 'expected')
        self.assertRegex(order.receipt_ids.name, r'^GR-\d{4}-\d{4}$')
        order.action_acknowledge()
        self.assertEqual(order.state, 'acknowledged')
        self.assertEqual(order.acknowledged_by_id, self.officer)
        self.assertTrue(order.acknowledged_on)
        order.action_close()
        self.assertEqual(order.state, 'closed')
        self.assertEqual(order.closed_by_id, self.officer)
        self.assertEqual(order.display_status, 'closed')

        partial = self._approved_order(delivery=today + timedelta(days=3), quantity=10, price=5)
        partial.action_issue()
        receipt = partial.receipt_ids
        receipt.action_confirm({receipt.line_ids.id: 4})
        receipt.action_inspect('pass', 'short')
        self.assertEqual(receipt.state, 'completed')
        remainder = partial.receipt_ids.filtered(lambda item: item.state == 'expected')
        self.assertEqual(len(remainder), 1)
        self.assertEqual(remainder.line_ids.ordered_qty, 6)
        self.assertEqual(partial.state, 'issued')
        self.assertEqual(partial.display_status, 'partial')

        overdue = self._approved_order(delivery=today - timedelta(days=1), quantity=10, price=5)
        overdue.action_issue()
        self.assertEqual(overdue.state, 'issued')
        self.assertEqual(overdue.display_status, 'overdue')

    def test_receipt_over_hold_and_reject(self):
        today = fields.Date.context_today(self.env.user)
        order = self._approved_order(delivery=today + timedelta(days=1), quantity=10, price=1)
        order.action_issue()
        receipt = order.receipt_ids
        receipt.action_start()
        self.assertEqual(receipt.state, 'receiving')
        with self.assertRaises(UserError):
            receipt.action_confirm({receipt.line_ids.id: 11})
        self.assertEqual(receipt.line_ids.received_qty, 0)

        held = self._approved_order(delivery=today + timedelta(days=1), quantity=2, price=1)
        held.action_issue()
        held_receipt = held.receipt_ids
        held_receipt.action_confirm({held_receipt.line_ids.id: 2})
        held_receipt.action_inspect('hold_qa', 'check')
        self.assertEqual(held_receipt.state, 'inspection')
        self.assertEqual(held_receipt.inspection_result, 'hold_qa')
        self.assertEqual(len(held.receipt_ids), 1)

        rejected = self._approved_order(delivery=today + timedelta(days=1), quantity=2, price=1)
        rejected.action_issue()
        rejected_receipt = rejected.receipt_ids
        rejected_receipt.action_confirm({rejected_receipt.line_ids.id: 2})
        rejected_receipt.action_inspect('reject', 'damaged')
        self.assertEqual(rejected_receipt.state, 'completed')
        self.assertEqual(rejected_receipt.inspection_result, 'reject')
        self.assertEqual(len(rejected.receipt_ids), 1)

    def test_invoice_match_duplicate_and_resolution(self):
        order = self._order(quantity=10, price=5)
        clean = self.env['procurement.management.invoice.match'].with_user(self.officer).create({
            'supplier_invoice_number': 'INV-100',
            'partner_id': self.partner.id,
            'order_id': order.id,
            'company_id': order.company_id.id,
            'invoice_amount': 50,
            'line_ids': [(0, 0, {
                'description': 'Goods',
                'order_line_id': order.line_ids.id,
                'po_qty': 10,
                'receipt_qty': 10,
                'invoice_qty': 10,
                'po_price': 5,
                'invoice_price': 5,
            })],
        })
        self.assertRegex(clean.name, r'^INV-\d{4}-\d{4}$')
        self.assertEqual(clean.matched_amount, 50)
        self.assertEqual(clean.amount_variance, 0)
        self.assertEqual(clean.line_ids.variance_qty, 0)
        clean.with_user(self.manager).action_approve()
        self.assertEqual(clean.state, 'matched')
        try:
            self.env['procurement.management.invoice.match'].with_user(self.officer).create({
                'supplier_invoice_number': 'INV-100',
                'partner_id': self.partner.id,
                'order_id': order.id,
                'company_id': order.company_id.id,
                'invoice_amount': 50,
            })
        except UserError as error:
            self.assertIn('already recorded', str(error).lower())
        else:
            self.fail('A duplicate supplier invoice must be refused.')
        denied = self.env['procurement.management.audit.event'].search([
            ('reference', '=', 'INV-100'),
            ('status', '=', 'denied'),
        ])
        self.assertTrue(denied)

        mismatch = self.env['procurement.management.invoice.match'].with_user(self.officer).create({
            'supplier_invoice_number': 'INV-200',
            'partner_id': self.partner.id,
            'order_id': order.id,
            'company_id': order.company_id.id,
            'invoice_amount': 40,
            'line_ids': [(0, 0, {
                'description': 'Goods',
                'po_qty': 10,
                'receipt_qty': 10,
                'invoice_qty': 8,
                'po_price': 5,
                'invoice_price': 5,
            })],
        })
        mismatch.action_auto_match()
        self.assertEqual(mismatch.state, 'mismatch')
        self.assertTrue(mismatch.exception_reason)
        mismatch.with_user(self.officer).action_resolve('Accepted the shortage note.')
        self.assertEqual(mismatch.resolution, 'resolved')
        self.assertIn('shortage', mismatch.resolution_note)

        rejected = self.env['procurement.management.invoice.match'].with_user(self.officer).create({
            'supplier_invoice_number': 'INV-300',
            'partner_id': self.partner.id,
            'order_id': order.id,
            'company_id': order.company_id.id,
            'invoice_amount': 99,
            'line_ids': [(0, 0, {
                'description': 'Goods',
                'po_qty': 10,
                'receipt_qty': 10,
                'invoice_qty': 10,
                'po_price': 5,
                'invoice_price': 9,
            })],
        })
        rejected.action_auto_match()
        rejected.with_user(self.manager).action_reject('Not acceptable')
        self.assertEqual(rejected.state, 'under_review')
        self.assertEqual(rejected.resolution, 'rejected')


@tagged('post_install', '-at_install')
class TestSupplierReportsAudit(ProcurementCase):
    def test_supplier_profile_and_contract(self):
        profile = self.env['procurement.management.supplier.profile'].with_user(self.officer).create({
            'partner_id': self.partner.id,
            'vendor_code': 'V-1',
            'category': 'MRO',
            'score': 80,
        })
        self.assertEqual(profile.state, 'active')
        with self.assertRaises(ValidationError):
            self.env['procurement.management.supplier.profile'].with_user(self.officer).create({
                'partner_id': self.partner.id,
                'vendor_code': 'V-2',
            })
        from odoo.addons.procurement_management.services.supplier_service import SupplierService
        supplier_service = SupplierService(self.env(user=self.officer.id))
        supplier_service.set_status(profile, 'preferred')
        self.assertTrue(profile.preferred)
        supplier_service.set_status(profile, 'suspended')
        self.assertFalse(profile.preferred)
        contact = supplier_service.add_contact(profile, 'Buyer Desk', email='desk@example.com')
        self.assertEqual(contact.parent_id, self.partner)
        contract = self.env['procurement.management.contract'].with_user(self.officer).create({
            'name': 'Master agreement',
            'profile_id': profile.id,
            'date_start': fields.Date.context_today(self.env.user),
            'notes': 'MSA',
        })
        self.assertRegex(contract.reference, r'^MSA-\d{4}-\d{4}$')
        with self.assertRaises(ValidationError):
            contract.write({
                'date_start': fields.Date.context_today(self.env.user),
                'date_end': fields.Date.context_today(self.env.user) - timedelta(days=1),
            })
        other_company = self.env['res.company'].create({'name': 'PM Contract Co %s' % self._testMethodName})
        with self.assertRaises(ValidationError):
            contract.write({'company_id': other_company.id})

    def test_reports_exports_and_schedule(self):
        definition = self.env['procurement.management.report.definition'].with_user(self.manager).create({
            'name': 'Requisition list',
            'report_type': 'requisitions',
            'department': 'Facilities',
            'status': 'draft',
        })
        self._requisition(department='Facilities')
        self._requisition(department='Security')
        preview = definition.action_preview()
        self.assertEqual(preview['columns'][0], 'Reference')
        self.assertEqual(len(preview['rows']), 1)
        with self.assertRaises(ValidationError):
            definition.write({
                'date_from': fields.Date.context_today(self.env.user),
                'date_to': fields.Date.context_today(self.env.user) - timedelta(days=2),
            })
        csv_result = definition.action_export('csv')
        self.assertTrue(csv_result['ok'])
        csv_run = self.env['procurement.management.report.run'].browse(csv_result['run_id'])
        self.assertEqual(csv_run.state, 'exported')
        csv_raw = base64.b64decode(csv_run.attachment_id.datas)
        self.assertIn(b'Reference', csv_raw)
        self.assertFalse(csv_run.attachment_id.public)
        xlsx_result = definition.action_export('xlsx')
        xlsx_run = self.env['procurement.management.report.run'].browse(xlsx_result['run_id'])
        self.assertTrue(base64.b64decode(xlsx_run.attachment_id.datas).startswith(b'PK'))
        pdf_result = definition.action_export('pdf')
        pdf_run = self.env['procurement.management.report.run'].browse(pdf_result['run_id'])
        if pdf_result['ok']:
            self.assertTrue(base64.b64decode(pdf_run.attachment_id.datas).startswith(b'%PDF'))
            self.assertEqual(pdf_run.state, 'exported')
            self.assertFalse(pdf_run.attachment_id.public)
        else:
            self.assertIn('unavailable', (pdf_result.get('error') or '').lower())
            self.assertEqual(pdf_run.state, 'failed')

        today = fields.Date.context_today(self.env.user)
        scheduled = self.env['procurement.management.report.definition'].with_user(self.manager).create({
            'name': 'Weekly spend',
            'report_type': 'spend',
            'schedule': 'weekly',
            'weekday': today.weekday(),
            'recipient_emails': 'reports@example.com',
        })
        missing = self.env['procurement.management.report.definition'].with_user(self.manager).create({
            'name': 'Weekly missing',
            'report_type': 'spend',
            'schedule': 'weekly',
            'weekday': today.weekday(),
        })
        self.assertTrue(self.env.ref('procurement_management.mail_template_pm_report'))
        self.env['procurement.management.report.definition']._cron_send_scheduled()
        scheduled.invalidate_recordset()
        details = [(run.state, run.error_detail) for run in scheduled.run_ids]
        self.assertEqual(scheduled.last_run_on, today, details)
        self.assertTrue(self.env['mail.mail'].search([
            ('subject', '=', 'Procurement scheduled report'),
        ], limit=1))
        failed = missing.run_ids.filtered(lambda run: run.state == 'failed')
        self.assertTrue(failed)
        self.assertIn('recipients', failed[:1].error_detail)

    def test_metrics_grouping_sorting_affect_preview(self):
        low = self._requisition(department='Facilities', price=10, quantity=1)
        mid = self._requisition(department='Facilities', price=30, quantity=1)
        high = self._requisition(department='Security', price=50, quantity=1)
        Report = self.env['procurement.management.report.definition'].with_user(self.manager)
        plain = Report.create({
            'name': 'Plain requisitions',
            'report_type': 'requisitions',
        })
        base = plain.action_preview()
        self.assertEqual(base['columns'], ['Reference', 'Partner', 'Amount', 'Status', 'Date'])
        self.assertEqual(len(base['rows']), 3)
        base_amounts = [row[2] for row in base['rows']]

        metrics = Report.create({
            'name': 'Amount metric',
            'report_type': 'requisitions',
            'metrics': 'amount',
        }).action_preview()
        self.assertEqual(metrics['columns'], ['Reference', 'Amount'])
        self.assertIn('Amount', metrics['columns'])
        self.assertNotEqual(metrics['columns'], base['columns'])
        self.assertEqual([row[-1] for row in metrics['rows']], base_amounts)

        grouped = Report.create({
            'name': 'By department',
            'report_type': 'requisitions',
            'group_by': 'department',
        }).action_preview()
        self.assertEqual(grouped['columns'][0], 'Department')
        self.assertIn('Amount', grouped['columns'])
        self.assertEqual(len(grouped['rows']), 2)
        amount_index = grouped['columns'].index('Amount')
        grouped_amounts = {row[0]: row[amount_index] for row in grouped['rows']}
        self.assertAlmostEqual(grouped_amounts['Facilities'], low.amount_total + mid.amount_total)
        self.assertAlmostEqual(grouped_amounts['Security'], high.amount_total)
        self.assertNotEqual(grouped['rows'], base['rows'])

        ordered = Report.create({
            'name': 'Sorted by amount',
            'report_type': 'requisitions',
            'sort_by': 'amount',
        }).action_preview()
        self.assertEqual(ordered['columns'], base['columns'])
        ordered_amounts = [row[2] for row in ordered['rows']]
        self.assertEqual(ordered_amounts, sorted(base_amounts))
        self.assertNotEqual(ordered_amounts, base_amounts)

        combined = Report.create({
            'name': 'Amount by department',
            'report_type': 'requisitions',
            'metrics': 'amount',
            'group_by': 'department',
            'sort_by': 'amount',
        }).action_preview()
        self.assertEqual(combined['columns'], ['Department', 'Amount'])
        self.assertEqual(len(combined['rows']), 2)
        self.assertEqual(
            [row[0] for row in combined['rows']],
            ['Facilities', 'Security'],
        )
        self.assertAlmostEqual(combined['rows'][0][1], low.amount_total + mid.amount_total)
        self.assertAlmostEqual(combined['rows'][1][1], high.amount_total)
        self.assertNotEqual(combined['columns'], base['columns'])
        self.assertNotEqual(combined['rows'], base['rows'])

    def test_audit_append_only_and_authorized_export(self):
        requisition = self._requisition()
        created = self.env['procurement.management.audit.event'].search([
            ('res_model', '=', requisition._name),
            ('reference', '=', requisition.name),
            ('action', '=', 'created'),
            ('status', '=', 'success'),
        ])
        self.assertTrue(created)
        requisition.write({'title': 'Updated filters'})
        modified = self.env['procurement.management.audit.event'].search([
            ('reference', '=', requisition.name),
            ('action', '=', 'modified'),
        ], limit=1)
        self.assertEqual(modified.before_value, 'draft')
        self.assertEqual(modified.after_value, 'draft')
        event = created[:1]
        with self.assertRaises(UserError):
            event.write({'detail': 'changed'})
        with self.assertRaises(UserError):
            event.unlink()
        with self.assertRaises(UserError):
            event.sudo().write({'detail': 'changed'})
        with self.assertRaises(AccessError):
            self.env['procurement.management.audit.event'].with_user(self.manager).create({
                'user_id': self.manager.id,
                'company_id': self.env.company.id,
                'action': 'created',
            })
        with self.assertRaises(UserError):
            self.env['procurement.management.audit.event'].sudo().create({
                'user_id': self.env.user.id,
                'company_id': self.env.company.id,
                'action': 'synced',
            })
        exported = AuditService(self.env(user=self.manager.id)).export_csv()
        self.assertIn('created', exported)
        with self.assertRaises(AccessError):
            AuditService(self.env(user=self.user.id)).export_csv()
        attachment = self.env['ir.attachment'].with_user(self.user).create({
            'name': 'justification.txt',
            'datas': base64.b64encode(b'needed'),
            'res_model': requisition._name,
            'res_id': requisition.id,
            'public': False,
        })
        self.assertFalse(attachment.public)
        self.assertIn(attachment, requisition.attachment_ids)


@tagged('post_install', '-at_install')
class TestSecurityIsolation(ProcurementCase):
    def test_groups_company_and_requester_isolation(self):
        with self.assertRaises(AccessError):
            self.env['procurement.management.purchase.order'].with_user(self.user).create({
                'partner_id': self.partner.id,
            })
        order = self._order()
        self.assertTrue(order)
        with self.assertRaises(AccessError):
            self.env['procurement.management.approval.matrix'].with_user(self.officer).search([])
        matrix = self.env['procurement.management.approval.matrix'].with_user(self.manager).create({
            'name': 'Visible',
        })
        self.assertEqual(matrix.state, 'draft')
        with self.assertRaises(AccessError):
            self.env['procurement.management.audit.event'].with_user(self.user).search([])
        with self.assertRaises(AccessError):
            self.env['procurement.management.approval.request'].with_user(self.manager).create({
                'name': 'Manual',
                'company_id': self.env.company.id,
                'res_model': 'procurement.management.requisition',
                'res_id': 1,
                'purpose': 'requisition',
                'matrix_id': matrix.id,
            })

        company = self.env['res.company'].create({'name': 'PM Other %s' % self._testMethodName})
        foreign = self.env['procurement.management.requisition'].with_company(company).create({
            'title': 'Foreign',
            'company_id': company.id,
            'requester_id': self.user.id,
            'line_ids': [(0, 0, {
                'description': 'Hidden',
                'quantity': 1,
                'price_unit': 1,
            })],
        })
        self.assertFalse(self.env['procurement.management.requisition'].with_user(self.user).search([
            ('id', '=', foreign.id),
        ]))
        own = self._requisition()
        self.assertFalse(self.env['procurement.management.requisition'].with_user(self.other).search([
            ('id', '=', own.id),
        ]))
        with self.assertRaises(AccessError):
            own.with_user(self.other).read(['name'])
        self._matrix()
        own.action_submit()
        self.assertTrue(self.env['mail.mail'].search([
            ('subject', '=', 'Procurement approval requested'),
        ], limit=1))
        self.assertNotIn('purchase', self.env['ir.module.module'].search([
            ('name', '=', 'procurement_management'),
        ]).dependencies_id.mapped('name'))
