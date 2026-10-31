# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .mixin import staff_link
from .selections import HEALTH_VALUES, METER_STATUSES


class UtilityConnectivity(models.Model):
    _name = 'utility.management.connectivity'
    _description = 'Meter Connectivity History'
    _inherit = ['utility.management.mixin']
    _order = 'observed_at desc, id desc'
    _check_company_auto = True

    meter_id = fields.Many2one(
        'utility.management.meter',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    observed_at = fields.Datetime(required=True, index=True)
    status = fields.Selection(METER_STATUSES, required=True, index=True)
    health = fields.Selection(HEALTH_VALUES, required=True, default='unknown')
    error_message = fields.Char()
    response_ms = fields.Integer()
    allowed_staff_ids = staff_link('utility_connectivity_staff_rel', 'connectivity_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_connectivity_log'):
            raise UserError('Connectivity history is written by the meter service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def _utility_candidate_users(self):
        users = self.env['res.users']
        for record in self:
            users |= record.meter_id._utility_candidate_users()
        return users

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        raise UserError('Connectivity history cannot be changed.')

    def unlink(self):
        raise UserError('Connectivity history cannot be deleted.')

    @api.constrains('meter_id', 'company_id')
    def _check_company_match(self):
        for record in self:
            if record.meter_id.company_id != record.company_id:
                raise ValidationError('Connectivity company must match the meter company.')
