# -*- coding: utf-8 -*-
"""Phase 4 workflow tests."""
import base64
import unittest
from datetime import timedelta

try:
    from odoo import fields
    from odoo.exceptions import AccessError, UserError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    from odoo.addons.document_management.services.notification_service import DocumentNotificationService
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    AccessError = UserError = Exception
    DocumentNotificationService = None

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'dm_workflows')
class TestDmWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()
        cls.api = cls.env['document.management.ui.api']
        cls.pdf = {
            'filename': 'policy.pdf',
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 workflow').decode(),
            'size': 16,
        }

    def _file(self, name='policy.pdf'):
        payload = dict(self.pdf)
        payload['filename'] = name
        return payload

    def _type(self, name, required=True):
        return self.env['document.management.document.type'].create({
            'name': name,
            'requires_approval': required,
        })

    def test_01_upload_draft(self):
        dto = self.api.create_draft({'name': 'WF Draft'}, None)
        self.assertEqual(dto['state'], 'draft')
        self.assertFalse(dto.get('duplicate'))

    def test_02_upload_approved_document(self):
        doc_type = self._type('WF Skip', False)
        dto = self.api.upload_document({'name': 'WF Approved', 'type_id': doc_type.id}, self._file())
        self.assertEqual(dto['state'], 'approved')
        self.assertEqual(dto['current_version'], 'v1.0')

    def test_03_upload_pending_approval(self):
        doc_type = self._type('WF Need', True)
        dto = self.api.upload_document({'name': 'WF Pending', 'type_id': doc_type.id}, self._file())
        self.assertEqual(dto['state'], 'pending_approval')

    def test_04_duplicate_response(self):
        self.api.create_draft({'name': 'WF Dup'}, None)
        dup = self.api.upload_document({'name': 'WF Dup'}, self._file())
        self.assertTrue(dup['duplicate'])
        self.assertEqual(dup['name'], 'WF Dup')
        self.assertIn('document_id', dup)
        self.assertIn('current_version', dup)

    def test_05_new_version_workflow(self):
        dto = self.api.upload_document({'name': 'WF Version', 'type_id': self._type('WF V', False).id}, self._file())
        updated = self.api.upload_new_version(dto['id'], self._file('next.pdf'), 'note')
        self.assertEqual(updated['current_version'], 'v1.1')
        self.assertEqual(len(updated['versions']), 2)

    def test_06_restore_version_workflow(self):
        dto = self.api.upload_document({'name': 'WF Restore', 'type_id': self._type('WF R', False).id}, self._file())
        first = dto['current_version_id']
        self.api.upload_new_version(dto['id'], self._file('changed.pdf'))
        restored = self.api.restore_version(dto['id'], first)
        self.assertEqual(restored['current_version'], 'v1.2')

    def test_07_approval_submission(self):
        dto = self.api.upload_document({'name': 'WF Submit', 'type_id': self._type('WF S', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        self.assertEqual(request['state'], 'pending')
        self.assertEqual(request['steps'][0]['state'], 'active')

    def test_08_sequential_approval(self):
        one = self.env['res.users'].create({
            'name': 'WF One', 'login': 'wf_one', 'email': 'wf_one@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        two = self.env['res.users'].create({
            'name': 'WF Two', 'login': 'wf_two', 'email': 'wf_two@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        dto = self.api.upload_document({'name': 'WF Seq', 'type_id': self._type('WF SeqT', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [
            {'name': 'First', 'approver_id': one.id},
            {'name': 'Second', 'approver_id': two.id},
        ])
        mid = self.api.with_user(one).approve(request['id'])
        self.assertEqual(mid['state'], 'pending')
        final = self.api.with_user(two).approve(request['id'])
        self.assertEqual(final['state'], 'approved')

    def test_09_approve(self):
        dto = self.api.upload_document({'name': 'WF Approve', 'type_id': self._type('WF AT', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        result = self.api.approve(request['id'])
        self.assertEqual(result['state'], 'approved')

    def test_10_reject(self):
        dto = self.api.upload_document({'name': 'WF Reject', 'type_id': self._type('WF RJ', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        result = self.api.reject(request['id'], 'Not ready')
        self.assertEqual(result['state'], 'rejected')

    def test_11_request_changes(self):
        dto = self.api.upload_document({'name': 'WF Changes', 'type_id': self._type('WF CH', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        result = self.api.request_changes(request['id'], 'Please revise')
        self.assertEqual(result['state'], 'returned')

    def test_12_resubmit(self):
        dto = self.api.upload_document({'name': 'WF Resubmit', 'type_id': self._type('WF RS', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        self.api.request_changes(request['id'], 'Please revise')
        again = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        self.assertEqual(again['state'], 'pending')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'pending_approval')

    def test_13_expiry_filtering(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        self.api.create_draft({'name': 'WF Soon', 'expiry_date': today + timedelta(days=5)}, None)
        self.api.create_draft({'name': 'WF Expired', 'expiry_date': today - timedelta(days=1)}, None)
        board_soon = self.api.get_approval_board('expiring_soon')
        board_expired = self.api.get_approval_board('expired')
        self.assertTrue(any(row['document'] == 'WF Soon' for row in board_soon['rows']))
        self.assertTrue(any(row['document'] == 'WF Expired' for row in board_expired['rows']))

    def test_14_renewal(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        dto = self.api.upload_document({
            'name': 'WF Renew',
            'type_id': self._type('WF RN', False).id,
            'expiry_date': today + timedelta(days=5),
        }, self._file())
        renewed = self.api.renew_document(dto['id'], today + timedelta(days=90), None)
        self.assertEqual(renewed['expiry_date'], today + timedelta(days=90))
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'expiry_renewed'),
        ])
        self.assertTrue(events)

    def test_15_replacement_version(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        dto = self.api.upload_document({
            'name': 'WF Replace',
            'type_id': self._type('WF RP', False).id,
            'expiry_date': today - timedelta(days=1),
        }, self._file())
        replaced = self.api.renew_document(dto['id'], today + timedelta(days=40), self._file('replacement.pdf'))
        self.assertEqual(replaced['current_version'], 'v1.1')

    def test_16_expiry_notification(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        dto = self.api.create_draft({
            'name': 'WF ExpNote',
            'expiry_date': today - timedelta(days=1),
            'expiry_notify': True,
        }, None)
        document = self.env['document.management.document'].browse(dto['id'])
        service = DocumentNotificationService(self.env)
        service.ensure_expiry_notifications(document)
        service.ensure_expiry_notifications(document)
        notes = self.env['document.management.notification'].search([
            ('document_id', '=', dto['id']),
            ('kind', '=', 'expired'),
            ('is_read', '=', False),
        ])
        self.assertEqual(len(notes), 1)

    def test_17_notification_read(self):
        notes = self.api.list_notifications()
        self.assertIn('items', notes)
        dto = self.api.create_draft({'name': 'WF NoteRead'}, None)
        document = self.env['document.management.document'].browse(dto['id'])
        note = DocumentNotificationService(self.env).create_notification(
            self.env.user, document, 'access_granted', 'granted'
        )
        self.assertTrue(self.api.mark_notification_read(note.id))
        self.assertTrue(note.is_read)

    def test_18_add_user_access(self):
        user = self.env['res.users'].create({
            'name': 'WF Viewer', 'login': 'wf_viewer', 'email': 'wf_viewer@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        dto = self.api.create_draft({'name': 'WF ACL User', 'access_level': 'role_restricted'}, None)
        matrix = self.api.add_access(dto['id'], {'partner_type': 'user', 'user_id': user.id, 'role': 'viewer'})
        self.assertTrue(any(row['name'] == user.name and row['role'] == 'viewer' for row in matrix['rows']))

    def test_19_add_group_access(self):
        user = self.env['res.users'].create({
            'name': 'WF GroupUser', 'login': 'wf_group_user', 'email': 'wf_group@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        group = self.env['document.management.access.group'].create({
            'name': 'WF Group',
            'member_ids': [(6, 0, [user.id])],
        })
        dto = self.api.create_draft({'name': 'WF ACL Group', 'access_level': 'role_restricted'}, None)
        matrix = self.api.add_access(dto['id'], {'partner_type': 'group', 'group_id': group.id, 'role': 'viewer'})
        self.assertTrue(any(row['type'] == 'group' for row in matrix['rows']))

    def test_20_revoke_access(self):
        user = self.env['res.users'].create({
            'name': 'WF Revoke', 'login': 'wf_revoke', 'email': 'wf_revoke@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        dto = self.api.create_draft({'name': 'WF ACL Revoke', 'access_level': 'role_restricted'}, None)
        matrix = self.api.add_access(dto['id'], {'partner_type': 'user', 'user_id': user.id, 'role': 'viewer'})
        rule_id = next(row['id'] for row in matrix['rows'] if row['name'] == user.name)
        revoked = self.api.revoke_access(dto['id'], rule_id)
        self.assertTrue(any(row['id'] == rule_id and row['status'] == 'revoked' for row in revoked['rows']))

    def test_21_create_share_link(self):
        dto = self.api.upload_document({'name': 'WF Share', 'type_id': self._type('WF SH', False).id}, self._file())
        link = self.api.create_share_link(dto['id'], {'expiry': fields.Datetime.now() + timedelta(days=1)})
        self.assertTrue(link['url'].startswith('/document_management/share/'))

    def test_22_expire_share_link(self):
        dto = self.api.upload_document({'name': 'WF ShareExp', 'type_id': self._type('WF SHE', False).id}, self._file())
        link = self.env['document.management.share.link'].create({
            'document_id': dto['id'],
            'expiry': fields.Datetime.now() - timedelta(hours=1),
        })
        self.assertEqual(link.state, 'expired')

    def test_23_repository_filters(self):
        self.api.create_draft({'name': 'WF Repo Mine', 'department_label': 'Ops'}, None)
        data = self.api.get_repository_data('my', {'department': 'Ops'}, 'Repo Mine')
        self.assertTrue(any(item['name'] == 'WF Repo Mine' for item in data['items']))
        self.assertIn(data['view'], ('my', 'all'))

    def test_24_favorites(self):
        dto = self.api.create_draft({'name': 'WF Fav'}, None)
        added = self.api.toggle_favorite(dto['id'])
        self.assertTrue(added['favorited'])
        repo = self.api.get_repository_data('favorites', {}, None)
        self.assertTrue(any(item['id'] == dto['id'] for item in repo['items']))

    def test_25_archive(self):
        dto = self.api.upload_document({'name': 'WF Archive', 'type_id': self._type('WF AR', False).id}, self._file())
        archived = self.api.archive_document(dto['id'])
        self.assertEqual(archived['state'], 'archived')

    def test_26_restore_archive(self):
        dto = self.api.upload_document({'name': 'WF Unarchive', 'type_id': self._type('WF UA', False).id}, self._file())
        self.api.archive_document(dto['id'])
        restored = self.api.restore_document(dto['id'])
        self.assertEqual(restored['state'], 'approved')

    def test_27_document_details_dto(self):
        dto = self.api.upload_document({'name': 'WF Details', 'type_id': self._type('WF DT', False).id}, self._file())
        detail = self.api.get_document(dto['id'])
        self.assertIn('versions', detail)
        self.assertIn('approvals', detail)
        self.assertIn('access', detail)
        self.assertIn('activity', detail)
        self.assertIn('file', detail)
        self.assertTrue(detail['file']['name'])

    def test_28_approval_drawer_dto(self):
        dto = self.api.upload_document({'name': 'WF Drawer', 'type_id': self._type('WF DR', True).id}, self._file())
        request = self.api.submit_for_approval(dto['id'], [{'name': 'Review', 'approver_id': self.env.user.id}])
        board = self.api.get_approval_board('pending', {'request_id': request['id']})
        self.assertTrue(board['selected'])
        self.assertEqual(board['selected']['document'], 'WF Drawer')
        self.assertIn('steps', board['selected'])
        self.assertIn('file_size', board['selected'])

    def test_29_access_matrix_dto(self):
        dto = self.api.create_draft({'name': 'WF Matrix'}, None)
        matrix = self.api.get_access_matrix(dto['id'])
        self.assertIn('rows', matrix)
        self.assertIn('kpis', matrix)
        self.assertIn('access_level', matrix['kpis'])

    def test_30_audit_dto(self):
        self.api.create_draft({'name': 'WF AuditDto'}, None)
        data = self.api.get_audit_data()
        self.assertIn('rows', data)
        self.assertIn('kpis', data)
        self.assertIn('breakdown', data)
        self.assertIn('top_users', data)
        self.assertIn('security_alerts', data)

    def test_31_audit_csv(self):
        self.api.create_draft({'name': 'WF AuditCsv'}, None)
        export = self.api.export_audit()
        self.assertTrue(export['csv'].startswith('timestamp,'))
        self.assertIn('created', export['csv'])

    def test_32_keyword_search(self):
        self.api.create_draft({'name': 'WF SearchToken', 'property_ref': 'P-9'}, None)
        hits = self.api.keyword_search('SearchToken', {'property': 'P-9'})
        self.assertEqual(hits['total'], 1)

    def test_33_search_csv(self):
        self.api.create_draft({'name': 'WF SearchCsv'}, None)
        export = self.api.export_search_csv('SearchCsv', {})
        self.assertIn('WF SearchCsv', export['csv'])

    def test_34_ai_unavailable_state(self):
        payload = self.api.ai_search('anything', {})
        self.assertFalse(payload['configured'])
        self.assertEqual(payload['message'], 'AI Search is not configured')
        self.assertEqual(payload['citations'], [])

    def test_35_dashboard_real_aggregates(self):
        self.api.upload_document({'name': 'WF Dash', 'type_id': self._type('WF DA', False).id}, self._file())
        data = self.api.get_dashboard_data()
        self.assertGreaterEqual(data['kpis']['documents_total'], 1)
        self.assertIn('status_summary', data)
        self.assertIn('quick_action_counts', data)

    def test_36_unauthorized_operation_checks(self):
        owner = self.env['res.users'].create({
            'name': 'WF Owner', 'login': 'wf_owner', 'email': 'wf_owner@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        stranger = self.env['res.users'].create({
            'name': 'WF Stranger', 'login': 'wf_stranger', 'email': 'wf_stranger@example.com',
            'groups_id': [(6, 0, [self.env.ref('document_management.group_dm_user').id])],
        })
        dto = self.api.with_user(owner).create_draft({
            'name': 'WF Secret',
            'access_level': 'private',
        }, None)
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).get_document(dto['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).download_document(dto['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).add_access(dto['id'], {
                'partner_type': 'user', 'user_id': stranger.id, 'role': 'editor',
            })
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).archive_document(dto['id'])
