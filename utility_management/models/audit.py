# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .mixin import staff_link
from .selections import AUDIT_EVENTS, AUDIT_OUTCOMES


class UtilityAuditEvent(models.Model):
    _name = 'utility.management.audit.event'
    _description = 'Utility Audit Event'
    _inherit = ['utility.management.mixin']
    _order = 'occurred_at desc, id desc'
    _check_company_auto = True

    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, ondelete='restrict')
    event_type = fields.Selection(AUDIT_EVENTS, required=True, index=True)
    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer()
    outcome = fields.Selection(AUDIT_OUTCOMES, required=True, index=True)
    summary = fields.Char(required=True)
    data_before = fields.Json()
    data_after = fields.Json()
    allowed_staff_ids = staff_link('utility_audit_staff_rel', 'audit_id')

    def _utility_candidate_users(self):
        self.ensure_one()
        users = self.user_id
        if self.model_name in self.env and self.res_id:
            target = self.env[self.model_name].sudo().browse(self.res_id).exists()
            if target and 'allowed_staff_ids' in target._fields:
                users |= target.allowed_staff_ids
            elif target and hasattr(target, '_utility_candidate_users'):
                users |= target._utility_candidate_users()
        return users

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_audit_service'):
            raise UserError('Audit events are created through the audit service.')
        records = super().create(vals_list)
        records._utility_sync_staff()
        return records

    def write(self, vals):
        if self.env.context.get('utility_staff_sync') and set(vals) <= {'allowed_staff_ids'}:
            return super().write(vals)
        raise UserError('Audit events cannot be changed.')

    def unlink(self):
        raise UserError('Audit events cannot be deleted.')
