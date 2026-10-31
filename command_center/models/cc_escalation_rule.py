# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import ESCALATION_MODE_VALUES, ESCALATION_MODES


class CcEscalationRule(models.Model):
    _name = 'cc.escalation.rule'
    _description = 'Command Center Escalation Rule'
    _inherit = ['cc.mixin']
    _order = 'level, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    level = fields.Integer(default=1, index=True)
    delay_minutes = fields.Integer()
    mode = fields.Selection(ESCALATION_MODES, default='manual')
    user_id = fields.Many2one('res.users', ondelete='set null', index=True)
    group_id = fields.Many2one('res.groups', ondelete='set null')
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    site_id = fields.Many2one(
        'cc.site',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    history_ids = fields.One2many('cc.escalation.history', 'rule_id')

    @api.constrains('level')
    def _check_level(self):
        for rec in self:
            if rec.level < 0:
                raise ValidationError('Escalation level must be greater than or equal to 0.')

    @api.constrains('delay_minutes')
    def _check_delay_minutes(self):
        for rec in self:
            if rec.delay_minutes < 0:
                raise ValidationError('Escalation delay must be greater than or equal to 0.')

    @api.constrains('mode')
    def _check_mode(self):
        for rec in self:
            if rec.mode and rec.mode not in ESCALATION_MODE_VALUES:
                raise ValidationError('Escalation mode is not supported.')

    @api.constrains('site_id', 'company_id')
    def _check_site_company(self):
        for rec in self:
            if rec.site_id and rec.site_id.company_id != rec.company_id:
                raise ValidationError('Escalation rule company must match the selected site company.')
