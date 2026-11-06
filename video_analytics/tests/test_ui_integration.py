# -*- coding: utf-8 -*-
"""Phase 5 UI API / ORM integration tests (no fake production data)."""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'va_ui')
class TestVaUiIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.api = self.env['va.ui.api']
        self.company_b = self.env['res.company'].create({'name': 'VA UI Other'})
        self.user = self.env['res.users'].create({
            'name': 'VA UI User',
            'login': 'va_ui_user',
            'groups_id': [(6, 0, [self.env.ref('video_analytics.group_va_user').id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        self.manager = self.env['res.users'].create({
            'name': 'VA UI Manager',
            'login': 'va_ui_manager',
            'groups_id': [(6, 0, [self.env.ref('video_analytics.group_va_manager').id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })

    def test_dashboard_empty_zeros_not_fake(self):
        data = self.api.get_dashboard_data()
        self.assertEqual(data['kpis']['cameras_total'], self.env['va.camera'].search_count([]))
        self.assertEqual(data['kpis']['cameras_online'], self.env['va.camera'].search_count([
            ('status', '=', 'online'), ('active', '=', True),
        ]))
        self.assertEqual(len(data['recent_events']), min(8, self.env['va.event'].search_count([])))
        self.assertNotIn('fake', str(data).lower())
        self.assertNotIn('demo', str(data['kpis']).lower())

    def test_camera_and_event_and_detection_lists(self):
        camera = self.env['va.camera'].create({'name': 'UI Cam', 'code': 'CAM-UI'})
        zone = self.env['va.zone'].create({'name': 'UI Zone', 'code': 'ZN-UI', 'capacity': 10})
        event = self.env['va.event'].create({
            'event_type': 'intrusion',
            'camera_id': camera.id,
            'zone_id': zone.id,
        })
        detection = self.env['va.detection'].create({
            'detection_type': 'intrusion',
            'confidence': 40,
            'timestamp': fields.Datetime.now(),
            'camera_id': camera.id,
        })
        cctv = self.api.get_cctv_data({})
        self.assertTrue(any(row['id'] == camera.id for row in cctv['cameras']))
        playback = self.api.get_playback_data({})
        self.assertTrue(any(row['id'] == event.id for row in playback['events']))
        detections = self.api.get_detection_data({})
        self.assertTrue(any(row['id'] == detection.id for row in detections['detections']))
        occupancy = self.api.get_occupancy_data()
        self.assertTrue(any(row['id'] == zone.id for row in occupancy['zones']))
        self.assertEqual(occupancy['snapshots'], occupancy['snapshots'])

    def test_empty_occupancy_snapshots(self):
        data = self.api.get_occupancy_data()
        self.assertIn('snapshots', data)
        self.assertIsInstance(data['snapshots'], list)

    def test_rpc_error_unknown_action(self):
        event = self.env['va.event'].create({'event_type': 'intrusion'})
        with self.assertRaises(UserError):
            self.api.run_event_action(event.id, 'not_an_action', {})
        with self.assertRaises(UserError):
            self.api.run_event_action(0, 'acknowledge', {})

    def test_user_cannot_test_camera_connection(self):
        camera = self.env['va.camera'].create({'name': 'User Cam', 'code': 'CAM-UI-U'})
        with self.assertRaises(AccessError):
            self.api.with_user(self.user).run_camera_action(camera.id, 'test_connection')

    def test_camera_test_action_reaches_server_method(self):
        camera = self.env['va.camera'].create({'name': 'Stub Cam', 'code': 'CAM-STUB'})
        result = self.api.with_user(self.manager).run_camera_action(camera.id, 'test_connection')
        self.assertEqual(result['mode'], 'stub')
        self.assertEqual(result['status'], 'offline')

    def test_event_lifecycle_via_ui_api(self):
        event = self.env['va.event'].create({'event_type': 'intrusion'})
        self.api.with_user(self.user).run_event_action(event.id, 'acknowledge', {})
        self.assertEqual(event.state, 'acknowledged')
        with self.assertRaises(AccessError):
            self.api.with_user(self.user).run_event_action(event.id, 'resolve', {'note': 'no'})
        self.api.with_user(self.manager).run_event_action(event.id, 'resolve', {'note': 'ok'})
        self.assertEqual(event.state, 'resolved')

    def test_restricted_actions_not_available_to_user_session(self):
        session = self.api.with_user(self.user).get_session_context()
        self.assertFalse(session['can_resolve'])
        self.assertFalse(session['can_reopen'])
        self.assertFalse(session['can_test_connection'])
        manager = self.api.with_user(self.manager).get_session_context()
        self.assertTrue(manager['can_resolve'])
        self.assertTrue(manager['can_test_connection'])

    def test_multi_company_ui_isolation(self):
        other = self.env['va.camera'].create({
            'name': 'Other UI Cam',
            'code': 'CAM-UI-B',
            'company_id': self.company_b.id,
        })
        data = self.api.with_user(self.user).get_cctv_data({})
        self.assertFalse(any(row['id'] == other.id for row in data['cameras']))

    def test_js_uses_ui_api_not_fake_engine(self):
        root = __import__('pathlib').Path(__file__).resolve().parents[1]
        js = (root / 'static' / 'src' / 'js' / 'screens' / 'va_dashboard.js').read_text(encoding='utf-8')
        self.assertIn('get_dashboard_data', js)
        self.assertNotIn('fakeKpi', js)
        app = (root / 'static' / 'src' / 'js' / 'va_app.js').read_text(encoding='utf-8')
        self.assertIn('video_analytics_app', app)
        utils = (root / 'static' / 'src' / 'js' / 'va_utils.js').read_text(encoding='utf-8')
        self.assertIn('formatDatetime', utils)
        playback = (root / 'static' / 'src' / 'xml' / 'screens' / 'va_playback.xml').read_text(encoding='utf-8')
        self.assertNotIn('<video', playback)
        alerts = (root / 'static' / 'src' / 'xml' / 'screens' / 'va_alerts.xml').read_text(encoding='utf-8')
        self.assertNotIn('<video', alerts)
        self.assertIn('Video-Based Alerts', alerts)
        cctv = (root / 'static' / 'src' / 'xml' / 'screens' / 'va_cctv.xml').read_text(encoding='utf-8')
        self.assertNotIn('<video', cctv)
        self.assertIn('CCTV Integration', cctv)
        self.assertIn('Not stored', cctv)

    def test_zone_camera_names_are_display_only(self):
        camera = self.env['va.camera'].create({'name': 'Zone Cam', 'code': 'CAM-ZN'})
        zone = self.env['va.zone'].create({
            'name': 'Named Zone',
            'code': 'ZN-CAM',
            'capacity': 5,
            'camera_ids': [(6, 0, [camera.id])],
        })
        data = self.api.get_occupancy_data()
        match = next(row for row in data['zones'] if row['id'] == zone.id)
        self.assertIn(camera.name, match['camera_names'])
