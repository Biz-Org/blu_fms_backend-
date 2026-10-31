# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.common import guard_state, has_group, set_state


class ProcurementRequisition(models.Model):
    _name = 'procurement.management.requisition'
    _description = 'Procurement Requisition'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='New', index=True)
    title = fields.Char(required=True)
    description = fields.Text()
    justification = fields.Text()
    requester_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user, index=True,
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    department = fields.Char(index=True)
    property_project = fields.Char(index=True)
    category = fields.Char(index=True)
    cost_center = fields.Char()
    required_date = fields.Date()
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('returned', 'Returned'),
            ('cancelled', 'Cancelled'),
            ('converted', 'Converted'),
        ],
        required=True,
        default='draft',
        index=True,
    )
    line_ids = fields.One2many(
        'procurement.management.requisition.line', 'requisition_id', copy=True,
    )
    amount_total = fields.Monetary(compute='_compute_amount_total', store=True, currency_field='currency_id')
    converted_model = fields.Char(copy=False)
    converted_res_id = fields.Integer(copy=False)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.requisition')],
    )

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.line_ids.mapped('price_subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        officer = has_group(self.env, 'group_procurement_officer')
        for vals in vals_list:
            requester_id = vals.get('requester_id') or self.env.user.id
            if not self.env.su and requester_id != self.env.user.id and not officer:
                raise AccessError('You can only create your own requisition.')
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.requisition'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state, detail=record.title or '')
        return records

    def write(self, vals):
        guard_state(self, vals)
        if not self.env.su and not self.env.context.get('pm_state_write'):
            officer = has_group(self.env, 'group_procurement_officer')
            for record in self:
                if record.requester_id != self.env.user and not officer:
                    raise AccessError('You can only edit your own requisition.')
                if record.state not in ('draft', 'returned') and not officer:
                    raise AccessError('You can only edit a draft requisition.')
        before = {record.id: record.state for record in self}
        result = super().write(vals)
        if not self.env.context.get('pm_state_write') and any(key != 'state' for key in vals):
            from ..services.common import audit_record
            for record in self:
                audit_record(
                    record, 'modified',
                    before=before.get(record.id, ''),
                    after=record.state,
                    detail=', '.join(sorted(vals)),
                )
        return result

    def unlink(self):
        from ..services.common import audit_record
        for record in self:
            if record.state != 'draft':
                raise UserError('Only a draft requisition can be deleted.')
            audit_record(record, 'deleted', before=record.state, detail=record.name)
        return super().unlink()

    def _set_state(self, state):
        set_state(self, state)

    def action_submit(self):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).submit(self)

    def action_approve(self):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).approve(self)

    def action_reject(self, comment=''):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).reject(self, comment)

    def action_return(self, comment=''):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).return_request(self, comment)

    def action_cancel(self):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).cancel(self)

    def action_convert_rfq(self):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).convert_rfq(self)

    def action_convert_po(self, partner):
        from ..services.requisition_service import RequisitionService
        return RequisitionService(self.env).convert_po(self, partner)


class ProcurementRequisitionLine(models.Model):
    _name = 'procurement.management.requisition.line'
    _description = 'Procurement Requisition Line'
    _order = 'id'
    _check_company_auto = True

    requisition_id = fields.Many2one(
        'procurement.management.requisition', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='requisition_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='requisition_id.currency_id', store=True)
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
                raise ValidationError('Requisition quantity must be greater than zero.')
            if line.price_unit < 0:
                raise ValidationError('Requisition price cannot be negative.')
