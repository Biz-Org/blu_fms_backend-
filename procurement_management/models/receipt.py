# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.common import guard_state, set_state


class ProcurementReceipt(models.Model):
    _name = 'procurement.management.receipt'
    _description = 'Procurement Goods Receipt'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    order_id = fields.Many2one(
        'procurement.management.purchase.order', required=True, ondelete='restrict', index=True,
    )
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    receipt_date = fields.Date(default=fields.Date.context_today)
    delivery_notes = fields.Text()
    state = fields.Selection(
        [
            ('expected', 'Expected'),
            ('pending_receipt', 'Pending Receipt'),
            ('receiving', 'Receiving'),
            ('pending_inspection', 'Pending Inspection'),
            ('inspection', 'Inspection'),
            ('completed', 'Completed'),
        ],
        required=True,
        default='expected',
        index=True,
    )
    inspection_result = fields.Selection(
        [
            ('pass', 'Pass'),
            ('hold_qa', 'Hold for QA'),
            ('reject', 'Reject'),
        ],
    )
    line_ids = fields.One2many('procurement.management.receipt.line', 'receipt_id')
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.receipt')],
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.receipt'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state)
        return records

    @api.constrains('company_id', 'order_id', 'partner_id')
    def _check_company_links(self):
        for receipt in self:
            if receipt.order_id and receipt.company_id != receipt.order_id.company_id:
                raise ValidationError('The receipt company must match the purchase order company.')
            if receipt.order_id and receipt.partner_id != receipt.order_id.partner_id:
                raise ValidationError('The receipt supplier must match the purchase order supplier.')

    def write(self, vals):
        guard_state(self, vals)
        return super().write(vals)

    def unlink(self):
        for receipt in self:
            if receipt.state not in ('expected', 'receiving', 'pending_receipt'):
                raise UserError('This receipt can no longer be deleted.')
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def action_start(self):
        from ..services.receipt_service import ReceiptService
        return ReceiptService(self.env).start(self)

    def action_save_draft(self, quantities=None):
        from ..services.receipt_service import ReceiptService
        return ReceiptService(self.env).save_draft(self, quantities or {})

    def action_confirm(self, quantities):
        from ..services.receipt_service import ReceiptService
        return ReceiptService(self.env).confirm(self, quantities)

    def action_inspect(self, result, notes=''):
        from ..services.receipt_service import ReceiptService
        return ReceiptService(self.env).inspect(self, result, notes)


class ProcurementReceiptLine(models.Model):
    _name = 'procurement.management.receipt.line'
    _description = 'Procurement Goods Receipt Line'
    _order = 'id'

    receipt_id = fields.Many2one(
        'procurement.management.receipt', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='receipt_id.company_id', store=True, index=True)
    order_line_id = fields.Many2one('procurement.management.purchase.order.line', required=True)
    description = fields.Char(required=True)
    ordered_qty = fields.Float(required=True)
    received_qty = fields.Float(default=0.0)
    batch_lot = fields.Char()
    inspection_notes = fields.Text()

    @api.constrains('ordered_qty', 'received_qty')
    def _check_qty(self):
        for line in self:
            if line.ordered_qty <= 0:
                raise ValidationError('Ordered quantity must be greater than zero.')
            if line.received_qty < 0:
                raise ValidationError('Received quantity cannot be negative.')
            if line.received_qty > line.ordered_qty + 0.0001:
                raise ValidationError('Received quantity cannot exceed the ordered quantity.')
