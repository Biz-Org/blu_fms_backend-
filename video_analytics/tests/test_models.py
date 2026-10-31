# -*- coding: utf-8 -*-
"""Phase 3 domain model tests."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

from odoo.addons.video_analytics.models.va_mixin import DETECTION_TYPE_VALUES


@tagged('post_install', '-at_install', 'va_models')
class TestVaModels(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.camera = self.env['va.camera'].create({
            'name': 'Gate Cam',
            'code': 'CAM-GATE',
            'location_label': 'Main gate',
            'status': 'online',
            'stream_protocol': 'http',
        })
        self.zone = self.env['va.zone'].create({
            'name': 'Lobby',
            'code': 'ZN-LOBBY',
            'capacity': 50,
            'occupancy_threshold_pct': 80,
            'camera_ids': [(6, 0, [self.camera.id])],
        })

    def test_nine_models_load(self):
        expected = {
            'va.mixin': 'va.mixin',
            'va.camera': 'va.camera',
            'va.zone': 'va.zone',
            'va.detection.rule': 'va.detection.rule',
            'va.detection': 'va.detection',
            'va.event': 'va.event',
            'va.investigation.note': 'va.investigation.note',
            'va.occupancy.snapshot': 'va.occupancy.snapshot',
            'va.ui.api': 'va.ui.api',
        }
        for name in expected:
            self.assertIn(name, self.env.registry)
        self.assertTrue(self.env['va.mixin']._abstract)
        self.assertTrue(self.env['va.ui.api']._transient)
        self.assertFalse(self.env['va.camera']._abstract)
        self.assertNotIn('va.alert', self.env.registry)

    def test_mixin_inheritance(self):
        for model in (
            'va.camera', 'va.zone', 'va.detection.rule', 'va.detection',
            'va.event', 'va.investigation.note', 'va.occupancy.snapshot', 'va.ui.api',
        ):
            self.assertTrue(hasattr(self.env[model], '_va_require_user'))

    def test_camera_required_and_protocol_status(self):
        self.assertEqual(self.camera.status, 'online')
        self.assertEqual(self.camera.stream_protocol, 'http')
        self.assertTrue(self.camera.active)
        self.assertEqual(self.camera.company_id, self.company)
        with self.assertRaises(Exception):
            self.env['va.camera'].create({'code': 'NO-NAME'})

    def test_camera_code_unique_per_company(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.env['va.camera'].create({
                    'name': 'Dup',
                    'code': 'CAM-GATE',
                })

    def test_zone_camera_m2m_and_validation(self):
        self.assertIn(self.camera, self.zone.camera_ids)
        self.assertIn(self.zone, self.camera.zone_ids)
        with self.assertRaises(ValidationError):
            self.zone.write({'capacity': 0})
        with self.assertRaises(ValidationError):
            self.zone.write({'occupancy_threshold_pct': 120})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.env['va.zone'].create({
                    'name': 'Dup zone',
                    'code': 'ZN-LOBBY',
                    'capacity': 10,
                })

    def test_detection_rule_types_and_threshold(self):
        self.assertEqual(DETECTION_TYPE_VALUES, {
            'intrusion', 'fire_smoke', 'ppe_violation',
            'vehicle_speeding', 'crowd_density', 'object_detection',
        })
        rule = self.env['va.detection.rule'].create({
            'name': 'Intrusion global',
            'detection_type': 'intrusion',
            'confidence_threshold': 70,
        })
        self.assertFalse(rule.camera_id)
        self.assertFalse(rule.zone_id)
        with self.assertRaises(ValidationError):
            rule.write({'confidence_threshold': 140})
        specific = self.env['va.detection.rule'].create({
            'name': 'Intrusion camera zone',
            'detection_type': 'intrusion',
            'confidence_threshold': 40,
            'camera_id': self.camera.id,
            'zone_id': self.zone.id,
        })
        matched = self.env['va.detection.rule'].find_matching_rule(
            'intrusion', camera=self.camera, zone=self.zone,
        )
        self.assertEqual(matched, specific)

    def test_detection_validation_and_external_id(self):
        now = fields.Datetime.now()
        det = self.env['va.detection'].create({
            'detection_type': 'fire_smoke',
            'confidence': 88.5,
            'timestamp': now,
            'camera_id': self.camera.id,
            'zone_id': self.zone.id,
            'external_id': 'ext-1',
        })
        self.assertTrue(det.name.startswith('VA-DET'))
        self.assertEqual(det.state, 'new')
        with self.assertRaises(ValidationError):
            det.copy({'external_id': 'ext-1', 'name': False})
        other = self.env['va.detection'].create({
            'detection_type': 'object_detection',
            'confidence': 10,
            'timestamp': now,
            'camera_id': self.camera.id,
        })
        self.assertFalse(other.external_id)
        with self.assertRaises(ValidationError):
            self.env['va.detection'].create({
                'detection_type': 'intrusion',
                'confidence': 101,
                'timestamp': now,
                'camera_id': self.camera.id,
            })

    def test_event_fields_and_alert_queue(self):
        event = self.env['va.event'].create({
            'event_type': 'ppe_violation',
            'severity': 'high',
            'camera_id': self.camera.id,
            'zone_id': self.zone.id,
            'confidence': 91,
        })
        self.assertTrue(event.name.startswith('VA-EVT'))
        self.assertEqual(event.state, 'open')
        self.assertTrue(event.is_alert_queue)
        with self.assertRaises(UserError):
            event.write({'state': 'resolved'})
        event.action_acknowledge()
        self.assertEqual(event.state, 'acknowledged')
        event.action_investigate()
        self.assertTrue(event.is_alert_queue)
        with self.assertRaises(ValidationError):
            event.write({'confidence': -1})

    def test_investigation_note_required(self):
        event = self.env['va.event'].create({
            'event_type': 'intrusion',
            'camera_id': self.camera.id,
        })
        note = self.env['va.investigation.note'].create({
            'event_id': event.id,
            'body': 'Reviewed footage.',
        })
        self.assertEqual(note.user_id, self.env.user)
        self.assertEqual(note.event_id, event)
        with self.assertRaises(Exception):
            self.env['va.investigation.note'].create({'body': 'no event'})
        with self.assertRaises(Exception):
            self.env['va.investigation.note'].create({'event_id': event.id, 'body': False})

    def test_occupancy_percentage_and_zone_current(self):
        stamp = fields.Datetime.now()
        low = self.env['va.occupancy.snapshot'].create({
            'zone_id': self.zone.id,
            'camera_id': self.camera.id,
            'timestamp': stamp,
            'count': 20,
        })
        self.assertEqual(low.capacity, 50)
        self.assertEqual(low.occupancy_pct, 40.0)
        self.assertFalse(low.over_threshold)
        later = fields.Datetime.to_datetime(stamp) + timedelta(hours=1)
        high = self.env['va.occupancy.snapshot'].create({
            'zone_id': self.zone.id,
            'timestamp': later,
            'count': 45,
            'capacity': 50,
        })
        self.assertEqual(high.occupancy_pct, 90.0)
        self.assertTrue(high.over_threshold)
        self.zone.invalidate_recordset(['current_count', 'current_occupancy_pct', 'over_threshold'])
        self.assertEqual(self.zone.current_count, 45)
        self.assertEqual(self.zone.current_occupancy_pct, 90.0)
        self.assertTrue(self.zone.over_threshold)
        with self.assertRaises(ValidationError):
            high.write({'count': -3})
        with self.assertRaises(ValidationError):
            high.write({'capacity': 0})

    def test_ui_api_session_helper(self):
        data = self.env['va.ui.api'].get_session_context()
        self.assertEqual(data['uid'], self.env.uid)
        self.assertTrue(data['is_admin'] or data['is_manager'] or data['is_user'])
        self.assertNotIn('kpis', data)
