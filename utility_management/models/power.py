# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .mixin import staff_link
from .selections import (
    MANAGER_GROUP,
    POWER_EVENT_TYPES,
    POWER_STATES,
    POWER_TRANSITIONS,
    SOURCE_KINDS,
)


class UtilityPowerSource(models.Model):
    _name = 'utility.management.power.source'
    _description = 'Utility Power Source'
    _inherit = ['utility.management.mixin']
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    source_kind = fields.Selection(SOURCE_KINDS, required=True, index=True)
    status = fields.Selection(POWER_STATES, required=True, index=True)
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
    asset_ref = fields.Char(index=True)
    fuel_level_percent = fields.Float()
    has_fuel_level = fields.Boolean(default=False)
    fuel_capacity = fields.Float()
    fuel_consumed = fields.Float()
    has_fuel_consumed = fields.Boolean(default=False)
    rated_load = fields.Float()
    meter_id = fields.Many2one(
        'utility.management.meter',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    last_transition_at = fields.Datetime()
    event_ids = fields.One2many('utility.management.power.event', 'source_id')
    allowed_staff_ids = staff_link('utility_power_source_staff_rel', 'source_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_power_service'):
            raise UserError('Power sources are created through the power service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_power_service'):
            raise UserError('Power sources are changed through the power service.')
        if 'status' in vals:
            for source in self:
                if vals['status'] not in POWER_TRANSITIONS.get(source.status, set()):
                    raise UserError(
                        'Power source cannot move from %s to %s.' % (source.status, vals['status'])
                    )
        result = super().write(vals)
        if not self.env.context.get('utility_staff_sync'):
            self._utility_sync_staff()
            self.event_ids._utility_sync_staff()
        return result

    @api.constrains('status')
    def _check_not_left_restored(self):
        return

    @api.constrains('meter_id', 'company_id')
    def _check_meter_company(self):
        for source in self:
            if source.meter_id and source.meter_id.company_id != source.company_id:
                raise ValidationError('Linked meter must belong to the power source company.')

    @api.constrains('fuel_level_percent', 'rated_load')
    def _check_non_negative(self):
        for source in self:
            if source.has_fuel_level and source.fuel_level_percent < 0:
                raise ValidationError('Fuel level cannot be negative.')
            if source.rated_load and source.rated_load < 0:
                raise ValidationError('Rated load cannot be negative.')


class UtilityPowerEvent(models.Model):
    _name = 'utility.management.power.event'
    _description = 'Utility Power Event'
    _inherit = ['utility.management.mixin']
    _order = 'started_at desc, id desc'
    _check_company_auto = True

    source_id = fields.Many2one(
        'utility.management.power.source',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    event_type = fields.Selection(POWER_EVENT_TYPES, required=True, index=True)
    state = fields.Selection(POWER_STATES, required=True, index=True)
    started_at = fields.Datetime(required=True, index=True)
    ended_at = fields.Datetime()
    load = fields.Float()
    fuel_level_percent = fields.Float()
    has_fuel_level = fields.Boolean(default=False)
    fuel_consumed = fields.Float()
    has_fuel_consumed = fields.Boolean(default=False)
    note = fields.Text()
    runtime_hours = fields.Float(compute='_compute_runtime', store=True)
    allowed_staff_ids = staff_link('utility_power_event_staff_rel', 'event_id')

    @api.depends('started_at', 'ended_at')
    def _compute_runtime(self):
        for event in self:
            if event.started_at and event.ended_at:
                event.runtime_hours = (event.ended_at - event.started_at).total_seconds() / 3600.0
            else:
                event.runtime_hours = 0.0

    def _utility_candidate_users(self):
        self.ensure_one()
        return self.source_id._utility_candidate_users()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_power_service'):
            raise UserError('Power events are created through the power service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_power_service'):
            raise UserError('Power events are changed through the power service.')
        return super().write(vals)

    @api.constrains('source_id', 'company_id')
    def _check_company_match(self):
        for event in self:
            if event.source_id.company_id != event.company_id:
                raise ValidationError('Power event company must match the source company.')

    @api.constrains('load', 'fuel_level_percent', 'fuel_consumed', 'started_at', 'ended_at')
    def _check_event_values(self):
        for event in self:
            if event.load and event.load < 0:
                raise ValidationError('Load cannot be negative.')
            if event.has_fuel_level and event.fuel_level_percent < 0:
                raise ValidationError('Fuel level cannot be negative.')
            if event.has_fuel_consumed and event.fuel_consumed < 0:
                raise ValidationError('Fuel consumed cannot be negative.')
            if event.ended_at and event.started_at and event.ended_at < event.started_at:
                raise ValidationError('Power event end cannot be before its start.')
