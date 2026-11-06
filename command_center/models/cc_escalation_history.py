# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .cc_mixin import ESCALATION_RESULT_VALUES, ESCALATION_RESULTS


class CcEscalationHistory(models.Model):
    _name = 'cc.escalation.history'
    _description = 'Command Center Escalation History'
    _inherit = ['cc.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char()
    alert_id = fields.Many2one(
        'cc.alert',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    rule_id = fields.Many2one(
        'cc.escalation.rule',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    level = fields.Integer()
    timestamp = fields.Datetime(default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', ondelete='set null', index=True)
    group_id = fields.Many2one('res.groups', ondelete='set null')
    result = fields.Selection(ESCALATION_RESULTS, index=True)
    actor_id = fields.Many2one('res.users', ondelete='set null')
    note = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        related='alert_id.company_id',
        store=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = 'Escalation'
        return super().create(vals_list)

    @api.constrains('result')
    def _check_result(self):
        for rec in self:
            if rec.result and rec.result not in ESCALATION_RESULT_VALUES:
                raise ValidationError('Escalation result is not supported.')

    @api.constrains('rule_id', 'alert_id')
    def _check_rule_company(self):
        for rec in self:
            if rec.rule_id and rec.alert_id and rec.rule_id.company_id != rec.alert_id.company_id:
                raise ValidationError('Escalation history rule company must match the alert company.')
