# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import (
    ALERT_PROTECTED_FIELDS,
    ALERT_SOURCE_VALUES,
    ALERT_SOURCES,
    ALERT_STATE_VALUES,
    ALERT_STATES,
    SEVERITIES,
    SEVERITY_VALUES,
)


class CcAlert(models.Model):
    _name = 'cc.alert'
    _description = 'Command Center Alert'
    _inherit = ['cc.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, index=True)
    alert_type = fields.Char(required=True, index=True)
    severity = fields.Selection(SEVERITIES, index=True)
    source = fields.Selection(ALERT_SOURCES, index=True, default='manual')
    source_model = fields.Char()
    source_id = fields.Integer()
    site_id = fields.Many2one(
        'cc.site',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    state = fields.Selection(ALERT_STATES, required=True, default='open', index=True)
    user_id = fields.Many2one('res.users', string='Assignee', index=True, ondelete='set null')
    is_emergency = fields.Boolean(default=False, index=True)
    acknowledged_uid = fields.Many2one('res.users', ondelete='set null')
    acknowledged_at = fields.Datetime()
    resolved_uid = fields.Many2one('res.users', ondelete='set null')
    resolved_at = fields.Datetime()
    closed_at = fields.Datetime()
    resolution_note = fields.Text()
    incident_id = fields.Many2one(
        'cc.incident',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    response_deadline = fields.Datetime()
    note_ids = fields.One2many('cc.investigation.note', 'alert_id')
    history_ids = fields.One2many('cc.escalation.history', 'alert_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._cc_guard_lifecycle_fields(
                vals,
                ALERT_PROTECTED_FIELDS,
                'Alert status fields can only be changed through lifecycle actions.',
                creating=True,
            )
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cc.alert') or 'CC-ALT'
        return super().create(vals_list)

    def write(self, vals):
        self._cc_guard_lifecycle_fields(
            vals,
            ALERT_PROTECTED_FIELDS,
            'Alert status fields can only be changed through lifecycle actions.',
        )
        return super().write(vals)

    @api.constrains('severity')
    def _check_severity(self):
        for rec in self:
            if rec.severity and rec.severity not in SEVERITY_VALUES:
                raise ValidationError('Alert severity is not supported.')

    @api.constrains('source')
    def _check_source(self):
        for rec in self:
            if rec.source and rec.source not in ALERT_SOURCE_VALUES:
                raise ValidationError('Alert source is not supported.')

    @api.constrains('state')
    def _check_state(self):
        for rec in self:
            if rec.state not in ALERT_STATE_VALUES:
                raise ValidationError('Alert state is not supported.')

    @api.constrains('site_id', 'company_id')
    def _check_site_company(self):
        for rec in self:
            if rec.site_id and rec.site_id.company_id != rec.company_id:
                raise ValidationError('Alert company must match the selected site company.')

    @api.constrains('incident_id', 'company_id')
    def _check_incident_company(self):
        for rec in self:
            if rec.incident_id and rec.incident_id.company_id != rec.company_id:
                raise ValidationError('Alert company must match the linked incident company.')
