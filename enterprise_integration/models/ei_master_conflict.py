# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EiMasterConflict(models.Model):
    _name = 'ei.master.conflict'
    _description = 'Master Data Conflict'
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(required=True, default='Conflict', index=True)
    mapping_id = fields.Many2one('ei.master.mapping', required=True, ondelete='cascade', index=True)
    state = fields.Selection(
        [
            ('conflict', 'Conflict'),
            ('resolved', 'Resolved'),
            ('ignored', 'Ignored'),
        ],
        default='conflict',
        required=True,
        index=True,
    )
    left_payload = fields.Text()
    right_payload = fields.Text()
    resolution = fields.Text()
    resolved_by = fields.Many2one('res.users')
    resolved_at = fields.Datetime()
    is_duplicate = fields.Boolean(default=False, index=True)
    external_ref = fields.Char(string='External Reference', index=True)
    company_id = fields.Many2one(
        related='mapping_id.company_id', store=True, readonly=True, index=True,
    )

    def action_ignore(self):
        self.check_access('write')
        self.write({'state': 'ignored'})
