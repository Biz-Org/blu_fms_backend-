# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import (
    ALERT_STATE_VALUES,
    ALERT_STATES,
    INCIDENT_PROTECTED_FIELDS,
    SEVERITIES,
    SEVERITY_VALUES,
)


class CcIncident(models.Model):
    _name = 'cc.incident'
    _description = 'Command Center Incident'
    _inherit = ['cc.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, index=True)
    severity = fields.Selection(SEVERITIES, index=True)
    state = fields.Selection(ALERT_STATES, required=True, default='open', index=True)
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
    user_id = fields.Many2one('res.users', string='Assignee', index=True, ondelete='set null')
    summary = fields.Text()
    resolution = fields.Text()
    opened_at = fields.Datetime(default=fields.Datetime.now)
    acknowledged_at = fields.Datetime()
    resolved_at = fields.Datetime()
    closed_at = fields.Datetime()
    alert_ids = fields.One2many('cc.alert', 'incident_id')
    note_ids = fields.One2many('cc.investigation.note', 'incident_id')

    @api.model_create_multi
    def create(self, vals_list):
        self._cc_require_manager()
        for vals in vals_list:
            self._cc_guard_lifecycle_fields(
                vals,
                INCIDENT_PROTECTED_FIELDS,
                'Incident status fields can only be changed through lifecycle actions.',
                creating=True,
            )
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cc.incident') or 'CC-INC'
        return super().create(vals_list)

    def write(self, vals):
        self._cc_guard_lifecycle_fields(
            vals,
            INCIDENT_PROTECTED_FIELDS,
            'Incident status fields can only be changed through lifecycle actions.',
        )
        return super().write(vals)

    @api.constrains('severity')
    def _check_severity(self):
        for rec in self:
            if rec.severity and rec.severity not in SEVERITY_VALUES:
                raise ValidationError('Incident severity is not supported.')

    @api.constrains('state')
    def _check_state(self):
        for rec in self:
            if rec.state not in ALERT_STATE_VALUES:
                raise ValidationError('Incident state is not supported.')

    @api.constrains('site_id', 'company_id')
    def _check_site_company(self):
        for rec in self:
            if rec.site_id and rec.site_id.company_id != rec.company_id:
                raise ValidationError('Incident company must match the selected site company.')
