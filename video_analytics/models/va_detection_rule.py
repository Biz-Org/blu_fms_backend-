# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .va_mixin import DETECTION_TYPES, SEVERITIES


class VaDetectionRule(models.Model):
    _name = 'va.detection.rule'
    _description = 'Detection Rule'
    _inherit = ['va.mixin']
    _order = 'name, id'

    name = fields.Char(required=True)
    detection_type = fields.Selection(DETECTION_TYPES, required=True, index=True)
    confidence_threshold = fields.Float(
        required=True,
        default=50.0,
        help='Minimum confidence (0–100) required to create an event.',
    )
    camera_id = fields.Many2one('va.camera', ondelete='cascade', index=True)
    zone_id = fields.Many2one('va.zone', ondelete='cascade', index=True)
    create_event = fields.Boolean(default=True)
    default_severity = fields.Selection(SEVERITIES, required=True, default='medium')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    @api.constrains('confidence_threshold')
    def _check_confidence_threshold(self):
        for rule in self:
            if rule.confidence_threshold < 0 or rule.confidence_threshold > 100:
                raise ValidationError('Confidence threshold must be between 0 and 100.')

    def find_matching_rule(self, detection_type, camera=None, zone=None):
        """Return the best active rule for a detection.

        Matching specificity (highest wins):
        1. camera + zone
        2. camera only
        3. zone only
        4. global (no camera, no zone)

        Tie-break: higher confidence_threshold, then lower id.
        Used by detection ingestion; does not execute dynamic code.
        """
        camera_id = camera.id if camera else False
        zone_id = zone.id if zone else False
        rules = self.search([
            ('active', '=', True),
            ('detection_type', '=', detection_type),
        ])

        def score(rule):
            if rule.camera_id and rule.zone_id:
                if rule.camera_id.id == camera_id and rule.zone_id.id == zone_id:
                    return (4, rule.confidence_threshold, -rule.id)
                return (-1, 0, 0)
            if rule.camera_id:
                if rule.camera_id.id == camera_id:
                    return (3, rule.confidence_threshold, -rule.id)
                return (-1, 0, 0)
            if rule.zone_id:
                if rule.zone_id.id == zone_id:
                    return (2, rule.confidence_threshold, -rule.id)
                return (-1, 0, 0)
            return (1, rule.confidence_threshold, -rule.id)

        ranked = [rule for rule in rules if score(rule)[0] >= 0]
        if not ranked:
            return self.browse()
        ranked.sort(key=score, reverse=True)
        return ranked[0]
