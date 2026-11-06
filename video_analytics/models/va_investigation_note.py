# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class VaInvestigationNote(models.Model):
    _name = 'va.investigation.note'
    _description = 'Investigation Note'
    _inherit = ['va.mixin']
    _order = 'create_date desc, id desc'

    event_id = fields.Many2one('va.event', required=True, ondelete='cascade', index=True)
    body = fields.Text(required=True)
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        related='event_id.company_id',
        store=True,
        index=True,
    )

    def write(self, vals):
        raise UserError('Investigation notes are append-only.')

    def unlink(self):
        self._va_require_admin()
        return super().unlink()
