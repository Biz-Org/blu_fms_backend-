# -*- coding: utf-8 -*-
"""Phase 4 detection, occupancy, CCTV, and lifecycle service tests."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'va_services')
class TestVaServices(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.group_user = self.env.ref('video_analytics.group_va_user')
        self.group_manager = self.env.ref('video_analytics.group_va_manager')
        self.group_admin = self.env.ref('video_analytics.group_va_admin')
        self.user = self.env['res.users'].create({
            'name': 'VA Svc User',
            'login': 'va_svc_user',
            'groups_id': [(6, 0, [self.group_user.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        self.manager = self.env['res.users'].create({
            'name': 'VA Svc Manager',
            'login': 'va_svc_manager',
            'groups_id': [(6, 0, [self.group_manager.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        self.admin = self.env['res.users'].create({
            'name': 'VA Svc Admin',
            'login': 'va_svc_admin',
            'groups_id': [(6, 0, [self.group_admin.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        self.camera = self.env['va.camera'].create({
            'name': 'North Cam',
            'code': 'CAM-N',
            'stream_url': 'http://example.local/stream.m3u8',
            'stream_protocol': 'hls',
        })
        self.zone = self.env['va.zone'].create({
            'name': 'North Hall',
            'code': 'ZN-N',
            'capacity': 40,
            'occupancy_threshold_pct': 80,
            'camera_ids': [(6, 0, [self.camera.id])],
        })
        self.now = fields.Datetime.now()

    def _ingest(self, **vals):
        payload = {
            'camera_code': 'CAM-N',
            'detection_type': 'intrusion',
            'confidence': 90,
            'timestamp': self.now,
        }
        payload.update(vals)
        return self.env['va.detection'].with_user(self.manager).ingest(payload)

    def test_01_valid_detection_creates_record(self):
        result = self._ingest()
        det = self.env['va.detection'].browse(result['detection_id'])
        self.assertTrue(det.exists())
        self.assertEqual(det.camera_id, self.camera)

    def test_02_unknown_camera_fails(self):
        with self.assertRaises(UserError):
            self._ingest(camera_code='MISSING')

    def test_03_invalid_detection_type_fails(self):
        with self.assertRaises(ValidationError):
            self._ingest(detection_type='unknown_type')

    def test_04_confidence_below_zero_fails(self):
        with self.assertRaises(ValidationError):
            self._ingest(confidence=-1)

    def test_05_confidence_above_100_fails(self):
        with self.assertRaises(ValidationError):
            self._ingest(confidence=101)

    def test_06_no_matching_rule_state_new(self):
        result = self._ingest()
        self.assertEqual(result['state'], 'new')
        self.assertFalse(result['event_id'])

    def test_07_below_threshold_skipped(self):
        self.env['va.detection.rule'].create({
            'name': 'High intrusion',
            'detection_type': 'intrusion',
            'confidence_threshold': 95,
        })
        result = self._ingest(confidence=50)
        self.assertEqual(result['state'], 'skipped')
        self.assertEqual(result['skip_reason'], 'below_threshold')
        self.assertFalse(result['event_id'])

    def test_08_above_threshold_creates_event(self):
        self.env['va.detection.rule'].create({
            'name': 'Intrusion',
            'detection_type': 'intrusion',
            'confidence_threshold': 40,
            'default_severity': 'high',
            'create_event': True,
        })
        result = self._ingest(confidence=80, evidence_url='http://evidence/clip.mp4',
                              playback_start=self.now, playback_end=self.now)
        self.assertEqual(result['state'], 'linked')
        event = self.env['va.event'].browse(result['event_id'])
        self.assertEqual(event.state, 'open')
        self.assertEqual(event.severity, 'high')
        self.assertEqual(event.evidence_url, 'http://evidence/clip.mp4')
        self.assertTrue(event.playback_start)

    def test_09_create_event_false_no_event(self):
        self.env['va.detection.rule'].create({
            'name': 'Silent',
            'detection_type': 'intrusion',
            'confidence_threshold': 10,
            'create_event': False,
        })
        result = self._ingest(confidence=90)
        self.assertFalse(result['event_id'])
        self.assertEqual(result['state'], 'new')

    def test_10_evidence_and_playback_preserved(self):
        self.env['va.detection.rule'].create({
            'name': 'PPE',
            'detection_type': 'ppe_violation',
            'confidence_threshold': 10,
        })
        start = self.now
        end = fields.Datetime.to_datetime(self.now) + timedelta(minutes=2)
        result = self._ingest(
            detection_type='ppe_violation',
            evidence_url='http://ev/1.jpg',
            playback_start=start,
            playback_end=end,
        )
        det = self.env['va.detection'].browse(result['detection_id'])
        event = self.env['va.event'].browse(result['event_id'])
        self.assertEqual(det.evidence_url, 'http://ev/1.jpg')
        self.assertEqual(fields.Datetime.to_datetime(event.playback_end), fields.Datetime.to_datetime(end))

    def test_11_12_external_id_idempotent_no_duplicate_event(self):
        self.env['va.detection.rule'].create({
            'name': 'Fire',
            'detection_type': 'fire_smoke',
            'confidence_threshold': 10,
        })
        first = self._ingest(detection_type='fire_smoke', external_id='ext-100')
        second = self._ingest(detection_type='fire_smoke', external_id='ext-100', confidence=99)
        self.assertTrue(second['idempotent'])
        self.assertEqual(first['detection_id'], second['detection_id'])
        self.assertEqual(first['event_id'], second['event_id'])
        self.assertEqual(self.env['va.detection'].search_count([('external_id', '=', 'ext-100')]), 1)
        self.assertEqual(self.env['va.event'].search_count([('detection_id', '=', first['detection_id'])]), 1)

    def test_13_16_rule_matching_order_and_tie_break(self):
        other_cam = self.env['va.camera'].create({'name': 'Other', 'code': 'CAM-O'})
        global_rule = self.env['va.detection.rule'].create({
            'name': 'global',
            'detection_type': 'object_detection',
            'confidence_threshold': 10,
        })
        zone_rule = self.env['va.detection.rule'].create({
            'name': 'zone',
            'detection_type': 'object_detection',
            'confidence_threshold': 10,
            'zone_id': self.zone.id,
        })
        camera_rule = self.env['va.detection.rule'].create({
            'name': 'camera',
            'detection_type': 'object_detection',
            'confidence_threshold': 10,
            'camera_id': self.camera.id,
        })
        both_rule = self.env['va.detection.rule'].create({
            'name': 'both',
            'detection_type': 'object_detection',
            'confidence_threshold': 10,
            'camera_id': self.camera.id,
            'zone_id': self.zone.id,
        })
        Rule = self.env['va.detection.rule']
        self.assertEqual(
            Rule.find_matching_rule('object_detection', camera=self.camera, zone=self.zone),
            both_rule,
        )
        self.assertEqual(
            Rule.find_matching_rule('object_detection', camera=self.camera, zone=False),
            camera_rule,
        )
        self.assertEqual(
            Rule.find_matching_rule('object_detection', camera=other_cam, zone=self.zone),
            zone_rule,
        )
        self.assertEqual(
            Rule.find_matching_rule('object_detection', camera=other_cam, zone=False),
            global_rule,
        )
        high = self.env['va.detection.rule'].create({
            'name': 'global-high',
            'detection_type': 'vehicle_speeding',
            'confidence_threshold': 80,
        })
        low = self.env['va.detection.rule'].create({
            'name': 'global-low',
            'detection_type': 'vehicle_speeding',
            'confidence_threshold': 20,
        })
        self.assertEqual(Rule.find_matching_rule('vehicle_speeding'), high)
        first_tie = self.env['va.detection.rule'].create({
            'name': 'tie-a',
            'detection_type': 'crowd_density',
            'confidence_threshold': 50,
        })
        self.env['va.detection.rule'].create({
            'name': 'tie-b',
            'detection_type': 'crowd_density',
            'confidence_threshold': 50,
        })
        self.assertEqual(Rule.find_matching_rule('crowd_density'), first_tie)

    def test_18_inactive_rules_ignored(self):
        self.env['va.detection.rule'].create({
            'name': 'off',
            'detection_type': 'intrusion',
            'confidence_threshold': 1,
            'active': False,
        })
        result = self._ingest(confidence=99)
        self.assertEqual(result['state'], 'new')

    def test_19_32_event_lifecycle_assignment_and_notes(self):
        event = self.env['va.event'].create({
            'event_type': 'intrusion',
            'camera_id': self.camera.id,
        })
        event.with_user(self.user).action_acknowledge()
        self.assertEqual(event.state, 'acknowledged')
        event.with_user(self.user).action_investigate()
        self.assertEqual(event.state, 'investigating')
        event.with_user(self.manager).action_resolve('cleared')
        self.assertEqual(event.state, 'resolved')
        with self.assertRaises(UserError):
            event.with_user(self.manager).action_resolve('again')
        with self.assertRaises(AccessError):
            event.with_user(self.user).action_close()
        event.with_user(self.manager).action_close()
        self.assertEqual(event.state, 'closed')
        with self.assertRaises(UserError):
            event.with_user(self.manager).action_close()
        event.with_user(self.admin).action_reopen()
        self.assertEqual(event.state, 'open')
        event.with_user(self.manager).action_false_positive('noise')
        self.assertEqual(event.state, 'false_positive')
        event.with_user(self.admin).action_reopen()
        event.with_user(self.user).action_acknowledge()
        event.with_user(self.manager).action_false_positive()
        event.with_user(self.admin).action_reopen()
        event.with_user(self.user).action_investigate()
        event.with_user(self.manager).action_false_positive()
        with self.assertRaises(UserError):
            event.write({'state': 'open'})
        event.with_user(self.admin).action_reopen()
        with self.assertRaises(AccessError):
            event.with_user(self.user).action_resolve('nope')
        with self.assertRaises(AccessError):
            event.with_user(self.user).action_assign(self.manager.id)
        event.with_user(self.user).action_assign(self.user.id)
        event.with_user(self.manager).action_assign(self.manager.id)
        self.assertEqual(event.user_id, self.manager)
        event.with_user(self.user).action_add_note('First look')
        self.assertEqual(len(event.note_ids), 1)
        self.assertEqual(event.note_ids.user_id, self.user)
        with self.assertRaises(UserError):
            event.with_user(self.user).action_add_note('   ')
        with self.assertRaises(UserError):
            event.note_ids.write({'body': 'tamper'})

    def test_33_41_occupancy_and_crowd_events(self):
        Occupancy = self.env['va.occupancy.snapshot'].with_user(self.manager)
        below = Occupancy.ingest({
            'zone_code': 'ZN-N',
            'camera_code': 'CAM-N',
            'timestamp': self.now,
            'count': 10,
            'occupancy_pct': 99,
        })
        self.assertEqual(below['occupancy_pct'], 25.0)
        self.assertFalse(below['over_threshold'])
        self.assertFalse(below['event_id'])
        first = Occupancy.ingest({
            'zone_id': self.zone.id,
            'timestamp': self.now,
            'count': 36,
        })
        self.assertEqual(first['occupancy_pct'], 90.0)
        self.assertTrue(first['over_threshold'])
        self.assertTrue(first['event_id'])
        second = Occupancy.ingest({
            'zone_code': 'ZN-N',
            'timestamp': self.now,
            'count': 39,
        })
        self.assertEqual(second['event_id'], first['event_id'])
        crowd = self.env['va.event'].browse(first['event_id'])
        crowd.action_acknowledge()
        crowd.action_investigate()
        crowd.with_user(self.manager).action_resolve('cleared')
        third = Occupancy.ingest({
            'zone_code': 'ZN-N',
            'timestamp': self.now,
            'count': 40,
        })
        self.assertNotEqual(third['event_id'], first['event_id'])
        snap = self.env['va.occupancy.snapshot'].browse(third['snapshot_id'])
        self.assertEqual(snap.event_id.id, third['event_id'])
        with self.assertRaises(ValidationError):
            Occupancy.ingest({'zone_code': 'ZN-N', 'timestamp': self.now, 'count': -1})
        with self.assertRaises(ValidationError):
            snap.write({'capacity': 0})

    def test_42_44_cctv_stub(self):
        result = self.camera.with_user(self.manager).action_test_connection()
        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'stub')
        self.assertEqual(result['status'], 'offline')
        self.assertFalse(result['connected'])
        self.assertEqual(self.camera.status, 'offline')
        self.assertTrue(self.camera.last_seen)
        stream = self.camera.with_user(self.user).action_resolve_stream()
        self.assertEqual(stream['url'], 'http://example.local/stream.m3u8')
        self.assertEqual(stream['protocol'], 'hls')
        self.assertTrue(stream['available'])
        with self.assertRaises(UserError):
            self.camera.write({'status': 'online'})
        self.camera.with_user(self.manager).action_set_status('degraded')
        self.assertEqual(self.camera.status, 'degraded')

    def test_45_50_security_and_company(self):
        Detection = self.env['va.detection']
        with self.assertRaises(AccessError):
            Detection.with_user(self.user).ingest({
                'camera_code': 'CAM-N',
                'detection_type': 'intrusion',
                'confidence': 90,
                'timestamp': self.now,
            })
        self.env['va.detection.rule'].create({
            'name': 'mgr',
            'detection_type': 'intrusion',
            'confidence_threshold': 10,
        })
        result = Detection.with_user(self.manager).ingest({
            'camera_code': 'CAM-N',
            'detection_type': 'intrusion',
            'confidence': 90,
            'timestamp': self.now,
        })
        event = self.env['va.event'].browse(result['event_id'])
        with self.assertRaises(AccessError):
            event.with_user(self.user).action_resolve('x')
        event.with_user(self.manager).action_acknowledge()
        event.with_user(self.manager).action_resolve('ok')
        event.with_user(self.admin).action_reopen()
        company_b = self.env['res.company'].create({'name': 'VA Svc Other'})
        cam_b = self.env['va.camera'].create({
            'name': 'B Cam',
            'code': 'CAM-B2',
            'company_id': company_b.id,
        })
        with self.assertRaises(UserError):
            Detection.with_user(self.manager).ingest({
                'camera_id': cam_b.id,
                'detection_type': 'intrusion',
                'confidence': 90,
                'timestamp': self.now,
            })
        with self.assertRaises(AccessError):
            self.camera.with_user(self.user).action_test_connection()
        with self.assertRaises(AccessError):
            self.env['va.occupancy.snapshot'].with_user(self.user).ingest({
                'zone_code': 'ZN-N',
                'timestamp': self.now,
                'count': 1,
            })
