# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .mixin import staff_link
from .selections import LEAK_ENTRY_KINDS, LEAK_SEVERITIES, LEAK_STATES, LEAK_TRANSITIONS, LEAK_TYPES


class UtilityLeak(models.Model):
    _name = 'utility.management.leak'
    _description = 'Utility Leak'
    _inherit = ['utility.management.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'detected_at desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default='/', index=True)
    leak_type = fields.Selection(LEAK_TYPES, required=True, index=True)
    severity = fields.Selection(LEAK_SEVERITIES, required=True, index=True)
    state = fields.Selection(LEAK_STATES, required=True, default='detected', index=True)
    detected_at = fields.Datetime(required=True, index=True)
    response_at = fields.Datetime()
    resolved_at = fields.Datetime()
    closed_at = fields.Datetime()
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
    assignee_id = fields.Many2one('res.users', index=True, ondelete='set null')
    affected_consumption = fields.Float()
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
    action_ids = fields.One2many('utility.management.leak.action', 'leak_id')
    allowed_staff_ids = staff_link('utility_leak_staff_rel', 'leak_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_leak_service'):
            raise UserError('Leaks are created through the leak service.')
        for vals in vals_list:
            if vals.get('name', '/') in (False, '/'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.management.leak') or '/'
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        if not self.env.context.get('utility_leak_service'):
            raise UserError('Leaks are changed through the leak service.')
        if 'state' in vals:
            for leak in self:
                if vals['state'] not in LEAK_TRANSITIONS.get(leak.state, set()):
                    raise UserError('Leak cannot move from %s to %s.' % (leak.state, vals['state']))
        result = super().write(vals)
        if not self.env.context.get('utility_staff_sync'):
            self._utility_sync_staff()
        return result

    @api.constrains('meter_id', 'reading_id', 'company_id')
    def _check_company_match(self):
        for leak in self:
            if leak.meter_id and leak.meter_id.company_id != leak.company_id:
                raise ValidationError('Leak company must match the meter company.')
            if leak.reading_id and leak.reading_id.company_id != leak.company_id:
                raise ValidationError('Leak company must match the reading company.')

    @api.constrains('affected_consumption')
    def _check_consumption(self):
        for leak in self:
            if leak.affected_consumption and leak.affected_consumption < 0:
                raise ValidationError('Affected consumption cannot be negative.')


class UtilityLeakAction(models.Model):
    _name = 'utility.management.leak.action'
    _description = 'Utility Leak Action'
    _inherit = ['utility.management.mixin']
    _order = 'occurred_at, id'
    _check_company_auto = True

    leak_id = fields.Many2one(
        'utility.management.leak',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    entry_kind = fields.Selection(LEAK_ENTRY_KINDS, required=True, index=True)
    note = fields.Text(required=True)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, ondelete='restrict')
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now)
    allowed_staff_ids = staff_link('utility_leak_action_staff_rel', 'action_id')

    def _utility_candidate_users(self):
        self.ensure_one()
        return self.leak_id._utility_candidate_users() | self.user_id

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_leak_service'):
            raise UserError('Leak actions are created through the leak service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        raise UserError('Leak actions cannot be changed.')

    def unlink(self):
        raise UserError('Leak actions cannot be deleted.')

    @api.constrains('leak_id', 'company_id')
    def _check_company_match(self):
        for action in self:
            if action.leak_id.company_id != action.company_id:
                raise ValidationError('Leak action company must match the leak company.')
