# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import REPORT_SOURCE_VALUES, REPORT_SOURCES


class CcReportDefinition(models.Model):
    _name = 'cc.report.definition'
    _description = 'Command Center Report Definition'
    _inherit = ['cc.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    source = fields.Selection(REPORT_SOURCES, required=True, index=True)
    field_names = fields.Json()
    filters_json = fields.Json()
    grouping = fields.Char()
    sorting = fields.Char()
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    owner_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True,
    )
    active = fields.Boolean(default=True)
    export_ids = fields.One2many('cc.report.export', 'definition_id')

    @api.constrains('source')
    def _check_source(self):
        for rec in self:
            if rec.source not in REPORT_SOURCE_VALUES:
                raise ValidationError('Report source is not supported.')
