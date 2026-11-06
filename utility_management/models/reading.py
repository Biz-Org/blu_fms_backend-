# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .mixin import staff_link
from .selections import (
    LOCATION_FIELDS,
    READING_SOURCES,
    READING_STATUSES,
    READING_TRANSITIONS,
    SAFETY_OBSERVATIONS,
)


class UtilityReading(models.Model):
    _name = 'utility.management.reading'
    _description = 'Utility Meter Reading'
    _inherit = ['utility.management.mixin']
    _order = 'observed_at desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='/', index=True)
    meter_id = fields.Many2one(
        'utility.management.meter',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    observed_at = fields.Datetime(required=True, index=True)
    source = fields.Selection(READING_SOURCES, required=True, index=True)
    status = fields.Selection(READING_STATUSES, required=True, default='recorded', index=True)
    register_value = fields.Float()
    interval_quantity = fields.Float()
    consumption_qty = fields.Float()
    previous_reading_id = fields.Many2one(
        'utility.management.reading',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    corrects_reading_id = fields.Many2one(
        'utility.management.reading',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    idempotency_key = fields.Char(index=True)
    is_abnormal = fields.Boolean(default=False, index=True)
    abnormal_reason = fields.Char()
    is_rollover = fields.Boolean(default=False)
    verified_by = fields.Many2one('res.users', ondelete='set null')
    verified_at = fields.Datetime()
    notes = fields.Text()
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
    voltage = fields.Float()
    current = fields.Float()
    frequency = fields.Float()
    power_factor = fields.Float()
    demand_kw = fields.Float()
    load_kw = fields.Float()
    flow_rate = fields.Float()
    tank_level = fields.Float()
    inflow = fields.Float()
    outflow = fields.Float()
    pressure = fields.Float()
    safety_observation = fields.Selection(SAFETY_OBSERVATIONS)
    photo_attachment_id = fields.Many2one('ir.attachment', ondelete='restrict', index=True)
    allowed_staff_ids = staff_link('utility_reading_staff_rel', 'reading_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_reading_service'):
            raise UserError('Readings are created through the reading service.')
        for vals in vals_list:
            if vals.get('name', '/') in (False, '/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'utility.management.reading'
                ) or '/'
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_reading_service'):
            raise UserError('Readings are changed through the reading service.')
        if 'status' in vals:
            for reading in self:
                new_status = vals['status']
                if new_status not in READING_TRANSITIONS.get(reading.status, set()):
                    raise UserError(
                        'Reading cannot move from %s to %s.' % (reading.status, new_status)
                    )
        locked = self.filtered(lambda reading: reading.status == 'corrected')
        mutable = {'allowed_staff_ids'}
        if locked and set(vals) - mutable:
            raise UserError('A corrected reading is immutable.')
        result = super().write(vals)
        if set(LOCATION_FIELDS).intersection(vals) or 'company_id' in vals:
            self._utility_sync_staff()
        return result

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_reading_observation_uniq
            ON utility_management_reading (company_id, meter_id, observed_at, source)
            WHERE status IS DISTINCT FROM 'corrected'
            """
        )
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_reading_idempotency_uniq
            ON utility_management_reading (company_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL AND status IS DISTINCT FROM 'corrected'
            """
        )

    @api.constrains(
        'voltage', 'current', 'frequency', 'power_factor', 'demand_kw', 'load_kw',
        'flow_rate', 'tank_level', 'inflow', 'outflow', 'pressure', 'meter_id',
    )
    def _check_measures(self):
        for reading in self:
            utility = reading.meter_id.utility_type
            electrical = (
                reading.voltage, reading.current, reading.frequency,
                reading.power_factor, reading.demand_kw, reading.load_kw,
            )
            water_only = (reading.tank_level, reading.inflow, reading.outflow)
            if utility != 'electricity' and any(electrical):
                raise ValidationError('Electrical measures belong on electricity meters only.')
            if utility not in ('water', 'gas') and reading.flow_rate:
                raise ValidationError('Flow rate belongs on water or gas meters only.')
            if utility != 'water' and any(water_only):
                raise ValidationError('Water measures belong on water meters only.')
            if utility != 'gas' and (reading.pressure or reading.safety_observation):
                raise ValidationError('Gas measures belong on gas meters only.')
            if utility == 'water' and (reading.pressure or reading.safety_observation):
                raise ValidationError('Pressure and gas safety do not belong on a water meter.')
            if utility == 'gas' and any(water_only):
                raise ValidationError('Tank and water flow fields do not belong on a gas meter.')
            for value in (
                reading.voltage, reading.current, reading.demand_kw, reading.load_kw,
                reading.flow_rate, reading.inflow, reading.outflow, reading.pressure,
                reading.tank_level, reading.register_value, reading.interval_quantity,
            ):
                if value and value < 0:
                    raise ValidationError('Physical measures cannot be negative.')
            if reading.power_factor and (reading.power_factor < 0 or reading.power_factor > 1):
                raise ValidationError('Power factor must be between 0 and 1.')
            if reading.frequency and reading.frequency <= 0:
                raise ValidationError('Frequency must be greater than zero.')
            capacity = reading.meter_id.tank_capacity
            if reading.tank_level and capacity and reading.tank_level > capacity:
                raise ValidationError('Tank level cannot exceed tank capacity.')

    @api.constrains('meter_id', 'company_id', 'previous_reading_id', 'corrects_reading_id')
    def _check_company_match(self):
        for reading in self:
            if reading.meter_id.company_id != reading.company_id:
                raise ValidationError('Reading company must match the meter company.')
            for linked in (reading.previous_reading_id, reading.corrects_reading_id):
                if linked and linked.company_id != reading.company_id:
                    raise ValidationError('Linked readings must belong to the same company.')

    @api.constrains('meter_id', 'property_ref', 'site_ref', 'floor_ref', 'area_ref', 'department_ref')
    def _check_location_snapshot(self):
        for reading in self:
            meter = reading.meter_id
            for name in (
                'property_ref', 'site_ref', 'floor_ref', 'area_ref', 'department_ref',
            ):
                if (reading[name] or False) != (meter[name] or False):
                    raise ValidationError('Reading location is copied from the meter and then kept.')
