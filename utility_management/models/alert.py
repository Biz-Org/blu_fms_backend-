# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .mixin import staff_link
from .selections import (
    ALERT_RULE_TYPES,
    ALERT_SEVERITIES,
    ALERT_STATES,
    ALERT_TRANSITIONS,
    TANK_BOUNDS,
    UTILITY_TYPES,
)


class UtilityAlertRule(models.Model):
    _name = 'utility.management.alert.rule'
    _description = 'Utility Alert Rule'
    _inherit = ['utility.management.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    rule_type = fields.Selection(ALERT_RULE_TYPES, required=True, index=True)
    utility_type = fields.Selection(UTILITY_TYPES, index=True)
    meter_id = fields.Many2one(
        'utility.management.meter',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
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
    threshold_value = fields.Float()
    threshold_percent = fields.Float()
    tank_bound = fields.Selection(TANK_BOUNDS)
    severity = fields.Selection(ALERT_SEVERITIES, required=True, default='medium')
    escalation_minutes = fields.Integer()
    escalate_to_id = fields.Many2one('res.users', ondelete='set null')
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_alert_service'):
            raise UserError('Alert rules are created through the alert service.')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('utility_alert_service'):
            raise UserError('Alert rules are changed through the alert service.')
        return super().write(vals)

    @api.constrains('meter_id', 'company_id', 'threshold_percent', 'escalation_minutes')
    def _check_rule(self):
        for rule in self:
            if rule.meter_id and rule.meter_id.company_id != rule.company_id:
                raise ValidationError('Alert rule company must match the meter company.')
            if rule.threshold_percent and rule.threshold_percent < 0:
                raise ValidationError('Threshold percent cannot be negative.')
            if rule.escalation_minutes and rule.escalation_minutes < 0:
                raise ValidationError('Escalation minutes cannot be negative.')


class UtilityAlert(models.Model):
    _name = 'utility.management.alert'
    _description = 'Utility Alert'
    _inherit = ['utility.management.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'triggered_at desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='/', index=True)
    rule_id = fields.Many2one(
        'utility.management.alert.rule',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    alert_type = fields.Selection(ALERT_RULE_TYPES, required=True, index=True)
    severity = fields.Selection(ALERT_SEVERITIES, required=True, default='medium', index=True)
    state = fields.Selection(ALERT_STATES, required=True, default='new', index=True)
    meter_id = fields.Many2one(
        'utility.management.meter',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    reading_id = fields.Many2one(
        'utility.management.reading',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    leak_id = fields.Many2one(
        'utility.management.leak',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    power_event_id = fields.Many2one(
        'utility.management.power.event',
        ondelete='set null',
        index=True,
        check_company=True,
    )
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
    assignee_id = fields.Many2one('res.users', index=True, ondelete='set null')
    triggered_at = fields.Datetime(required=True, index=True)
    observed_value = fields.Float()
    threshold_value = fields.Float()
    acknowledged_by = fields.Many2one('res.users', ondelete='set null')
    acknowledged_at = fields.Datetime()
    resolved_by = fields.Many2one('res.users', ondelete='set null')
    resolved_at = fields.Datetime()
    closed_at = fields.Datetime()
    resolution_note = fields.Text()
    escalated_at = fields.Datetime()
    escalation_count = fields.Integer(default=0)
    allowed_staff_ids = staff_link('utility_alert_staff_rel', 'alert_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_alert_service'):
            raise UserError('Alerts are created through the alert service.')
        for vals in vals_list:
            if vals.get('name', '/') in (False, '/'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.management.alert') or '/'
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_alert_service'):
            raise UserError('Alerts are changed through the alert service.')
        if 'state' in vals:
            for alert in self:
                if vals['state'] not in ALERT_TRANSITIONS.get(alert.state, set()):
                    raise UserError('Alert cannot move from %s to %s.' % (alert.state, vals['state']))
        result = super().write(vals)
        if not self.env.context.get('utility_staff_sync'):
            self._utility_sync_staff()
        return result

    def _cron_escalate(self):
        from odoo.addons.utility_management.services.alert_service import AlertService
        AlertService(self.env).escalate_due()

    @api.constrains('meter_id', 'reading_id', 'leak_id', 'power_event_id', 'rule_id', 'company_id')
    def _check_company_match(self):
        for alert in self:
            for linked in (alert.meter_id, alert.reading_id, alert.leak_id, alert.power_event_id, alert.rule_id):
                if linked and linked.company_id != alert.company_id:
                    raise ValidationError('Alert links must belong to the alert company.')
