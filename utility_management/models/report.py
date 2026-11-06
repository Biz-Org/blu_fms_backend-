# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .mixin import staff_link
from .selections import (
    COMPARISONS,
    EXECUTION_STATES,
    EXPORT_FORMATS,
    GROUPINGS,
    REPORT_TYPES,
    SCHEDULES,
    UTILITY_TYPES,
)


class UtilityReportDefinition(models.Model):
    _name = 'utility.management.report.definition'
    _description = 'Utility Report Definition'
    _inherit = ['utility.management.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    owner_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True,
    )
    report_type = fields.Selection(REPORT_TYPES, required=True, index=True)
    property_ref = fields.Char(index=True)
    property_label = fields.Char()
    site_ref = fields.Char(index=True)
    site_label = fields.Char()
    floor_ref = fields.Char(index=True)
    floor_label = fields.Char()
    area_ref = fields.Char(index=True)
    area_label = fields.Char()
    department_ref = fields.Char(index=True)
    department_label = fields.Char()
    utility_type = fields.Selection(UTILITY_TYPES, index=True)
    meter_id = fields.Many2one(
        'utility.management.meter',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    date_from = fields.Date()
    date_to = fields.Date()
    grouping = fields.Selection(GROUPINGS, default='month')
    comparison = fields.Selection(COMPARISONS, default='none')
    schedule = fields.Selection(SCHEDULES, default='none', required=True)
    recipient_user_ids = fields.Many2many(
        'res.users',
        'utility_report_recipient_rel',
        'definition_id',
        'user_id',
        string='Recipients',
    )
    active = fields.Boolean(default=True)
    run_ids = fields.One2many('utility.management.report.run', 'definition_id')
    allowed_staff_ids = staff_link('utility_report_def_staff_rel', 'definition_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_report_service'):
            raise UserError('Report definitions are created through the report service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_report_service'):
            raise UserError('Report definitions are changed through the report service.')
        result = super().write(vals)
        if not self.env.context.get('utility_staff_sync'):
            self._utility_sync_staff()
        return result

    def _cron_scheduled(self):
        from odoo.addons.utility_management.services.report_service import ReportService
        ReportService(self.env).send_due()

    def report_lines(self):
        self.ensure_one()
        from odoo.addons.utility_management.services.report_service import ReportService
        rows = ReportService(self.env).rows_for(self)
        if isinstance(rows, dict):
            return [rows]
        return rows or []

    def report_text(self):
        lines = []
        for row in self.report_lines():
            if isinstance(row, dict):
                lines.append(', '.join('%s=%s' % (key, value) for key, value in row.items()))
            else:
                lines.append(str(row))
        return lines or ['No rows']

    @api.constrains('meter_id', 'company_id', 'date_from', 'date_to')
    def _check_definition(self):
        for definition in self:
            if definition.meter_id and definition.meter_id.company_id != definition.company_id:
                raise ValidationError('Report meter must belong to the report company.')
            if definition.date_from and definition.date_to and definition.date_from > definition.date_to:
                raise ValidationError('Report start date cannot be after the end date.')


class UtilityReportRun(models.Model):
    _name = 'utility.management.report.run'
    _description = 'Utility Report Run'
    _inherit = ['utility.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='/', index=True)
    definition_id = fields.Many2one(
        'utility.management.report.definition',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, ondelete='set null', index=True)
    execution_state = fields.Selection(EXECUTION_STATES, required=True, default='pending', index=True)
    export_format = fields.Selection(EXPORT_FORMATS, required=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='restrict')
    error_message = fields.Text()
    result_rows = fields.Json(
        help='Rows used to build this run. Report Detail charts this snapshot.',
    )
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    allowed_staff_ids = staff_link('utility_report_run_staff_rel', 'run_id')

    def _utility_candidate_users(self):
        self.ensure_one()
        users = self.definition_id._utility_candidate_users()
        if self.user_id:
            users |= self.user_id
        return users

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_report_service'):
            raise UserError('Report runs are created through the report service.')
        for vals in vals_list:
            if vals.get('name', '/') in (False, '/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'utility.management.report.run'
                ) or '/'
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_report_service'):
            raise UserError('Report runs are changed through the report service.')
        for run in self:
            if run.execution_state in ('completed', 'failed') and 'execution_state' in vals:
                raise UserError('A finished report run cannot change state.')
        return super().write(vals)

    @api.constrains('definition_id', 'company_id')
    def _check_company_match(self):
        for run in self:
            if run.definition_id.company_id != run.company_id:
                raise ValidationError('Report run company must match the definition company.')
