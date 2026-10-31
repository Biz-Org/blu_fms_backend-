# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import OPERATIONAL_STATUSES, OPERATIONAL_STATUS_VALUES


class CcSite(models.Model):
    _name = 'cc.site'
    _description = 'Command Center Site'
    _inherit = ['cc.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, index=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    operational_status = fields.Selection(
        OPERATIONAL_STATUSES,
        required=True,
        default='normal',
        index=True,
    )
    site_ref = fields.Char(index=True)
    location_label = fields.Char()
    active = fields.Boolean(default=True)
    alert_ids = fields.One2many('cc.alert', 'site_id')
    incident_ids = fields.One2many('cc.incident', 'site_id')
    escalation_rule_ids = fields.One2many('cc.escalation.rule', 'site_id')

    _sql_constraints = [
        (
            'code_company_uniq',
            'unique(company_id, code)',
            'Site code must be unique per company.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                raise ValidationError('Site code is required.')
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cc.site') or 'CC-SITE'
            self._assert_code_unique(
                vals.get('code'),
                vals.get('company_id') or self.env.company.id,
            )
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals or 'company_id' in vals:
            for rec in self:
                self._assert_code_unique(
                    vals.get('code', rec.code),
                    vals.get('company_id', rec.company_id.id),
                    exclude_id=rec.id,
                )
        return super().write(vals)

    def _assert_code_unique(self, code, company_id, exclude_id=None):
        if not code or not company_id:
            return
        domain = [
            ('company_id', '=', company_id),
            ('code', '=', code),
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.search_count(domain):
            raise ValidationError('Site code must be unique per company.')

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        for rec in self:
            rec._assert_code_unique(rec.code, rec.company_id.id, exclude_id=rec.id)

    @api.constrains('operational_status')
    def _check_operational_status(self):
        for rec in self:
            if rec.operational_status not in OPERATIONAL_STATUS_VALUES:
                raise ValidationError('Site operational status is not supported.')
