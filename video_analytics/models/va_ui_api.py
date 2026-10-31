# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .va_mixin import DETECTION_TYPES


class VaUiApi(models.TransientModel):
    _name = 'va.ui.api'
    _description = 'Video Analytics UI API'
    _inherit = ['va.mixin']

    @api.model
    def get_session_context(self):
        user = self.env.user
        is_user = user.has_group('video_analytics.group_va_user')
        is_manager = user.has_group('video_analytics.group_va_manager')
        is_admin = user.has_group('video_analytics.group_va_admin')
        return {
            'uid': user.id,
            'name': user.name,
            'is_user': is_user,
            'is_manager': is_manager,
            'is_admin': is_admin,
            'can_manage_cameras': is_manager,
            'can_test_connection': is_manager,
            'can_ingest': is_manager,
            'can_resolve': is_manager,
            'can_reopen': is_admin,
            'can_assign_others': is_manager,
        }

    def _dt(self, value):
        return fields.Datetime.to_string(value) if value else False

    def _selection_label(self, record, fname):
        selection = record._fields[fname]._description_selection(self.env)
        return dict(selection).get(record[fname], record[fname] or '')

    def _camera_dict(self, camera, last_event=None):
        return {
            'id': camera.id,
            'name': camera.name,
            'code': camera.code,
            'location_label': camera.location_label or '',
            'status': camera.status,
            'status_label': self._selection_label(camera, 'status'),
            'stream_url': camera.stream_url or '',
            'stream_protocol': camera.stream_protocol,
            'stream_protocol_label': self._selection_label(camera, 'stream_protocol'),
            'last_seen': self._dt(camera.last_seen),
            'last_error': camera.last_error or '',
            'active': camera.active,
            'last_event_name': last_event.name if last_event else '',
            'last_event_label': self._selection_label(last_event, 'event_type') if last_event else '',
            'last_event_at': self._dt(last_event.create_date) if last_event else '',
        }

    def _zone_dict(self, zone):
        return {
            'id': zone.id,
            'name': zone.name,
            'code': zone.code,
            'capacity': zone.capacity,
            'occupancy_threshold_pct': zone.occupancy_threshold_pct,
            'current_count': zone.current_count,
            'current_occupancy_pct': zone.current_occupancy_pct,
            'over_threshold': zone.over_threshold,
            'active': zone.active,
            'camera_names': ', '.join(zone.camera_ids.mapped('display_name')) or '',
        }

    def _event_dict(self, event, notes=False):
        payload = {
            'id': event.id,
            'name': event.name,
            'event_type': event.event_type,
            'event_type_label': self._selection_label(event, 'event_type'),
            'severity': event.severity,
            'severity_label': self._selection_label(event, 'severity'),
            'state': event.state,
            'state_label': self._selection_label(event, 'state'),
            'confidence': event.confidence,
            'camera_id': event.camera_id.id or False,
            'camera_name': event.camera_id.display_name or '',
            'camera_code': event.camera_id.code or '',
            'location_label': event.camera_id.location_label or '',
            'zone_id': event.zone_id.id or False,
            'zone_name': event.zone_id.display_name or '',
            'detection_id': event.detection_id.id or False,
            'evidence_url': event.evidence_url or '',
            'playback_start': self._dt(event.playback_start),
            'playback_end': self._dt(event.playback_end),
            'user_id': event.user_id.id or False,
            'user_name': event.user_id.display_name or '',
            'create_date': self._dt(event.create_date),
            'is_alert_queue': event.is_alert_queue,
            'resolution_note': event.resolution_note or '',
        }
        if notes:
            payload['notes'] = [{
                'id': note.id,
                'body': note.body,
                'user_name': note.user_id.display_name or '',
                'create_date': self._dt(note.create_date),
            } for note in event.note_ids]
        return payload

    def _detection_dict(self, detection):
        return {
            'id': detection.id,
            'name': detection.name,
            'detection_type': detection.detection_type,
            'detection_type_label': self._selection_label(detection, 'detection_type'),
            'confidence': detection.confidence,
            'timestamp': self._dt(detection.timestamp),
            'state': detection.state,
            'state_label': self._selection_label(detection, 'state'),
            'camera_name': detection.camera_id.display_name or '',
            'zone_name': detection.zone_id.display_name or '',
            'evidence_url': detection.evidence_url or '',
            'external_id': detection.external_id or '',
            'skip_reason': detection.skip_reason or '',
            'event_id': detection.event_id.id or False,
            'event_severity': detection.event_id.severity or False,
        }

    def _snapshot_dict(self, snap):
        return {
            'id': snap.id,
            'zone_name': snap.zone_id.display_name or '',
            'camera_name': snap.camera_id.display_name or '',
            'timestamp': self._dt(snap.timestamp),
            'count': snap.count,
            'capacity': snap.capacity,
            'occupancy_pct': snap.occupancy_pct,
            'over_threshold': snap.over_threshold,
            'threshold_pct': snap.zone_id.occupancy_threshold_pct if snap.zone_id else 0,
            'event_id': snap.event_id.id or False,
            'event_name': snap.event_id.display_name or '',
        }

    def _assignable_users(self):
        group = self.env.ref('video_analytics.group_va_user')
        domain = [('groups_id', 'in', [group.id]), ('share', '=', False)]
        if not self.env.user.has_group('video_analytics.group_va_manager'):
            domain.append(('id', '=', self.env.uid))
        users = self.env['res.users'].search(domain)
        return [{'id': user.id, 'name': user.name} for user in users]

    def _event_domain(self, filters):
        filters = filters or {}
        domain = []
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('severity'):
            domain.append(('severity', '=', filters['severity']))
        if filters.get('event_type'):
            domain.append(('event_type', '=', filters['event_type']))
        if filters.get('camera_id'):
            domain.append(('camera_id', '=', int(filters['camera_id'])))
        if filters.get('zone_id'):
            domain.append(('zone_id', '=', int(filters['zone_id'])))
        if filters.get('user_id'):
            domain.append(('user_id', '=', int(filters['user_id'])))
        if filters.get('date_from'):
            domain.append(('create_date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('create_date', '<=', filters['date_to']))
        search = (filters.get('search') or '').strip()
        if search:
            domain += ['|', '|', ('name', 'ilike', search), ('event_type', 'ilike', search), ('evidence_url', 'ilike', search)]
        return domain

    @api.model
    def get_dashboard_data(self):
        self._va_require_user()
        Camera = self.env['va.camera']
        Event = self.env['va.event']
        Detection = self.env['va.detection']
        Zone = self.env['va.zone']
        cameras_total = Camera.search_count([])
        cameras_online = Camera.search_count([('status', '=', 'online'), ('active', '=', True)])
        cameras_offline = Camera.search_count([('status', '=', 'offline')])
        cameras_degraded = Camera.search_count([('status', '=', 'degraded')])
        cameras_inactive = Camera.search_count([('status', '=', 'inactive')])
        events_open = Event.search_count([('is_alert_queue', '=', True)])
        detections_total = Detection.search_count([])
        zones = Zone.search([], order='name')
        occupancy_current = sum(zones.mapped('current_count'))
        occupancy_capacity = sum(zones.mapped('capacity'))
        zones_over = len([zone for zone in zones if zone.over_threshold])
        recent_events = Event.search([], order='id desc', limit=8)
        recent_detections = Detection.search([], order='timestamp desc, id desc', limit=8)
        return {
            'kpis': {
                'cameras_total': cameras_total,
                'cameras_online': cameras_online,
                'cameras_offline': cameras_offline,
                'cameras_degraded': cameras_degraded,
                'cameras_inactive': cameras_inactive,
                'events_open': events_open,
                'detections_total': detections_total,
                'zones_over_threshold': zones_over,
                'events_intrusion': Event.search_count([('event_type', '=', 'intrusion'), ('is_alert_queue', '=', True)]),
                'events_fire': Event.search_count([('event_type', '=', 'fire_smoke'), ('is_alert_queue', '=', True)]),
                'events_ppe': Event.search_count([('event_type', '=', 'ppe_violation'), ('is_alert_queue', '=', True)]),
                'occupancy_current': occupancy_current,
                'occupancy_capacity': occupancy_capacity,
            },
            'zones': [self._zone_dict(zone) for zone in zones],
            'recent_events': [self._event_dict(event) for event in recent_events],
            'recent_detections': [self._detection_dict(det) for det in recent_detections],
        }

    @api.model
    def get_cctv_data(self, filters=None):
        self._va_require_user()
        filters = filters or {}
        domain = []
        if filters.get('status'):
            domain.append(('status', '=', filters['status']))
        if filters.get('active') is True:
            domain.append(('active', '=', True))
        if filters.get('active') is False:
            domain.append(('active', '=', False))
        search = (filters.get('search') or '').strip()
        if search:
            domain += ['|', '|', ('name', 'ilike', search), ('code', 'ilike', search), ('location_label', 'ilike', search)]
        cameras = self.env['va.camera'].search(domain, order='name, id')
        selected_id = int(filters['camera_id']) if filters.get('camera_id') else (cameras[:1].id if cameras else 0)
        selected = cameras.filtered(lambda cam: cam.id == selected_id)[:1]
        Event = self.env['va.event']
        last_by_cam = {}
        if cameras:
            for event in Event.search([('camera_id', 'in', cameras.ids)], order='id desc', limit=500):
                if event.camera_id.id not in last_by_cam:
                    last_by_cam[event.camera_id.id] = event
        since = fields.Datetime.now() - timedelta(hours=24)
        return {
            'kpis': {
                'cameras_total': self.env['va.camera'].search_count([]),
                'cameras_online': self.env['va.camera'].search_count([('status', '=', 'online'), ('active', '=', True)]),
                'cameras_offline': self.env['va.camera'].search_count([('status', '=', 'offline')]),
                'alerts_open': Event.search_count([('is_alert_queue', '=', True)]),
                'alerts_24h': Event.search_count([('create_date', '>=', since)]),
            },
            'cameras': [self._camera_dict(cam, last_by_cam.get(cam.id)) for cam in cameras],
            'selected': self._camera_dict(selected, last_by_cam.get(selected.id)) if selected else False,
        }

    @api.model
    def get_playback_data(self, filters=None):
        self._va_require_user()
        filters = filters or {}
        Event = self.env['va.event']
        events = Event.search(self._event_domain(filters), order='id desc', limit=100)
        selected_id = int(filters['event_id']) if filters.get('event_id') else (events[:1].id if events else 0)
        selected = Event.search([('id', '=', selected_id)], limit=1) if selected_id else events.browse()
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)
        events_today = Event.search_count([('create_date', '>=', today)])
        events_yesterday = Event.search_count([
            ('create_date', '>=', yesterday),
            ('create_date', '<', today),
        ])
        vs_yesterday = False
        if events_yesterday:
            vs_yesterday = int(round((events_today - events_yesterday) * 100.0 / events_yesterday))
        return {
            'kpis': {
                'events_today': events_today,
                'vs_yesterday': vs_yesterday,
                'under_review': Event.search_count([('state', '=', 'investigating')]),
                'confirmed': Event.search_count([('state', '=', 'resolved')]),
                'false_positives': Event.search_count([('state', '=', 'false_positive')]),
            },
            'events': [self._event_dict(event) for event in events],
            'selected': self._event_dict(selected, notes=True) if selected else False,
            'assignable_users': self._assignable_users(),
            'cameras': [{'id': cam.id, 'name': cam.display_name} for cam in self.env['va.camera'].search([], order='name')],
            'zones': [{'id': zone.id, 'name': zone.display_name} for zone in self.env['va.zone'].search([], order='name')],
        }

    @api.model
    def get_detection_data(self, filters=None):
        self._va_require_user()
        filters = filters or {}
        domain = []
        if filters.get('detection_type'):
            domain.append(('detection_type', '=', filters['detection_type']))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('camera_id'):
            domain.append(('camera_id', '=', int(filters['camera_id'])))
        if filters.get('zone_id'):
            domain.append(('zone_id', '=', int(filters['zone_id'])))
        Detection = self.env['va.detection']
        Camera = self.env['va.camera']
        Event = self.env['va.event']
        detections = Detection.search(domain, order='timestamp desc, id desc', limit=100)
        rules = self.env['va.detection.rule'].search([], order='name')
        zones = self.env['va.zone'].search([], order='name')
        cameras = Camera.search([], order='name')
        cameras_total = len(cameras)
        cameras_online = len(cameras.filtered(lambda cam: cam.status == 'online' and cam.active))
        ppe_domain = [('detection_type', '=', 'ppe_violation')]
        ppe_total = Detection.search_count(ppe_domain)
        ppe_new = Detection.search_count(ppe_domain + [('state', '=', 'new')])
        ppe_linked = Detection.search_count(ppe_domain + [('state', '=', 'linked')])
        ppe_dismissed = Detection.search_count(ppe_domain + [('state', '=', 'dismissed')])
        ppe_open = ppe_new + ppe_linked
        ppe_compliance = round(((ppe_total - ppe_open) / ppe_total) * 100.0, 1) if ppe_total else False
        health = round((cameras_online / cameras_total) * 100.0, 1) if cameras_total else 0.0
        now = fields.Datetime.now()
        day_ago = now - timedelta(hours=24)
        two_ago = now - timedelta(hours=48)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        recent_count = Detection.search_count([('timestamp', '>=', day_ago)])
        prior_count = Detection.search_count([
            ('timestamp', '>=', two_ago),
            ('timestamp', '<', day_ago),
        ])
        if prior_count:
            trend = int(round(((recent_count - prior_count) / float(prior_count)) * 100.0))
        else:
            trend = False
        type_counts_today = {
            dtype: Detection.search_count([
                ('detection_type', '=', dtype),
                ('timestamp', '>=', today_start),
            ])
            for dtype, _label in DETECTION_TYPES
        }
        thresholds = rules.mapped('confidence_threshold')
        confidence_threshold = max(thresholds) if thresholds else False
        return {
            'kpis': {
                'active_detections': Detection.search_count([('state', 'in', ['new', 'linked'])]),
                'active_trend_pct': trend,
                'critical_alerts': Event.search_count([
                    ('severity', '=', 'critical'),
                    ('create_date', '>=', day_ago),
                ]),
                'ppe_total': ppe_total,
                'ppe_new': ppe_new,
                'ppe_linked': ppe_linked,
                'ppe_dismissed': ppe_dismissed,
                'ppe_compliance': ppe_compliance,
                'system_health': health,
                'cameras_total': cameras_total,
                'cameras_online': cameras_online,
                'type_counts_today': type_counts_today,
                'confidence_threshold': confidence_threshold,
                'fps_label': '—',
                'ms_label': '—',
                'latency_label': '—',
            },
            'detections': [self._detection_dict(det) for det in detections],
            'zones': [self._zone_dict(zone) for zone in zones],
            'cameras': [{'id': cam.id, 'name': cam.display_name} for cam in cameras],
            'rules': [{
                'id': rule.id,
                'name': rule.name,
                'detection_type': rule.detection_type,
                'detection_type_label': self._selection_label(rule, 'detection_type'),
                'confidence_threshold': rule.confidence_threshold,
                'camera_name': rule.camera_id.display_name or 'Any',
                'zone_name': rule.zone_id.display_name or 'Any',
                'create_event': rule.create_event,
                'active': rule.active,
            } for rule in rules],
        }

    @api.model
    def get_occupancy_data(self):
        self._va_require_user()
        zones = self.env['va.zone'].search([], order='name')
        snapshots = self.env['va.occupancy.snapshot'].search([], order='timestamp desc, id desc', limit=50)
        occupancy_current = sum(zones.mapped('current_count'))
        occupancy_capacity = sum(zones.mapped('capacity'))
        pcts = [zone.current_occupancy_pct for zone in zones] if zones else []
        avg_density = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
        trend = list(reversed(snapshots[:12]))
        return {
            'kpis': {
                'occupancy_current': occupancy_current,
                'occupancy_capacity': occupancy_capacity,
                'zones_total': len(zones),
                'zones_active': len([zone for zone in zones if zone.current_count]),
                'crowd_events': self.env['va.event'].search_count([('event_type', '=', 'crowd_density')]),
                'avg_density': avg_density,
            },
            'zones': [self._zone_dict(zone) for zone in zones],
            'snapshots': [self._snapshot_dict(snap) for snap in snapshots],
            'trend': [self._snapshot_dict(snap) for snap in trend],
        }

    @api.model
    def get_alerts_data(self, filters=None):
        self._va_require_user()
        filters = filters or {}
        Event = self.env['va.event']
        events = Event.search(self._event_domain(filters), order='id desc', limit=100)
        selected_id = int(filters['event_id']) if filters.get('event_id') else (events[:1].id if events else 0)
        selected = Event.search([('id', '=', selected_id)], limit=1) if selected_id else Event
        return {
            'kpis': {
                'open': Event.search_count([('state', '=', 'open')]),
                'acknowledged': Event.search_count([('state', '=', 'acknowledged')]),
                'investigating': Event.search_count([('state', '=', 'investigating')]),
                'resolved': Event.search_count([('state', '=', 'resolved')]),
                'active': Event.search_count([('is_alert_queue', '=', True)]),
                'critical': Event.search_count([('severity', '=', 'critical'), ('is_alert_queue', '=', True)]),
                'warning': Event.search_count([('severity', 'in', ['medium', 'high']), ('is_alert_queue', '=', True)]),
                'resolved_today': Event.search_count([
                    ('state', '=', 'resolved'),
                    ('write_date', '>=', fields.Date.context_today(self)),
                ]),
            },
            'events': [self._event_dict(event) for event in events],
            'selected': self._event_dict(selected, notes=True) if selected else False,
            'assignable_users': self._assignable_users(),
            'cameras': [{'id': cam.id, 'name': cam.display_name} for cam in self.env['va.camera'].search([], order='name')],
            'zones': [{'id': zone.id, 'name': zone.display_name} for zone in self.env['va.zone'].search([], order='name')],
        }

    @api.model
    def run_event_action(self, event_id, action, extra=None):
        """Dispatch to existing lifecycle methods. extra may include note or user_id."""
        self._va_require_user()
        extra = extra or {}
        event = self.env['va.event'].browse(int(event_id))
        if not event.exists():
            raise UserError('Event was not found.')
        if action == 'acknowledge':
            event.action_acknowledge()
        elif action == 'investigate':
            event.action_investigate()
        elif action == 'assign':
            event.action_assign(int(extra.get('user_id') or 0))
        elif action == 'add_note':
            event.action_add_note(extra.get('body') or '')
        elif action == 'resolve':
            event.action_resolve(extra.get('note'))
        elif action == 'close':
            event.action_close()
        elif action == 'false_positive':
            event.action_false_positive(extra.get('note'))
        elif action == 'reopen':
            event.action_reopen()
        else:
            raise UserError('Unsupported event action.')
        return True

    @api.model
    def run_camera_action(self, camera_id, action, extra=None):
        self._va_require_user()
        extra = extra or {}
        camera = self.env['va.camera'].search([('id', '=', int(camera_id))], limit=1)
        if not camera:
            raise UserError('Camera was not found.')
        if action == 'test_connection':
            return camera.action_test_connection()
        if action == 'resolve_stream':
            return camera.action_resolve_stream()
        if action == 'set_status':
            return camera.action_set_status(extra.get('status'))
        raise UserError('Unsupported camera action.')
