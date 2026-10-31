# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

from .va_mixin import CAMERA_STATUSES, STREAM_PROTOCOLS

_STATUS_FIELDS = {'status', 'last_seen', 'last_error'}


class VaCamera(models.Model):
    _name = 'va.camera'
    _description = 'Camera'
    _inherit = ['va.mixin']
    _order = 'name, id'
    _rec_name = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    location_label = fields.Char(help='Free-text location. Not a Property/Building/Floor record.')
    external_id = fields.Char(index=True, help='Future CCTV or Enterprise Integration identifier.')
    status = fields.Selection(CAMERA_STATUSES, required=True, default='inactive', index=True)
    stream_url = fields.Char(help='Optional playback URL. RTSP is stored but not played in the browser.')
    stream_protocol = fields.Selection(STREAM_PROTOCOLS, required=True, default='none')
    last_seen = fields.Datetime()
    last_error = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    zone_ids = fields.Many2many(
        'va.zone',
        'va_zone_camera_rel',
        'camera_id',
        'zone_id',
        string='Zones',
    )

    _sql_constraints = [
        ('code_company_uniq', 'unique(company_id, code)', 'Camera code must be unique per company.'),
    ]

    def write(self, vals):
        if _STATUS_FIELDS.intersection(vals) and not self.env.context.get('va_camera_status'):
            raise UserError('Camera operational status can only be changed through approved service methods.')
        return super().write(vals)

    def action_test_connection(self):
        from odoo.addons.video_analytics.services.cctv import service
        self.ensure_one()
        return service.test_connection(self)

    def action_resolve_stream(self):
        from odoo.addons.video_analytics.services.cctv import service
        self.ensure_one()
        return service.resolve_stream(self)

    def action_set_status(self, status):
        from odoo.addons.video_analytics.services.cctv import service
        self.ensure_one()
        return service.set_status(self, status)
