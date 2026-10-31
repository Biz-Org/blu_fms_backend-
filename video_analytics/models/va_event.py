# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .va_mixin import DETECTION_TYPES, DETECTION_TYPE_VALUES, EVENT_STATES, SEVERITIES, SEVERITY_VALUES

_PROTECTED_FIELDS = {
    'state',
    'acknowledged_uid',
    'acknowledged_at',
    'resolved_uid',
    'resolved_at',
}


class VaEvent(models.Model):
    _name = 'va.event'
    _description = 'Video Event'
    _inherit = ['va.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, copy=False, index=True)
    event_type = fields.Selection(DETECTION_TYPES, required=True, index=True)
    severity = fields.Selection(SEVERITIES, required=True, default='medium', index=True)
    camera_id = fields.Many2one('va.camera', ondelete='restrict', index=True)
    zone_id = fields.Many2one('va.zone', ondelete='set null', index=True)
    detection_id = fields.Many2one('va.detection', ondelete='set null', index=True)
    confidence = fields.Float()
    evidence_url = fields.Char()
    playback_start = fields.Datetime()
    playback_end = fields.Datetime()
    user_id = fields.Many2one('res.users', string='Assignee', index=True, ondelete='set null')
    state = fields.Selection(EVENT_STATES, required=True, default='open', index=True)
    acknowledged_uid = fields.Many2one('res.users', ondelete='set null')
    acknowledged_at = fields.Datetime()
    resolved_uid = fields.Many2one('res.users', ondelete='set null')
    resolved_at = fields.Datetime()
    resolution_note = fields.Text()
    note_ids = fields.One2many('va.investigation.note', 'event_id', string='Investigation Notes')
    is_alert_queue = fields.Boolean(compute='_compute_is_alert_queue', store=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    @api.depends('state')
    def _compute_is_alert_queue(self):
        for rec in self:
            rec.is_alert_queue = rec.state in ('open', 'acknowledged', 'investigating')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('va.event') or 'VA-EVT'
        return super().create(vals_list)

    def write(self, vals):
        protected = _PROTECTED_FIELDS.intersection(vals)
        if protected and not self.env.context.get('va_lifecycle'):
            raise UserError('Event status fields can only be changed through lifecycle actions.')
        return super().write(vals)

    @api.constrains('confidence')
    def _check_confidence(self):
        for rec in self:
            if rec.confidence is False:
                continue
            if rec.confidence < 0 or rec.confidence > 100:
                raise ValidationError('Event confidence must be between 0 and 100.')

    @api.constrains('event_type')
    def _check_event_type(self):
        for rec in self:
            if rec.event_type not in DETECTION_TYPE_VALUES:
                raise ValidationError('Event type is not supported.')

    @api.constrains('severity')
    def _check_severity(self):
        for rec in self:
            if rec.severity not in SEVERITY_VALUES:
                raise ValidationError('Event severity is not supported.')

    def _lifecycle_write(self, vals):
        return self.with_context(va_lifecycle=True).write(vals)

    def action_acknowledge(self):
        self._va_require_user()
        for rec in self:
            if rec.state != 'open':
                raise UserError('Only open events can be acknowledged.')
            rec._lifecycle_write({
                'state': 'acknowledged',
                'acknowledged_uid': self.env.user.id,
                'acknowledged_at': fields.Datetime.now(),
            })
        return True

    def action_investigate(self):
        self._va_require_user()
        for rec in self:
            if rec.state not in ('open', 'acknowledged'):
                raise UserError('Only open or acknowledged events can move to investigating.')
            rec._lifecycle_write({'state': 'investigating'})
        return True

    def action_assign(self, user_id):
        self._va_require_user()
        user = self.env['res.users'].browse(user_id)
        if not user.exists():
            raise UserError('Assignee was not found.')
        if not user.has_group('video_analytics.group_va_user'):
            raise UserError('Assignee must be a Video Analytics user.')
        if not (user.company_ids & self.env.companies) and user.company_id not in self.env.companies:
            raise UserError('Assignee is not accessible in the current company.')
        if user.id != self.env.user.id:
            self._va_require_manager()
        self.write({'user_id': user.id})
        return True

    def action_add_note(self, body):
        self._va_require_user()
        self.ensure_one()
        if not (body or '').strip():
            raise UserError('Investigation note body is required.')
        self.env['va.investigation.note'].create({
            'event_id': self.id,
            'body': body,
        })
        return True

    def action_resolve(self, note=None):
        self._va_require_manager()
        for rec in self:
            if rec.state not in ('acknowledged', 'investigating'):
                raise UserError('Only verified or incident events can be resolved.')
            vals = {
                'state': 'resolved',
                'resolved_uid': self.env.user.id,
                'resolved_at': fields.Datetime.now(),
            }
            if note:
                vals['resolution_note'] = note
            rec._lifecycle_write(vals)
        return True

    def action_close(self):
        self._va_require_manager()
        for rec in self:
            if rec.state != 'resolved':
                raise UserError('Only resolved events can be closed.')
            rec._lifecycle_write({'state': 'closed'})
        return True

    def action_false_positive(self, note=None):
        self._va_require_manager()
        for rec in self:
            if rec.state not in ('open', 'acknowledged', 'investigating'):
                raise UserError('This event cannot be marked as a false positive.')
            vals = {
                'state': 'false_positive',
                'resolved_uid': self.env.user.id,
                'resolved_at': fields.Datetime.now(),
            }
            if note:
                vals['resolution_note'] = note
            rec._lifecycle_write(vals)
        return True

    def action_reopen(self):
        self._va_require_admin()
        for rec in self:
            if rec.state not in ('resolved', 'closed', 'false_positive'):
                raise UserError('Only resolved, closed, or false-positive events can be reopened.')
            rec._lifecycle_write({
                'state': 'open',
                'resolved_uid': False,
                'resolved_at': False,
            })
        return True
