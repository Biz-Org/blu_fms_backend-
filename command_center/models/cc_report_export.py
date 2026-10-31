# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import EXPORT_FORMAT_VALUES, EXPORT_FORMATS


class CcReportExport(models.Model):
    _name = 'cc.report.export'
    _description = 'Command Center Report Export'
    _inherit = ['cc.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char()
    definition_id = fields.Many2one(
        'cc.report.definition',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    export_format = fields.Selection(EXPORT_FORMATS, required=True, default='csv')
    filename = fields.Char()
    content = fields.Text()
    user_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = vals.get('filename') or 'Export'
        return super().create(vals_list)

    @api.constrains('export_format')
    def _check_export_format(self):
        for rec in self:
            if rec.export_format not in EXPORT_FORMAT_VALUES:
                raise ValidationError('Export format must be CSV or JSON.')

    @api.constrains('definition_id', 'company_id')
    def _check_definition_company(self):
        for rec in self:
            if rec.definition_id and rec.definition_id.company_id != rec.company_id:
                raise ValidationError('Export company must match the report definition company.')
