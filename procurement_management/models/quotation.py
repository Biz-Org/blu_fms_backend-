# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services.common import guard_state


class ProcurementQuotation(models.Model):
    _name = 'procurement.management.quotation'
    _description = 'Procurement Quotation'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    rfq_id = fields.Many2one(
        'procurement.management.rfq', required=True, ondelete='cascade', index=True,
    )
    invitation_id = fields.Many2one('procurement.management.rfq.supplier', index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    quotation_date = fields.Date(default=fields.Date.context_today)
    validity_date = fields.Date()
    amount_untaxed = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_tax = fields.Monetary(currency_field='currency_id')
    freight_amount = fields.Monetary(currency_field='currency_id')
    amount_total = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    commercial_score = fields.Float()
    technical_score = fields.Float()
    weighted_score = fields.Float(compute='_compute_weighted_score', store=True)
    evaluation_notes = fields.Text()
    state = fields.Selection(
        [
            ('under_evaluation', 'Under Evaluation'),
            ('shortlisted', 'Shortlisted'),
            ('recommended', 'Recommended'),
            ('selected', 'Selected'),
            ('rejected', 'Rejected'),
        ],
        required=True,
        default='under_evaluation',
        index=True,
    )
    line_ids = fields.One2many('procurement.management.quotation.line', 'quotation_id', copy=True)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.quotation')],
    )

    @api.depends('line_ids.price_subtotal', 'amount_tax', 'freight_amount')
    def _compute_amounts(self):
        for quotation in self:
            untaxed = sum(quotation.line_ids.mapped('price_subtotal'))
            quotation.amount_untaxed = untaxed
            quotation.amount_total = untaxed + (quotation.amount_tax or 0.0) + (quotation.freight_amount or 0.0)

    @api.depends(
        'commercial_score', 'technical_score',
        'rfq_id.commercial_weight', 'rfq_id.technical_weight',
    )
    def _compute_weighted_score(self):
        for quotation in self:
            rfq = quotation.rfq_id
            quotation.weighted_score = (
                (quotation.commercial_score or 0.0) * (rfq.commercial_weight or 0.0)
                + (quotation.technical_score or 0.0) * (rfq.technical_weight or 0.0)
            ) / 100.0

    @api.constrains('commercial_score', 'technical_score', 'amount_tax', 'freight_amount', 'quotation_date', 'validity_date')
    def _check_scores(self):
        for quotation in self:
            for score in (quotation.commercial_score, quotation.technical_score):
                if score < 0 or score > 10:
                    raise ValidationError('Scores must be between 0 and 10.')
            if quotation.amount_tax < 0 or quotation.freight_amount < 0:
                raise ValidationError('Tax and freight cannot be negative.')
            if quotation.validity_date and quotation.quotation_date and quotation.validity_date < quotation.quotation_date:
                raise ValidationError('Quotation validity cannot be before the quotation date.')
            if quotation.rfq_id and quotation.company_id != quotation.rfq_id.company_id:
                raise ValidationError('The quotation company must match the RFQ company.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            rfq = self.env['procurement.management.rfq'].browse(vals.get('rfq_id'))
            if rfq and not vals.get('company_id'):
                vals['company_id'] = rfq.company_id.id
            if rfq and not vals.get('invitation_id') and vals.get('partner_id'):
                invitation = rfq.supplier_ids.filtered(
                    lambda row: row.partner_id.id == vals['partner_id']
                )[:1]
                if invitation:
                    vals['invitation_id'] = invitation.id
            if not vals.get('name') or vals['name'] == 'New':
                sequence = len(rfq.quotation_ids) + 1 if rfq else 1
                vals['name'] = '%s-Q%02d' % (rfq.name or 'QT', sequence)
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state)
            if record.invitation_id:
                record.invitation_id.write({
                    'response_status': 'responded',
                    'response_on': fields.Datetime.now(),
                })
                record.rfq_id._refresh_response_state()
        return records

    def write(self, vals):
        guard_state(self, vals)
        return super().write(vals)

    def _set_state(self, state):
        from ..services.common import set_state as apply_state
        apply_state(self, state)


class ProcurementQuotationLine(models.Model):
    _name = 'procurement.management.quotation.line'
    _description = 'Procurement Quotation Line'
    _order = 'id'

    quotation_id = fields.Many2one(
        'procurement.management.quotation', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='quotation_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='quotation_id.currency_id', store=True)
    description = fields.Char(required=True)
    quantity = fields.Float(required=True, default=1.0)
    unit_text = fields.Char()
    price_unit = fields.Monetary(currency_field='currency_id')
    technical_notes = fields.Text()
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
                raise ValidationError('Quotation quantity must be greater than zero.')
            if line.price_unit < 0:
                raise ValidationError('Quotation price cannot be negative.')
