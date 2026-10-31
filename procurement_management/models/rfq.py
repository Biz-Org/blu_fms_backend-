# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.common import guard_state, set_state


class ProcurementRfq(models.Model):
    _name = 'procurement.management.rfq'
    _description = 'Procurement RFQ'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    requisition_id = fields.Many2one('procurement.management.requisition', index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    description = fields.Text()
    department = fields.Char(index=True)
    property_project = fields.Char(index=True)
    category = fields.Char(index=True)
    deadline = fields.Date()
    estimated_value = fields.Monetary(currency_field='currency_id')
    commercial_weight = fields.Float(default=40.0)
    technical_weight = fields.Float(default=60.0)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('issued', 'Issued'),
            ('supplier_responded', 'Supplier Responded'),
            ('partially_responded', 'Partially Responded'),
            ('under_evaluation', 'Under Evaluation'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='draft',
        index=True,
    )
    selection_status = fields.Selection(
        [
            ('none', 'None'),
            ('pending', 'Pending Approval'),
            ('effective', 'Effective'),
            ('rejected', 'Rejected'),
        ],
        required=True,
        default='none',
    )
    selected_quotation_id = fields.Many2one('procurement.management.quotation', copy=False)
    supplier_ids = fields.One2many('procurement.management.rfq.supplier', 'rfq_id')
    quotation_ids = fields.One2many('procurement.management.quotation', 'rfq_id')
    response_count = fields.Integer(compute='_compute_response_count', store=True)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.rfq')],
    )

    @api.depends('supplier_ids.response_status')
    def _compute_response_count(self):
        for rfq in self:
            rfq.response_count = len(rfq.supplier_ids.filtered(
                lambda item: item.response_status == 'responded'
            ))

    @api.constrains('commercial_weight', 'technical_weight', 'estimated_value', 'company_id', 'requisition_id')
    def _check_weights(self):
        for rfq in self:
            if rfq.commercial_weight < 0 or rfq.technical_weight < 0:
                raise ValidationError('Comparison weights cannot be negative.')
            if abs((rfq.commercial_weight + rfq.technical_weight) - 100.0) > 0.001:
                raise ValidationError('Commercial and technical weights must total 100.')
            if rfq.estimated_value < 0:
                raise ValidationError('Estimated value cannot be negative.')
            if rfq.requisition_id and rfq.company_id != rfq.requisition_id.company_id:
                raise ValidationError('The RFQ company must match the requisition company.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.rfq'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state)
        return records

    def write(self, vals):
        guard_state(self, vals)
        if any(record.state in ('closed', 'cancelled') for record in self):
            allowed = {'selection_status', 'selected_quotation_id'}
            if not self.env.context.get('pm_state_write') and not set(vals).issubset(allowed):
                if not self.env.context.get('pm_admin_write'):
                    raise UserError('A closed RFQ cannot be changed.')
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise UserError('Only a draft RFQ can be deleted.')
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def _refresh_response_state(self):
        for rfq in self:
            if rfq.state not in ('issued', 'partially_responded', 'supplier_responded'):
                continue
            invited = len(rfq.supplier_ids)
            responded = rfq.response_count
            if invited and responded >= invited:
                rfq._set_state('supplier_responded')
            elif responded:
                rfq._set_state('partially_responded')

    def action_issue(self):
        from ..services.rfq_service import RfqService
        return RfqService(self.env).issue(self)

    def action_start_evaluation(self):
        from ..services.rfq_service import RfqService
        return RfqService(self.env).start_evaluation(self)

    def action_close(self):
        from ..services.rfq_service import RfqService
        return RfqService(self.env).close(self)

    def action_cancel(self):
        from ..services.rfq_service import RfqService
        return RfqService(self.env).cancel(self)


class ProcurementRfqSupplier(models.Model):
    _name = 'procurement.management.rfq.supplier'
    _description = 'Procurement RFQ Supplier'
    _order = 'id'
    _check_company_auto = True

    rfq_id = fields.Many2one(
        'procurement.management.rfq', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='rfq_id.company_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    invited_on = fields.Datetime(default=fields.Datetime.now)
    response_status = fields.Selection(
        [('invited', 'Invited'), ('responded', 'Responded')],
        required=True,
        default='invited',
    )
    response_on = fields.Datetime()

    _sql_constraints = [
        (
            'rfq_partner_uniq',
            'unique(rfq_id, partner_id)',
            'A supplier can only be invited once on an RFQ.',
        ),
    ]
