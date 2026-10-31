# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.common import guard_state, set_state, today


class ProcurementPurchaseOrder(models.Model):
    _name = 'procurement.management.purchase.order'
    _description = 'Procurement Purchase Order'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    requisition_id = fields.Many2one('procurement.management.requisition', index=True)
    rfq_id = fields.Many2one('procurement.management.rfq', index=True)
    quotation_id = fields.Many2one('procurement.management.quotation', index=True)
    department = fields.Char(index=True)
    property_project = fields.Char(index=True)
    category = fields.Char(index=True)
    delivery_date = fields.Date()
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('issued', 'Issued'),
            ('acknowledged', 'Acknowledged'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='draft',
        index=True,
    )
    display_status = fields.Char(compute='_compute_display_status')
    line_ids = fields.One2many('procurement.management.purchase.order.line', 'order_id', copy=True)
    receipt_ids = fields.One2many('procurement.management.receipt', 'order_id')
    invoice_ids = fields.One2many('procurement.management.invoice.match', 'order_id')
    amount_total = fields.Monetary(compute='_compute_amount_total', store=True, currency_field='currency_id')
    acknowledged_by_id = fields.Many2one('res.users', copy=False)
    acknowledged_on = fields.Datetime(copy=False)
    closed_by_id = fields.Many2one('res.users', copy=False)
    closed_on = fields.Datetime(copy=False)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.purchase.order')],
    )

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_subtotal'))

    @api.depends(
        'state', 'delivery_date', 'line_ids.quantity',
        'receipt_ids.state', 'receipt_ids.inspection_result', 'receipt_ids.line_ids.received_qty',
    )
    def _compute_display_status(self):
        current = today(self.env)
        for order in self:
            if order.state in ('issued', 'acknowledged') and order._is_overdue(current):
                order.display_status = 'overdue'
            elif order.state in ('issued', 'acknowledged') and order._is_partial():
                order.display_status = 'partial'
            else:
                order.display_status = order.state

    def _accepted_qty(self, line):
        qty = 0.0
        for receipt in self.receipt_ids.filtered(
            lambda item: item.state == 'completed' and item.inspection_result == 'pass'
        ):
            qty += sum(receipt.line_ids.filtered(
                lambda row: row.order_line_id == line
            ).mapped('received_qty'))
        return qty

    def _is_partial(self):
        self.ensure_one()
        accepted = [self._accepted_qty(line) for line in self.line_ids]
        if not accepted:
            return False
        any_received = any(qty > 0 for qty in accepted)
        complete = all(
            self.currency_id.round(got - line.quantity) >= 0
            for got, line in zip(accepted, self.line_ids)
        ) if self.currency_id else all(got >= line.quantity for got, line in zip(accepted, self.line_ids))
        return any_received and not complete

    @api.constrains('company_id', 'requisition_id', 'rfq_id', 'quotation_id')
    def _check_company_links(self):
        for order in self:
            if order.requisition_id and order.company_id != order.requisition_id.company_id:
                raise ValidationError('The purchase order company must match the requisition company.')
            if order.rfq_id and order.company_id != order.rfq_id.company_id:
                raise ValidationError('The purchase order company must match the RFQ company.')
            if order.quotation_id and order.company_id != order.quotation_id.company_id:
                raise ValidationError('The purchase order company must match the quotation company.')

    def _is_overdue(self, current):
        self.ensure_one()
        if not self.delivery_date or self.delivery_date >= current:
            return False
        if not self.line_ids:
            return True
        return any(self._accepted_qty(line) < line.quantity for line in self.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.purchase.order'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state)
        return records

    def write(self, vals):
        guard_state(self, vals)
        return super().write(vals)

    def unlink(self):
        for order in self:
            if order.state != 'draft':
                raise UserError('Only a draft purchase order can be deleted.')
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def _return_to_pending_for_amendment(self):
        from ..services.approval_service import ApprovalService
        from ..services.common import audit_record
        approvals = ApprovalService(self.env)
        for order in self.filtered(lambda item: item.state in ('approved', 'issued', 'acknowledged')):
            before = order.state
            order._set_state('pending')
            if not approvals.open_request(order, 'purchase_order'):
                approvals.start(
                    order, 'purchase_order', order.amount_total,
                    order.department, order.property_project, order.category,
                )
            audit_record(order, 'modified', before=before, after='pending', detail='Amendment requires approval again.')

    def action_submit(self):
        from ..services.purchase_order_service import PurchaseOrderService
        return PurchaseOrderService(self.env).submit(self)

    def action_issue(self):
        from ..services.purchase_order_service import PurchaseOrderService
        return PurchaseOrderService(self.env).issue(self)

    def action_acknowledge(self):
        from ..services.purchase_order_service import PurchaseOrderService
        return PurchaseOrderService(self.env).acknowledge(self)

    def action_close(self):
        from ..services.purchase_order_service import PurchaseOrderService
        return PurchaseOrderService(self.env).close(self)

    def action_cancel(self):
        from ..services.purchase_order_service import PurchaseOrderService
        return PurchaseOrderService(self.env).cancel(self)


class ProcurementPurchaseOrderLine(models.Model):
    _name = 'procurement.management.purchase.order.line'
    _description = 'Procurement Purchase Order Line'
    _order = 'id'

    order_id = fields.Many2one(
        'procurement.management.purchase.order', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True)
    description = fields.Char(required=True)
    quantity = fields.Float(required=True, default=1.0)
    unit_text = fields.Char()
    price_unit = fields.Monetary(currency_field='currency_id')
    cost_center = fields.Char()
    price_subtotal = fields.Monetary(
        compute='_compute_price_subtotal', store=True, currency_field='currency_id',
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.constrains('quantity', 'price_unit')
    def _check_amounts(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError('Purchase order quantity must be greater than zero.')
            if line.price_unit < 0:
                raise ValidationError('Purchase order price cannot be negative.')

    def write(self, vals):
        watched = {'description', 'quantity', 'unit_text', 'price_unit', 'cost_center'}
        orders = self.mapped('order_id').filtered(
            lambda order: order.state in ('approved', 'issued', 'acknowledged')
        )
        result = super().write(vals)
        if watched & set(vals):
            orders._return_to_pending_for_amendment()
        return result
