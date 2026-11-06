# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .approval_service import ApprovalService
from .common import audit_record, has_group


class PurchaseOrderService:
    def __init__(self, env):
        self.env = env

    def _officer(self):
        if not has_group(self.env, 'group_procurement_officer'):
            raise UserError('Only a procurement officer can process a purchase order.')

    def create_from_quotation(self, quotation):
        quotation.ensure_one()
        existing = self.env['procurement.management.purchase.order'].search([
            ('quotation_id', '=', quotation.id),
            ('company_id', '=', quotation.company_id.id),
            ('state', '!=', 'cancelled'),
        ], limit=1)
        if existing:
            return existing
        rfq = quotation.rfq_id
        requisition = rfq.requisition_id
        return self.env['procurement.management.purchase.order'].create({
            'partner_id': quotation.partner_id.id,
            'company_id': quotation.company_id.id,
            'requisition_id': requisition.id or False,
            'rfq_id': rfq.id,
            'quotation_id': quotation.id,
            'department': rfq.department,
            'property_project': rfq.property_project,
            'category': rfq.category,
            'delivery_date': rfq.deadline,
            'line_ids': [(0, 0, {
                'description': line.description,
                'quantity': line.quantity,
                'unit_text': line.unit_text,
                'price_unit': line.price_unit,
                'cost_center': requisition.cost_center or False,
            }) for line in quotation.line_ids],
        })

    def submit(self, orders):
        approvals = ApprovalService(self.env)
        for order in orders:
            self._officer()
            if order.state != 'draft':
                raise UserError('Only a draft purchase order can be submitted.')
            if not order.line_ids:
                raise UserError('Add at least one purchase order line.')
            before = order.state
            request = approvals.start(
                order, 'purchase_order', order.amount_total,
                order.department, order.property_project, order.category,
            )
            if request.state == 'pending':
                order._set_state('pending')
            audit_record(order, 'modified', before=before, after=order.state, detail='Submitted.')
        return True

    def issue(self, orders):
        for order in orders:
            self._officer()
            if order.state != 'approved':
                raise UserError('A purchase order cannot be issued before it is approved.')
            before = order.state
            order._set_state('issued')
            self.env['procurement.management.receipt'].create({
                'order_id': order.id,
                'partner_id': order.partner_id.id,
                'company_id': order.company_id.id,
                'state': 'expected',
                'line_ids': [(0, 0, {
                    'order_line_id': line.id,
                    'description': line.description,
                    'ordered_qty': line.quantity,
                    'received_qty': 0.0,
                }) for line in order.line_ids],
            })
            audit_record(order, 'modified', before=before, after='issued', detail='Issued.')
        return True

    def acknowledge(self, orders):
        for order in orders:
            self._officer()
            if order.state != 'issued':
                raise UserError('Only an issued purchase order can be acknowledged.')
            order.with_context(pm_state_write=True).write({
                'state': 'acknowledged',
                'acknowledged_by_id': self.env.user.id,
                'acknowledged_on': fields.Datetime.now(),
            })
            audit_record(order, 'modified', before='issued', after='acknowledged')
        return True

    def close(self, orders):
        for order in orders:
            self._officer()
            if order.state not in ('issued', 'acknowledged'):
                raise UserError('Only an issued or acknowledged purchase order can be closed.')
            before = order.state
            order.with_context(pm_state_write=True).write({
                'state': 'closed',
                'closed_by_id': self.env.user.id,
                'closed_on': fields.Datetime.now(),
            })
            audit_record(order, 'modified', before=before, after='closed')
        return True

    def cancel(self, orders):
        for order in orders:
            self._officer()
            if order.state not in ('draft', 'pending'):
                raise UserError('This purchase order cannot be cancelled.')
            before = order.state
            order._set_state('cancelled')
            pending = ApprovalService(self.env).open_request(order, 'purchase_order')
            if pending:
                pending._set_state('cancelled')
            audit_record(order, 'modified', before=before, after='cancelled')
        return True
