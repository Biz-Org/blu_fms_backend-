# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CcInvestigationNote(models.Model):
    _name = 'cc.investigation.note'
    _description = 'Command Center Investigation Note'
    _inherit = ['cc.mixin']
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    body = fields.Text(required=True)
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        readonly=True,
    )
    alert_id = fields.Many2one(
        'cc.alert',
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    incident_id = fields.Many2one(
        'cc.incident',
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        compute='_compute_company_id',
        store=True,
        index=True,
    )

    @api.depends('alert_id.company_id', 'incident_id.company_id')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.alert_id.company_id or rec.incident_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['user_id'] = self.env.uid
            if not str(vals.get('body') or '').strip():
                raise ValidationError('Investigation note body is required.')
            if not vals.get('alert_id') and not vals.get('incident_id'):
                raise ValidationError('An investigation note must be linked to an alert or an incident.')
        return super().create(vals_list)

    def write(self, vals):
        raise UserError('Investigation notes are append-only.')

    def unlink(self):
        self._cc_require_admin()
        return super().unlink()

    @api.constrains('body')
    def _check_body(self):
        for rec in self:
            if not (rec.body or '').strip():
                raise ValidationError('Investigation note body is required.')

    @api.constrains('alert_id', 'incident_id')
    def _check_parent(self):
        for rec in self:
            if not rec.alert_id and not rec.incident_id:
                raise ValidationError('An investigation note must be linked to an alert or an incident.')
            if rec.alert_id and rec.incident_id and rec.alert_id.company_id != rec.incident_id.company_id:
                raise ValidationError('Note alert and incident must belong to the same company.')
