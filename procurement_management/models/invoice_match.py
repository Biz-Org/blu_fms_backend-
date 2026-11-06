# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.common import guard_state, set_state


class ProcurementInvoiceMatch(models.Model):
    _name = 'procurement.management.invoice.match'
    _description = 'Procurement Invoice Match'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    supplier_invoice_number = fields.Char(required=True, index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    order_id = fields.Many2one('procurement.management.purchase.order', required=True, index=True)
    receipt_id = fields.Many2one('procurement.management.receipt', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    invoice_date = fields.Date(default=fields.Date.context_today)
    invoice_amount = fields.Monetary(currency_field='currency_id')
    matched_amount = fields.Monetary(compute='_compute_variance', store=True, currency_field='currency_id')
    amount_variance = fields.Monetary(compute='_compute_variance', store=True, currency_field='currency_id')
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('matched', 'Matched'),
            ('mismatch', 'Mismatch'),
            ('under_review', 'Under Review'),
        ],
        required=True,
        default='pending',
        index=True,
    )
    duplicate_flag = fields.Boolean(default=False)
    exception_reason = fields.Char()
    resolution = fields.Selection(
        [('rejected', 'Rejected'), ('resolved', 'Resolved')],
    )
    resolution_note = fields.Text()
    line_ids = fields.One2many('procurement.management.invoice.match.line', 'match_id')
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.invoice.match')],
    )

    _sql_constraints = [
        (
            'supplier_invoice_uniq',
            'unique(company_id, partner_id, supplier_invoice_number)',
            'This supplier invoice number is already recorded for the supplier in this company.',
        ),
    ]

    @api.depends(
        'line_ids.matched_amount', 'line_ids.variance_amount',
        'invoice_amount', 'currency_id',
    )
    def _compute_variance(self):
        for match in self:
            matched = sum(match.line_ids.mapped('matched_amount'))
            variance = sum(match.line_ids.mapped('variance_amount'))
            if match.currency_id:
                matched = match.currency_id.round(matched)
                variance = match.currency_id.round(variance)
            match.matched_amount = matched
            match.amount_variance = variance

    @api.constrains('company_id', 'order_id', 'receipt_id', 'invoice_amount')
    def _check_company_links(self):
        for match in self:
            if match.invoice_amount < 0:
                raise ValidationError('Invoice amount cannot be negative.')
            if match.order_id and match.company_id != match.order_id.company_id:
                raise ValidationError('The invoice company must match the purchase order company.')
            if match.receipt_id and match.receipt_id.company_id != match.company_id:
                raise ValidationError('The invoice company must match the receipt company.')
            if match.order_id and match.partner_id != match.order_id.partner_id:
                raise ValidationError('The invoice supplier must match the purchase order supplier.')

    @api.model_create_multi
    def create(self, vals_list):
        from ..services.invoice_match_service import InvoiceMatchService
        checker = InvoiceMatchService(self.env)
        for vals in vals_list:
            company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            checker.check_duplicate(company, partner, vals.get('supplier_invoice_number'))
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.invoice.match'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state, detail=record.supplier_invoice_number)
        return records

    def write(self, vals):
        guard_state(self, vals)
        return super().write(vals)

    def unlink(self):
        for match in self:
            if match.state != 'pending':
                raise UserError('Only a pending invoice match can be deleted.')
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def _is_clean(self):
        self.ensure_one()
        currency = self.currency_id
        amount_gap = currency.round(self.amount_variance) if currency else round(self.amount_variance, 2)
        header_gap = 0.0
        if self.invoice_amount:
            header_gap = (currency.round(self.invoice_amount - self.matched_amount)
                          if currency else round(self.invoice_amount - self.matched_amount, 2))
        qty_gap = any(abs(line.variance_qty) > 0.0001 for line in self.line_ids)
        return not qty_gap and amount_gap == 0 and header_gap == 0

    def action_auto_match(self):
        from ..services.invoice_match_service import InvoiceMatchService
        return InvoiceMatchService(self.env).auto_match(self)

    def action_approve(self):
        from ..services.invoice_match_service import InvoiceMatchService
        return InvoiceMatchService(self.env).approve(self)

    def action_reject(self, note=''):
        from ..services.invoice_match_service import InvoiceMatchService
        return InvoiceMatchService(self.env).reject(self, note)

    def action_resolve(self, note):
        from ..services.invoice_match_service import InvoiceMatchService
        return InvoiceMatchService(self.env).resolve(self, note)


class ProcurementInvoiceMatchLine(models.Model):
    _name = 'procurement.management.invoice.match.line'
    _description = 'Procurement Invoice Match Line'
    _order = 'id'

    match_id = fields.Many2one(
        'procurement.management.invoice.match', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='match_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='match_id.currency_id', store=True)
    order_line_id = fields.Many2one('procurement.management.purchase.order.line')
    description = fields.Char(required=True)
    po_qty = fields.Float()
    receipt_qty = fields.Float()
    invoice_qty = fields.Float()
    po_price = fields.Monetary(currency_field='currency_id')
    invoice_price = fields.Monetary(currency_field='currency_id')
    variance_qty = fields.Float(compute='_compute_variance', store=True)
    matched_amount = fields.Monetary(compute='_compute_variance', store=True, currency_field='currency_id')
    variance_amount = fields.Monetary(compute='_compute_variance', store=True, currency_field='currency_id')

    @api.depends('po_qty', 'receipt_qty', 'invoice_qty', 'po_price', 'invoice_price', 'currency_id')
    def _compute_variance(self):
        for line in self:
            currency = line.currency_id
            matched_qty = min(line.po_qty or 0.0, line.receipt_qty or 0.0, line.invoice_qty or 0.0)
            matched = matched_qty * (line.po_price or 0.0)
            invoiced = (line.invoice_qty or 0.0) * (line.invoice_price or 0.0)
            ordered = (line.po_qty or 0.0) * (line.po_price or 0.0)
            variance = invoiced - ordered
            if currency:
                matched = currency.round(matched)
                variance = currency.round(variance)
            line.variance_qty = (line.invoice_qty or 0.0) - (line.receipt_qty or 0.0)
            line.matched_amount = matched
            line.variance_amount = variance

    @api.constrains('po_qty', 'receipt_qty', 'invoice_qty', 'po_price', 'invoice_price')
    def _check_values(self):
        for line in self:
            for value in (line.po_qty, line.receipt_qty, line.invoice_qty, line.po_price, line.invoice_price):
                if value < 0:
                    raise ValidationError('Invoice match quantities and prices cannot be negative.')
