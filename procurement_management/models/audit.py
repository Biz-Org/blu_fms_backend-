# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.common import AUDIT_CTX


class ProcurementAuditEvent(models.Model):
    _name = 'procurement.management.audit.event'
    _description = 'Procurement Audit Event'
    _order = 'id desc'

    event_time = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    action = fields.Selection(
        [
            ('created', 'Created'),
            ('modified', 'Modified'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('deleted', 'Deleted'),
            ('synced', 'Synced'),
        ],
        required=True,
        index=True,
    )
    status = fields.Selection(
        [('success', 'Success'), ('denied', 'Denied')],
        required=True,
        default='success',
        index=True,
    )
    res_model = fields.Char(index=True)
    reference = fields.Char()
    before_value = fields.Text()
    after_value = fields.Text()
    detail = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self.check_access('create')
        if not self.env.context.get(AUDIT_CTX):
            raise UserError('Audit events are written by the procurement workflow.')
        return super().create(vals_list)

    def write(self, vals):
        raise UserError('Audit events cannot be modified.')

    def unlink(self):
        raise UserError('Audit events cannot be deleted.')
