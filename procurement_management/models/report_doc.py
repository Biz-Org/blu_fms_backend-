# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProcurementReportDefinition(models.Model):
    _name = 'procurement.management.report.definition'
    _description = 'Procurement Report Definition'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True,
    )
    report_type = fields.Selection(
        [
            ('spend', 'Spend Analysis'),
            ('performance', 'Performance'),
            ('requisitions', 'Requisitions'),
            ('rfq', 'RFQs and Quotations'),
            ('custom', 'Custom'),
        ],
        required=True,
        default='spend',
    )
    date_from = fields.Date()
    date_to = fields.Date()
    department = fields.Char()
    partner_id = fields.Many2one('res.partner')
    category = fields.Char()
    status = fields.Char()
    metrics = fields.Char()
    group_by = fields.Char()
    sort_by = fields.Char()
    schedule = fields.Selection(
        [('none', 'None'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        required=True,
        default='none',
    )
    weekday = fields.Integer(help='Monday is 0.')
    month_day = fields.Integer()
    recipient_emails = fields.Char()
    last_run_on = fields.Date()
    run_ids = fields.One2many('procurement.management.report.run', 'definition_id')

    @api.constrains('date_from', 'date_to', 'schedule', 'weekday', 'month_day')
    def _check_definition(self):
        for definition in self:
            if definition.date_from and definition.date_to and definition.date_to < definition.date_from:
                raise ValidationError('The report end date cannot be before the start date.')
            if definition.schedule == 'weekly' and definition.weekday not in range(0, 7):
                raise ValidationError('Weekly reports need a weekday from 0 (Monday) to 6 (Sunday).')
            if definition.schedule == 'monthly' and definition.month_day not in range(1, 29):
                raise ValidationError('Monthly reports need a day from 1 to 28.')

    def action_preview(self):
        from ..services.report_service import ReportService
        return ReportService(self.env).preview(self)

    def action_export(self, file_format):
        from ..services.report_service import ReportService
        return ReportService(self.env).export(self, file_format)

    @api.model
    def _cron_send_scheduled(self):
        from ..services.report_service import ReportService
        return ReportService(self.env).send_due()


class ProcurementReportRun(models.Model):
    _name = 'procurement.management.report.run'
    _description = 'Procurement Report Run'
    _order = 'id desc'

    name = fields.Char(required=True)
    definition_id = fields.Many2one(
        'procurement.management.report.definition', required=True, ondelete='restrict', index=True,
    )
    company_id = fields.Many2one(related='definition_id.company_id', store=True, index=True)
    state = fields.Selection(
        [
            ('ready', 'Ready'),
            ('generating', 'Generating'),
            ('exported', 'Exported'),
            ('failed', 'Failed'),
        ],
        required=True,
        default='ready',
        index=True,
    )
    file_format = fields.Selection(
        [('csv', 'CSV'), ('xlsx', 'Excel'), ('pdf', 'PDF')],
    )
    attachment_id = fields.Many2one('ir.attachment')
    error_detail = fields.Text()
    started_on = fields.Datetime()
    finished_on = fields.Datetime()

    def unlink(self):
        from odoo.exceptions import UserError
        raise UserError('Report runs cannot be deleted.')
