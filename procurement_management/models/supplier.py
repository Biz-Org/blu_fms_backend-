# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProcurementSupplierProfile(models.Model):
    _name = 'procurement.management.supplier.profile'
    _description = 'Procurement Supplier Profile'
    _order = 'id desc'
    _check_company_auto = True

    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    vendor_code = fields.Char(index=True)
    category = fields.Char(index=True)
    score = fields.Float()
    preferred = fields.Boolean()
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('preferred', 'Preferred'),
            ('suspended', 'Suspended'),
        ],
        required=True,
        default='active',
        index=True,
    )
    contract_ids = fields.One2many('procurement.management.contract', 'profile_id')

    _sql_constraints = [
        (
            'partner_company_uniq',
            'unique(partner_id, company_id)',
            'A supplier can have only one procurement profile in a company.',
        ),
    ]

    @api.constrains('score')
    def _check_score(self):
        for profile in self:
            if profile.score < 0 or profile.score > 100:
                raise ValidationError('Supplier score must be between 0 and 100.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            if self.sudo().search_count([
                ('partner_id', '=', vals.get('partner_id')),
                ('company_id', '=', company_id),
            ]):
                raise ValidationError('A supplier can have only one procurement profile in a company.')
            if vals.get('state') == 'preferred':
                vals['preferred'] = True
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state, detail=record.partner_id.name)
        return records

    def write(self, vals):
        if vals.get('state') == 'preferred':
            vals = dict(vals, preferred=True)
        if vals.get('state') and vals['state'] != 'preferred' and 'preferred' not in vals:
            vals = dict(vals, preferred=False)
        result = super().write(vals)
        from ..services.common import audit_record
        for record in self:
            audit_record(record, 'modified', after=record.state, detail=', '.join(sorted(vals)))
        return result

    def unlink(self):
        from odoo.exceptions import UserError
        for profile in self:
            used = self.env['procurement.management.purchase.order'].search_count([
                ('partner_id', '=', profile.partner_id.id),
                ('company_id', '=', profile.company_id.id),
            ])
            if used:
                raise UserError('A supplier with purchase orders cannot be deleted. Suspend the profile instead.')
        return super().unlink()


class ProcurementContract(models.Model):
    _name = 'procurement.management.contract'
    _description = 'Procurement Contract'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    reference = fields.Char(required=True, copy=False, default='New', index=True)
    profile_id = fields.Many2one(
        'procurement.management.supplier.profile', required=True, ondelete='restrict', index=True,
    )
    partner_id = fields.Many2one(related='profile_id.partner_id', store=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    contract_type = fields.Char(default='MSA')
    date_start = fields.Date()
    date_end = fields.Date()
    state = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired')],
        required=True,
        default='draft',
    )
    notes = fields.Text()
    payment_terms = fields.Char()
    incoterms = fields.Char()
    credit_limit = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'procurement.management.contract')],
    )

    @api.constrains('date_start', 'date_end', 'company_id', 'profile_id')
    def _check_contract(self):
        for contract in self:
            if contract.date_end and contract.date_start and contract.date_end < contract.date_start:
                raise ValidationError('Contract expiry cannot be before the effective date.')
            if contract.profile_id.company_id != contract.company_id:
                raise ValidationError('The contract company must match the supplier profile company.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals['reference'] == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'procurement.management.contract'
                ) or 'New'
        records = super().create(vals_list)
        from ..services.common import audit_record
        for record in records:
            audit_record(record, 'created', after=record.state, detail=record.reference)
        return records
