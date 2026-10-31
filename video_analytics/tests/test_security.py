# -*- coding: utf-8 -*-
"""Phase 3 ACL and multi-company tests."""
from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'va_security')
class TestVaSecurity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company_a = self.env.company
        self.company_b = self.env['res.company'].create({'name': 'VA Other Company'})
        self.group_user = self.env.ref('video_analytics.group_va_user')
        self.group_manager = self.env.ref('video_analytics.group_va_manager')
        self.group_admin = self.env.ref('video_analytics.group_va_admin')
        self.user = self._make_user('va_phase3_user', self.group_user, self.company_a)
        self.manager = self._make_user('va_phase3_manager', self.group_manager, self.company_a)
        self.admin = self._make_user('va_phase3_admin', self.group_admin, self.company_a)

        self.camera_a = self.env['va.camera'].create({
            'name': 'Cam A',
            'code': 'CAM-A',
            'company_id': self.company_a.id,
        })
        self.camera_b = self.env['va.camera'].create({
            'name': 'Cam B',
            'code': 'CAM-B',
            'company_id': self.company_b.id,
        })
        self.event_a = self.env['va.event'].create({
            'event_type': 'intrusion',
            'camera_id': self.camera_a.id,
            'company_id': self.company_a.id,
        })

    def _make_user(self, login, group, company):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, [group.id])],
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
        })

    def test_user_cannot_create_camera_event_or_detection(self):
        Camera = self.env['va.camera'].with_user(self.user)
        with self.assertRaises(AccessError):
            Camera.create({'name': 'X', 'code': 'CAM-X'})
        with self.assertRaises(AccessError):
            self.env['va.event'].with_user(self.user).create({
                'event_type': 'intrusion',
                'camera_id': self.camera_a.id,
            })
        with self.assertRaises(AccessError):
            self.env['va.detection'].with_user(self.user).create({
                'detection_type': 'intrusion',
                'confidence': 50,
                'timestamp': fields.Datetime.now(),
                'camera_id': self.camera_a.id,
            })

    def test_user_can_read_and_add_note(self):
        event = self.env['va.event'].with_user(self.user).browse(self.event_a.id)
        self.assertEqual(event.event_type, 'intrusion')
        self.env['va.investigation.note'].with_user(self.user).create({
            'event_id': self.event_a.id,
            'body': 'Operator note',
        })
        cameras = self.env['va.camera'].with_user(self.user).search([])
        self.assertIn(self.camera_a, cameras)

    def test_manager_can_create_camera_and_not_create_as_user(self):
        cam = self.env['va.camera'].with_user(self.manager).create({
            'name': 'Mgr Cam',
            'code': 'CAM-MGR',
        })
        self.assertTrue(cam.id)
        self.env['va.detection'].with_user(self.manager).create({
            'detection_type': 'object_detection',
            'confidence': 12,
            'timestamp': fields.Datetime.now(),
            'camera_id': cam.id,
        })

    def test_admin_can_unlink_zone(self):
        zone = self.env['va.zone'].create({
            'name': 'Temp',
            'code': 'ZN-TEMP',
            'capacity': 5,
        })
        with self.assertRaises(AccessError):
            zone.with_user(self.manager).unlink()
        zone.with_user(self.admin).unlink()
        self.assertFalse(zone.exists())

    def test_multi_company_record_rules(self):
        CameraUser = self.env['va.camera'].with_user(self.user)
        self.assertTrue(CameraUser.search([('id', '=', self.camera_a.id)]))
        self.assertFalse(CameraUser.search([('id', '=', self.camera_b.id)]))
        self.assertFalse(
            self.env['va.event'].with_user(self.user).search([
                ('company_id', '=', self.company_b.id),
            ])
        )

    def test_user_cannot_resolve_event(self):
        self.event_a.action_acknowledge()
        with self.assertRaises(AccessError):
            self.event_a.with_user(self.user).action_resolve('done')
        self.event_a.with_user(self.manager).action_investigate()
        self.event_a.with_user(self.manager).action_resolve('closed')
        self.assertEqual(self.event_a.state, 'resolved')
