# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EiSyncRecord(models.Model):
    _name = 'ei.sync.record'
    _description = 'Synchronization Record Result'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    run_id = fields.Many2one('ei.sync.run', required=True, ondelete='cascade', index=True)
    external_id = fields.Char(index=True)
    external_ref = fields.Char(string='External Reference', index=True)
    correlation_id = fields.Char(index=True)
    state = fields.Selection(
        [
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('conflict', 'Conflict'),
            ('skipped', 'Skipped'),
        ],
        default='success',
        required=True,
        index=True,
    )
    error_message = fields.Text()
    payload_summary = fields.Text()
    is_duplicate = fields.Boolean(default=False, index=True)
    company_id = fields.Many2one(
        related='run_id.company_id', store=True, readonly=True, index=True,
    )

    @api.depends('external_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.external_id or f'Record {rec.id or ""}'
