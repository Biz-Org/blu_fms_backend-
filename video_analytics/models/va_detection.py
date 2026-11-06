# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .va_mixin import DETECTION_STATES, DETECTION_TYPES, DETECTION_TYPE_VALUES


class VaDetection(models.Model):
    _name = 'va.detection'
    _description = 'AI Detection'
    _inherit = ['va.mixin']
    _order = 'timestamp desc, id desc'

    name = fields.Char(required=True, copy=False, index=True)
    external_id = fields.Char(index=True, help='Provider idempotency key.')
    detection_type = fields.Selection(DETECTION_TYPES, required=True, index=True)
    confidence = fields.Float(required=True)
    timestamp = fields.Datetime(required=True, index=True)
    camera_id = fields.Many2one('va.camera', required=True, ondelete='restrict', index=True)
    zone_id = fields.Many2one('va.zone', ondelete='set null', index=True)
    rule_id = fields.Many2one('va.detection.rule', ondelete='set null', index=True)
    event_id = fields.Many2one('va.event', ondelete='set null', index=True)
    evidence_url = fields.Char()
    state = fields.Selection(DETECTION_STATES, required=True, default='new', index=True)
    skip_reason = fields.Char()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('va.detection') or 'VA-DET'
        return super().create(vals_list)

    @api.constrains('confidence')
    def _check_confidence(self):
        for rec in self:
            if rec.confidence < 0 or rec.confidence > 100:
                raise ValidationError('Detection confidence must be between 0 and 100.')

    @api.constrains('detection_type')
    def _check_detection_type(self):
        for rec in self:
            if rec.detection_type not in DETECTION_TYPE_VALUES:
                raise ValidationError('Detection type is not supported.')

    @api.constrains('external_id', 'company_id')
    def _check_external_id_unique(self):
        for rec in self:
            if not rec.external_id:
                continue
            domain = [
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('external_id', '=', rec.external_id),
            ]
            if self.search_count(domain):
                raise ValidationError('Detection external ID must be unique per company.')

    @api.model
    def ingest(self, vals):
        from odoo.addons.video_analytics.services import detection_ingest
        return detection_ingest.ingest(self.env, vals)
