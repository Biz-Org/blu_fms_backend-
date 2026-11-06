# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .mixin import staff_link
from .selections import (
    HEALTH_VALUES,
    LOCATION_FIELDS,
    MANAGER_GROUP,
    METER_ROLES,
    METER_STATUSES,
    METER_TRANSITIONS,
    PROTOCOLS,
    READING_MODES,
    UTILITY_TYPES,
)


class UtilityMeter(models.Model):
    _name = 'utility.management.meter'
    _description = 'Utility Meter'
    _inherit = ['utility.management.mixin']
    _order = 'meter_code, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    meter_code = fields.Char(required=True, index=True)
    serial_number = fields.Char(index=True)
    utility_type = fields.Selection(UTILITY_TYPES, required=True, index=True)
    meter_role = fields.Selection(METER_ROLES, required=True, default='consumption', index=True)
    reading_mode = fields.Selection(READING_MODES, required=True, default='cumulative')
    manufacturer = fields.Char()
    model = fields.Char()
    uom = fields.Char()
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
    protocol = fields.Selection(PROTOCOLS, required=True, default='manual')
    connection_config = fields.Json()
    sync_frequency_minutes = fields.Integer(default=60)
    status = fields.Selection(METER_STATUSES, required=True, default='connecting', index=True)
    health = fields.Selection(HEALTH_VALUES, required=True, default='unknown', index=True)
    last_sync = fields.Datetime(index=True)
    health_note = fields.Char()
    battery_percent = fields.Float()
    firmware = fields.Char()
    anomaly_enabled = fields.Boolean(default=False)
    anomaly_percent = fields.Float()
    tank_capacity = fields.Float()
    power_source_id = fields.Many2one(
        'utility.management.power.source',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    active = fields.Boolean(default=True)
    allowed_staff_ids = staff_link('utility_meter_staff_rel', 'meter_id')
    reading_ids = fields.One2many('utility.management.reading', 'meter_id')
    connectivity_ids = fields.One2many('utility.management.connectivity', 'meter_id')

    _sql_constraints = [
        (
            'meter_code_company_uniq',
            'unique(company_id, meter_code)',
            'Meter code must be unique per company.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError('Only a Facility Manager can register a meter.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if (
            not self.env.su
            and not self.env.context.get('utility_staff_sync')
            and not self.env.user.has_group(MANAGER_GROUP)
        ):
            raise AccessError('Only a Facility Manager can modify a meter.')
        if 'status' in vals and not self.env.context.get('utility_meter_status'):
            raise UserError('Meter status can only be changed through the meter service.')
        if 'status' in vals:
            for meter in self:
                new_status = vals['status']
                if new_status not in METER_TRANSITIONS.get(meter.status, set()):
                    raise UserError(
                        'Meter cannot move from %s to %s.' % (meter.status, new_status)
                    )
        result = super().write(vals)
        if not self.env.context.get('utility_staff_sync'):
            watched = set(LOCATION_FIELDS) | {'company_id'}
            if watched.intersection(vals):
                self._utility_sync_staff()
        return result

    @api.constrains('meter_role', 'tank_capacity')
    def _check_tank_capacity(self):
        for meter in self:
            if meter.meter_role == 'tank' and (not meter.tank_capacity or meter.tank_capacity <= 0):
                raise ValidationError('A tank meter requires tank capacity greater than zero.')

    @api.constrains('battery_percent', 'anomaly_percent', 'sync_frequency_minutes')
    def _check_meter_numbers(self):
        for meter in self:
            if meter.battery_percent and (meter.battery_percent < 0 or meter.battery_percent > 100):
                raise ValidationError('Battery percent must be between 0 and 100.')
            if meter.anomaly_percent and meter.anomaly_percent < 0:
                raise ValidationError('Anomaly percent cannot be negative.')
            if meter.sync_frequency_minutes is not None and meter.sync_frequency_minutes < 0:
                raise ValidationError('Sync frequency cannot be negative.')

    @api.constrains('power_source_id', 'company_id')
    def _check_power_company(self):
        for meter in self:
            if meter.power_source_id and meter.power_source_id.company_id != meter.company_id:
                raise ValidationError('Power source must belong to the meter company.')
