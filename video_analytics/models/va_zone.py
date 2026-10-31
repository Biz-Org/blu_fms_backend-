# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VaZone(models.Model):
    _name = 'va.zone'
    _description = 'Zone'
    _inherit = ['va.mixin']
    _order = 'name, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    capacity = fields.Integer(required=True, default=1, help='Maximum occupancy for this zone.')
    occupancy_threshold_pct = fields.Float(
        required=True,
        default=80.0,
        help='Alert when occupancy percentage reaches this value (0–100).',
    )
    camera_ids = fields.Many2many(
        'va.camera',
        'va_zone_camera_rel',
        'zone_id',
        'camera_id',
        string='Cameras',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    active = fields.Boolean(default=True)
    snapshot_ids = fields.One2many('va.occupancy.snapshot', 'zone_id')
    current_count = fields.Integer(compute='_compute_current_occupancy')
    current_occupancy_pct = fields.Float(compute='_compute_current_occupancy')
    over_threshold = fields.Boolean(compute='_compute_current_occupancy')

    _sql_constraints = [
        ('code_company_uniq', 'unique(company_id, code)', 'Zone code must be unique per company.'),
    ]

    @api.depends(
        'snapshot_ids',
        'snapshot_ids.count',
        'snapshot_ids.occupancy_pct',
        'snapshot_ids.over_threshold',
        'snapshot_ids.timestamp',
    )
    def _compute_current_occupancy(self):
        Snapshot = self.env['va.occupancy.snapshot']
        for zone in self:
            snap = Snapshot.search(
                [('zone_id', '=', zone.id)],
                order='timestamp desc, id desc',
                limit=1,
            )
            if snap:
                zone.current_count = snap.count
                zone.current_occupancy_pct = snap.occupancy_pct
                zone.over_threshold = snap.over_threshold
            else:
                zone.current_count = 0
                zone.current_occupancy_pct = 0.0
                zone.over_threshold = False

    @api.constrains('capacity')
    def _check_capacity(self):
        for zone in self:
            if zone.capacity <= 0:
                raise ValidationError('Zone capacity must be greater than 0.')

    @api.constrains('occupancy_threshold_pct')
    def _check_threshold(self):
        for zone in self:
            if zone.occupancy_threshold_pct < 0 or zone.occupancy_threshold_pct > 100:
                raise ValidationError('Occupancy threshold must be between 0 and 100.')
