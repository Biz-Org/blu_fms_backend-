# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VaOccupancySnapshot(models.Model):
    _name = 'va.occupancy.snapshot'
    _description = 'Occupancy Snapshot'
    _inherit = ['va.mixin']
    _order = 'timestamp desc, id desc'

    zone_id = fields.Many2one('va.zone', required=True, ondelete='cascade', index=True)
    camera_id = fields.Many2one('va.camera', ondelete='set null', index=True)
    timestamp = fields.Datetime(required=True, index=True)
    count = fields.Integer(required=True)
    capacity = fields.Integer(required=True, help='Capacity copied from the zone at ingest time.')
    occupancy_pct = fields.Float(compute='_compute_occupancy_pct', store=True)
    over_threshold = fields.Boolean(compute='_compute_over_threshold', store=True)
    event_id = fields.Many2one('va.event', ondelete='set null', index=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    @api.model_create_multi
    def create(self, vals_list):
        Zone = self.env['va.zone']
        for vals in vals_list:
            if vals.get('zone_id') and not vals.get('capacity'):
                vals['capacity'] = Zone.browse(vals['zone_id']).capacity
            if vals.get('zone_id') and not vals.get('company_id'):
                vals['company_id'] = Zone.browse(vals['zone_id']).company_id.id
        return super().create(vals_list)

    @api.depends('count', 'capacity')
    def _compute_occupancy_pct(self):
        for rec in self:
            if rec.capacity:
                rec.occupancy_pct = round(100.0 * rec.count / rec.capacity, 2)
            else:
                rec.occupancy_pct = 0.0

    @api.depends('occupancy_pct', 'zone_id', 'zone_id.occupancy_threshold_pct')
    def _compute_over_threshold(self):
        for rec in self:
            threshold = rec.zone_id.occupancy_threshold_pct if rec.zone_id else 0.0
            rec.over_threshold = rec.occupancy_pct >= threshold

    @api.constrains('count')
    def _check_count(self):
        for rec in self:
            if rec.count < 0:
                raise ValidationError('Occupancy count cannot be negative.')

    @api.constrains('capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.capacity <= 0:
                raise ValidationError('Occupancy capacity must be greater than 0.')

    @api.model
    def ingest(self, vals):
        from odoo.addons.video_analytics.services import occupancy_ingest
        return occupancy_ingest.ingest(self.env, vals)
