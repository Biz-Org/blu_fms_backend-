# -*- coding: utf-8 -*-
"""Phase 6 end-to-end QA, security, and production-readiness tests."""
import base64
import json
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
@tagged('post_install', '-at_install', 'dm_phase6')
class TestDmPhase6(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()
        cls.api = cls.env['document.management.ui.api']
        cls.pdf = {
            'filename': 'policy.pdf',
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 phase6-file').decode(),
            'size': 22,
        }

    def _user(self, login, group='document_management.group_dm_user', company=None):
        company = company or self.env.company
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'password': 'pwd',
            'email': '%s@example.com' % login,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(group).id,
            ])],
        })

    def _file(self, filename='policy.pdf', mimetype='application/pdf'):
        payload = dict(self.pdf)
        payload['filename'] = filename
        payload['mimetype'] = mimetype
        return payload

    def _type(self, name, requires_approval=True):
        return self.env['document.management.document.type'].create({
            'name': name,
            'requires_approval': requires_approval,
        })

    def _upload(self, name, requires_approval=False, **vals):
        vals.setdefault('name', name)
        vals.setdefault('type_id', self._type('T %s' % name, requires_approval).id)
        return self.api.upload_document(vals, self._file())

    def test_01_save_draft_requires_name_file_optional(self):
        with self.assertRaises(UserError):
            self.api.create_draft({'description': 'no name'}, None)
        dto = self.api.create_draft({'name': 'P6 Draft Only'}, None)
        self.assertEqual(dto['state'], 'draft')
        self.assertFalse(dto['current_version_id'])
        self.assertFalse(dto.get('duplicate'))
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'submitted'),
        ])
        self.assertFalse(events)

    def test_02_upload_sets_owner_company_version_private_attachment(self):
        owner = self._user('p6_upload_owner')
        folder = self.env['document.management.folder'].create({'name': 'P6 Folder'})
        category = self.env['document.management.category'].create({'name': 'P6 Category'})
        doc_type = self._type('P6 Upload Type', False)
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Uploaded',
            'folder_id': folder.id,
            'category_id': category.id,
            'type_id': doc_type.id,
            'department_label': 'Ops',
        }, self._file())
        self.assertEqual(dto['state'], 'approved')
        self.assertEqual(dto['owner_id'], owner.id)
        self.assertEqual(dto['company_id'], self.env.company.id)
        self.assertEqual(dto['folder_id'], folder.id)
        self.assertEqual(dto['current_version'], 'v1.0')
        version = self.env['document.management.version'].browse(dto['current_version_id'])
        self.assertFalse(version.attachment_id.public)

    def test_03_invalid_uploads_return_useful_errors(self):
        cases = [
            ('virus.exe', 'application/octet-stream', 100),
            ('file.pdf', 'application/x-msdownload', 100),
            ('file.pdf', 'application/pdf', 51 * 1024 * 1024),
            ('../secret.pdf', 'application/pdf', 100),
            ('folder/secret.pdf', 'application/pdf', 100),
        ]
        for filename, mimetype, size in cases:
            result = self.api.validate_upload(filename, mimetype, size, None, 'Named')
            self.assertFalse(result['ok'], filename)
            self.assertTrue(result['errors'], filename)
        with self.assertRaises(UserError):
            self.api.upload_document({'description': 'missing name'}, self._file())

    def test_04_duplicate_structured_response_no_second_master(self):
        folder = self.env['document.management.folder'].create({'name': 'P6 Dup Folder'})
        first = self.api.create_draft({'name': 'P6 Same Name', 'folder_id': folder.id}, None)
        duplicate = self.api.upload_document(
            {'name': 'P6 Same Name', 'folder_id': folder.id},
            self._file(),
        )
        self.assertTrue(duplicate.get('duplicate'))
        self.assertEqual(duplicate['document_id'], first['id'])
        self.assertIn('message', duplicate)
        self.assertEqual(
            self.env['document.management.document'].search_count([
                ('name', '=', 'P6 Same Name'),
                ('folder_id', '=', folder.id),
            ]),
            1,
        )
        versioned = self.api.upload_document({
            'name': 'P6 Same Name',
            'folder_id': folder.id,
            'create_new_version': True,
        }, self._file())
        self.assertEqual(versioned['id'], first['id'])
        self.assertEqual(versioned['current_version'], 'v1.0')

    def test_05_draft_to_approved_journey(self):
        owner = self._user('p6_journey_owner')
        reviewer = self._user('p6_journey_reviewer')
        dto = self.api.with_user(owner).create_draft({
            'name': 'P6 Journey',
            'type_id': self._type('P6 Journey Type', True).id,
        }, self._file())
        self.assertEqual(dto['state'], 'draft')
        request = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        self.assertEqual(request['state'], 'pending')
        self.assertEqual(request['steps'][0]['state'], 'active')
        self.assertEqual(request['current_reviewer_id'], reviewer.id)
        notes = self.env['document.management.notification'].sudo().search([
            ('document_id', '=', dto['id']),
            ('kind', '=', 'approval_submitted'),
        ])
        self.assertTrue(notes.filtered(lambda n: n.user_id == reviewer))
        approved = self.api.with_user(reviewer).approve(request['id'])
        self.assertEqual(approved['state'], 'approved')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'approved')
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
        ]).mapped('event_type')
        self.assertIn('submitted', events)
        self.assertIn('approved', events)

    def test_06_sequential_approval_security_and_notifications(self):
        owner = self._user('p6_seq_owner')
        one = self._user('p6_seq_one')
        two = self._user('p6_seq_two')
        stranger = self._user('p6_seq_stranger')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Sequential',
            'type_id': self._type('P6 Seq Type', True).id,
        }, self._file())
        request = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'First', 'approver_id': one.id},
            {'name': 'Second', 'approver_id': two.id},
        ])
        with self.assertRaises(AccessError):
            self.api.with_user(two).approve(request['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).approve(request['id'])
        mid = self.api.with_user(one).approve(request['id'])
        self.assertEqual(mid['state'], 'pending')
        self.assertEqual(mid['steps'][1]['state'], 'active')
        mid_events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'approved'),
        ])
        self.assertTrue(mid_events)
        owner_notes = self.env['document.management.notification'].sudo().search([
            ('document_id', '=', dto['id']),
            ('user_id', '=', owner.id),
            ('kind', '=', 'approval_decision'),
        ])
        self.assertTrue(owner_notes)
        with self.assertRaises(AccessError):
            self.api.with_user(one).approve(request['id'])
        final = self.api.with_user(two).approve(request['id'])
        self.assertEqual(final['state'], 'approved')
        decisions = self.env['document.management.approval.step'].search([
            ('request_id', '=', request['id']),
            ('state', '=', 'approved'),
        ])
        self.assertEqual(len(decisions), 2)

    def test_07_reject_request_changes_resubmit_new_cycle(self):
        owner = self._user('p6_resub_owner')
        reviewer = self._user('p6_resub_reviewer')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Reject Cycle',
            'type_id': self._type('P6 Reject Type', True).id,
        }, self._file())
        first = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        with self.assertRaises(UserError):
            self.api.with_user(reviewer).reject(first['id'], '   ')
        rejected = self.api.with_user(reviewer).reject(first['id'], 'Needs work')
        self.assertEqual(rejected['state'], 'rejected')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'rejected')
        self.assertEqual(document.approval_ids.filtered(lambda r: r.state == 'pending'), document.approval_ids.browse())
        again = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'Review 2', 'approver_id': reviewer.id},
        ])
        self.assertEqual(again['state'], 'pending')
        self.assertNotEqual(again['id'], first['id'])
        first_rec = self.env['document.management.approval.request'].browse(first['id'])
        self.assertEqual(first_rec.state, 'rejected')
        returned_doc = self.api.with_user(owner).upload_document({
            'name': 'P6 Return Cycle',
            'type_id': self._type('P6 Return Type', True).id,
        }, self._file())
        returned_req = self.api.with_user(owner).submit_for_approval(returned_doc['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        changed = self.api.with_user(reviewer).request_changes(returned_req['id'], 'Please revise')
        self.assertEqual(changed['state'], 'returned')
        resubmitted = self.api.with_user(owner).submit_for_approval(returned_doc['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        self.assertEqual(resubmitted['state'], 'pending')

    def test_08_lifecycle_pending_cannot_archive(self):
        dto = self._upload('P6 Pending Archive', requires_approval=True)
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'pending_approval')
        with self.assertRaises(UserError):
            self.api.archive_document(dto['id'])
        with self.assertRaises(UserError):
            document._dm_set_state('archived')
        draft = self.api.create_draft({'name': 'P6 Draft Archive'}, None)
        archived = self.api.archive_document(draft['id'])
        self.assertEqual(archived['state'], 'archived')
        restored = self.api.restore_document(draft['id'])
        self.assertEqual(restored['state'], 'draft')

    def test_09_expiry_overlay_filters_and_idempotent_notifications(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        none = self.api.create_draft({'name': 'P6 No Expiry'}, None)
        future = self.api.create_draft({
            'name': 'P6 Future Expiry',
            'expiry_date': today + timedelta(days=60),
        }, None)
        soon = self.api.create_draft({
            'name': 'P6 Soon Expiry',
            'expiry_date': today + timedelta(days=5),
            'expiry_notify': True,
        }, None)
        expired = self.api.create_draft({
            'name': 'P6 Expired Overlay',
            'expiry_date': today - timedelta(days=1),
            'expiry_notify': True,
        }, None)
        self.assertEqual(none['state'], 'draft')
        self.assertEqual(future['state'], 'draft')
        self.assertEqual(soon['expiry_status'], 'expiring_soon')
        self.assertEqual(expired['expiry_status'], 'expired')
        self.assertEqual(self.env['document.management.document'].browse(expired['id']).state, 'draft')
        board_soon = self.api.get_approval_board('expiring_soon')
        board_expired = self.api.get_approval_board('expired')
        self.assertGreaterEqual(board_soon['kpis']['expiring_soon'], 1)
        self.assertGreaterEqual(board_expired['kpis']['expired'], 1)
        self.assertTrue(any(row['document'] == 'P6 Soon Expiry' for row in board_soon['rows']))
        self.assertTrue(any(row['document'] == 'P6 Expired Overlay' for row in board_expired['rows']))
        document = self.env['document.management.document'].browse(expired['id'])
        service = DocumentNotificationService(self.env)
        service.ensure_expiry_notifications(document)
        service.ensure_expiry_notifications(document)
        service.ensure_expiry_notifications(document)
        notes = self.env['document.management.notification'].search([
            ('document_id', '=', document.id),
            ('kind', '=', 'expired'),
            ('is_read', '=', False),
        ])
        self.assertEqual(len(notes), 1)
        renewed = self.api.renew_document(expired['id'], today + timedelta(days=40), self._file())
        self.assertEqual(renewed['current_version'], 'v1.0')
        self.assertEqual(renewed['expiry_date'], today + timedelta(days=40))
        self.assertTrue(self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', expired['id']),
            ('event_type', '=', 'expiry_renewed'),
        ]))

    def test_10_versioning_restore_and_unauthorized(self):
        owner = self._user('p6_ver_owner')
        stranger = self._user('p6_ver_stranger')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Versioned',
            'type_id': self._type('P6 Ver Type', False).id,
            'access_level': 'private',
        }, self._file())
        first_id = dto['current_version_id']
        updated = self.api.with_user(owner).upload_new_version(dto['id'], self._file('next.pdf'))
        self.assertEqual(updated['current_version'], 'v1.1')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(len(document.version_ids.filtered('is_current')), 1)
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).upload_new_version(dto['id'], self._file('hack.pdf'))
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).restore_version(dto['id'], first_id)
        restored = self.api.with_user(owner).restore_version(dto['id'], first_id)
        self.assertEqual(restored['current_version'], 'v1.2')
        self.assertEqual(len(document.version_ids.filtered('is_current')), 1)

    def test_11_acl_modes_and_inherited_grandparent(self):
        owner = self._user('p6_acl_owner')
        viewer = self._user('p6_acl_viewer')
        editor = self._user('p6_acl_editor')
        no_dl = self._user('p6_acl_nodl')
        stranger = self._user('p6_acl_stranger')
        grand = self.env['document.management.folder'].create({'name': 'P6 Grand'})
        parent = self.env['document.management.folder'].create({
            'name': 'P6 Parent',
            'parent_id': grand.id,
        })
        child = self.env['document.management.folder'].create({
            'name': 'P6 Child',
            'parent_id': parent.id,
        })
        self.env['document.management.access.rule'].create({
            'folder_id': grand.id,
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
        })
        inherited = self.api.with_user(owner).create_draft({
            'name': 'P6 Deep Inherit',
            'folder_id': child.id,
            'access_level': 'role_restricted',
        }, None)
        detail = self.api.with_user(viewer).get_document(inherited['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertFalse(detail['permissions']['write'])
        hits = self.api.with_user(viewer).keyword_search('P6 Deep Inherit')
        self.assertEqual(hits['total'], 1)
        repo = self.api.with_user(viewer).get_repository_data('all', {}, 'Deep Inherit')
        self.assertTrue(any(item['id'] == inherited['id'] for item in repo['items']))

        shared = self.api.with_user(owner).create_draft({
            'name': 'P6 Shared ACL',
            'access_level': 'role_restricted',
        }, None)
        self.api.with_user(owner).add_access(shared['id'], {
            'partner_type': 'user',
            'user_id': editor.id,
            'role': 'editor',
        })
        editor_detail = self.api.with_user(editor).get_document(shared['id'])
        self.assertTrue(editor_detail['permissions']['write'])
        self.assertFalse(editor_detail['permissions']['share'])
        with self.assertRaises(AccessError):
            self.api.with_user(editor).add_access(shared['id'], {
                'partner_type': 'user',
                'user_id': stranger.id,
                'role': 'editor',
            })
        self.api.with_user(owner).add_access(shared['id'], {
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
        })
        with self.assertRaises(AccessError):
            self.api.with_user(viewer).add_access(shared['id'], {
                'partner_type': 'user',
                'user_id': stranger.id,
                'role': 'editor',
            })
        rule = self.env['document.management.access.rule'].create({
            'document_id': shared['id'],
            'partner_type': 'user',
            'user_id': no_dl.id,
            'role': 'viewer',
        })
        rule.with_context(dm_lifecycle=True).write({'perm_download': False})
        no_dl_detail = self.api.with_user(no_dl).get_document(shared['id'])
        self.assertTrue(no_dl_detail['permissions']['read'])
        self.assertFalse(no_dl_detail['permissions']['download'])
        with self.assertRaises(AccessError):
            self.api.with_user(no_dl).download_document(shared['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).get_document(shared['id'])

    def test_12_owner_cannot_be_revoked(self):
        owner = self._user('p6_owner_protect')
        dto = self.api.with_user(owner).create_draft({'name': 'P6 Owner Rule'}, None)
        matrix = self.api.with_user(owner).get_access_matrix(dto['id'])
        owner_rule = next(row for row in matrix['rows'] if row['role'] == 'owner')
        with self.assertRaises(UserError):
            self.api.with_user(owner).revoke_access(dto['id'], owner_rule['id'])
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'access_changed'),
        ])
        viewer = self._user('p6_owner_viewer')
        self.api.with_user(owner).add_access(dto['id'], {
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
        })
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'access_changed'),
        ])
        self.assertTrue(events)

    def test_13_share_token_security(self):
        owner = self._user('p6_share_owner')
        stranger = self._user('p6_share_stranger')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Share Token',
            'type_id': self._type('P6 Share Type', False).id,
            'access_level': 'private',
        }, self._file())
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).create_share_link(dto['id'], {
                'expiry': fields.Datetime.now() + timedelta(days=1),
            })
        link = self.api.with_user(owner).create_share_link(dto['id'], {
            'expiry': fields.Datetime.now() + timedelta(days=1),
            'perm_download': True,
        })
        token = link['url'].rsplit('/', 1)[-1]
        record = self.env['document.management.share.link'].browse(link['id'])
        payload = record._dm_prepare_download()
        self.assertTrue(payload['content'])
        self.assertNotIn('token', payload)
        self.assertNotIn(token, json.dumps(payload, default=str))
        downloaded = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'downloaded'),
        ])
        self.assertFalse(any(token in (event.metadata or '') for event in downloaded))

        readonly = self.env['document.management.share.link'].create({
            'document_id': dto['id'],
            'expiry': fields.Datetime.now() + timedelta(days=1),
            'perm_read': True,
            'perm_download': False,
        })
        with self.assertRaises(AccessError):
            readonly._dm_prepare_download()

        expired = self.env['document.management.share.link'].create({
            'document_id': dto['id'],
            'expiry': fields.Datetime.now() - timedelta(hours=1),
        })
        with self.assertRaises(AccessError):
            expired._dm_prepare_download()

        self.api.with_user(owner).revoke_share_link(dto['id'], link['id'])
        with self.assertRaises(AccessError):
            record._dm_prepare_download()

        archived = self.api.with_user(owner).upload_document({
            'name': 'P6 Share Archived',
            'type_id': self._type('P6 Share Arch Type', False).id,
        }, self._file())
        arch_link = self.api.with_user(owner).create_share_link(archived['id'], {
            'expiry': fields.Datetime.now() + timedelta(days=1),
        })
        self.api.with_user(owner).archive_document(archived['id'])
        with self.assertRaises(UserError):
            self.api.with_user(owner).create_share_link(archived['id'], {
                'expiry': fields.Datetime.now() + timedelta(days=1),
            })
        with self.assertRaises(AccessError):
            self.env['document.management.share.link'].browse(arch_link['id'])._dm_prepare_download()

        missing = self.env['document.management.share.link']._dm_find_by_token('not-a-real-token')
        self.assertFalse(missing)

    def test_14_repository_views_filters_and_actions(self):
        owner = self._user('p6_repo_owner')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Repo Doc',
            'department_label': 'Finance',
            'type_id': self._type('P6 Repo Type', False).id,
        }, self._file())
        self.api.with_user(owner).toggle_favorite(dto['id'])
        mine = self.api.with_user(owner).get_repository_data('my', {'department': 'Finance'}, 'Repo Doc')
        self.assertTrue(any(item['id'] == dto['id'] for item in mine['items']))
        fav = self.api.with_user(owner).get_repository_data('favorites', {}, None)
        self.assertTrue(any(item['id'] == dto['id'] for item in fav['items']))
        recent = self.api.with_user(owner).get_repository_data('recent', {}, None)
        self.assertTrue(any(item['id'] == dto['id'] for item in recent['items']))
        self.api.with_user(owner).archive_document(dto['id'])
        archived = self.api.with_user(owner).get_repository_data('archived', {}, None)
        self.assertTrue(any(item['id'] == dto['id'] for item in archived['items']))
        restored = self.api.restore_document(dto['id'])
        self.assertEqual(restored['state'], 'approved')

    def test_15_details_tabs_and_download_payload(self):
        dto = self._upload('P6 Details Tabs', requires_approval=False)
        detail = self.api.get_document(dto['id'])
        for key in ('file', 'versions', 'approvals', 'access', 'activity'):
            self.assertIn(key, detail)
        payload = self.api.download_document(dto['id'])
        self.assertIn('datas', payload)
        self.assertIn('name', payload)
        self.assertNotIn('attachment_id', payload)
        self.assertNotIn('/web/content/', json.dumps(payload, default=str))

    def test_16_search_and_csv_authorization(self):
        owner = self._user('p6_search_owner')
        stranger = self._user('p6_search_stranger')
        self.api.with_user(owner).create_draft({
            'name': 'P6 Secret Search',
            'description': 'hidden metadata',
            'access_level': 'private',
            'property_ref': 'PROP-P6',
            'asset_ref': 'ASSET-P6',
            'department_label': 'Legal',
        }, None)
        hits = self.api.with_user(stranger).keyword_search('P6 Secret Search')
        self.assertEqual(hits['total'], 0)
        csv_export = self.api.with_user(stranger).export_search_csv('P6 Secret Search', {})
        self.assertNotIn('P6 Secret Search', csv_export['csv'])
        self.assertNotIn('hidden metadata', csv_export['csv'])
        owner_hits = self.api.with_user(owner).keyword_search('Secret Search', {
            'property': 'PROP-P6',
            'department': 'Legal',
        })
        self.assertEqual(owner_hits['total'], 1)

    def test_17_ai_unavailable_contract(self):
        payload = self.api.ai_search('anything', {})
        self.assertEqual(payload, {
            'configured': False,
            'available': False,
            'message': 'AI Search is not configured',
            'answer': False,
            'citations': [],
            'sources': [],
            'related': [],
        })

    def test_18_notification_recipient_isolation(self):
        owner = self._user('p6_note_owner')
        other = self._user('p6_note_other')
        dto = self.api.with_user(owner).create_draft({'name': 'P6 Note Iso'}, None)
        document = self.env['document.management.document'].browse(dto['id'])
        note = DocumentNotificationService(self.env).create_notification(
            owner, document, 'access_granted', 'granted to owner'
        )
        listed = self.api.with_user(other).list_notifications()
        self.assertFalse(any(item['id'] == note.id for item in listed['items']))
        with self.assertRaises(UserError):
            self.api.with_user(other).mark_notification_read(note.id)
        self.assertFalse(note.is_read)
        self.assertTrue(self.api.with_user(owner).mark_notification_read(note.id))
        self.assertTrue(note.is_read)

    def test_19_audit_append_only_and_csv_auth(self):
        owner = self._user('p6_audit_owner')
        stranger = self._user('p6_audit_stranger')
        dto = self.api.with_user(owner).create_draft({
            'name': 'P6 Audit Secret',
            'access_level': 'private',
        }, None)
        event = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'created'),
        ], limit=1)
        with self.assertRaises(UserError):
            event.with_user(stranger).write({'document_name': 'tampered'})
        with self.assertRaises(UserError):
            event.with_user(stranger).unlink()
        csv_export = self.api.with_user(stranger).export_audit({})
        self.assertNotIn('P6 Audit Secret', csv_export['csv'])
        owner_export = self.api.with_user(owner).export_audit({'document_id': dto['id']})
        self.assertIn('P6 Audit Secret', owner_export['csv'])
        self.assertIn('created', owner_export['csv'])

    def test_20_delete_policy_roles(self):
        user = self._user('p6_del_user')
        manager = self._user('p6_del_manager', 'document_management.group_dm_manager')
        admin = self._user('p6_del_admin', 'document_management.group_dm_admin')
        dto = self.api.with_user(admin).upload_document({
            'name': 'P6 Delete Policy',
            'type_id': self._type('P6 Del Type', False).id,
        }, self._file())
        with self.assertRaises(AccessError):
            self.api.with_user(user).delete_document(dto['id'])
        with self.assertRaises(UserError):
            self.api.with_user(admin).delete_document(dto['id'])
        self.api.with_user(admin).archive_document(dto['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(user).delete_document(dto['id'])
        with self.assertRaises(AccessError):
            self.api.with_user(manager).delete_document(dto['id'])
        self.assertTrue(self.api.with_user(admin).delete_document(dto['id']))
        self.assertFalse(
            self.env['document.management.document'].with_context(active_test=False).browse(dto['id']).exists()
        )

    def test_21_multi_company_isolation(self):
        company_b = self.env['res.company'].create({'name': 'P6 Company B'})
        user_a = self._user('p6_co_a')
        user_b = self._user('p6_co_b', company=company_b)
        dto = self.api.with_user(user_a).upload_document({
            'name': 'P6 Company A Doc',
            'access_level': 'internal',
            'type_id': self._type('P6 CoA Type', False).id,
        }, self._file())
        api_b = self.api.with_user(user_b).with_company(company_b)
        self.assertEqual(api_b.keyword_search('P6 Company A Doc')['total'], 0)
        self.assertFalse(any(
            item['name'] == 'P6 Company A Doc'
            for item in api_b.get_repository_data('all', {}, None)['items']
        ))
        self.assertNotIn('P6 Company A Doc', api_b.export_search_csv('P6 Company A Doc', {})['csv'])
        self.assertNotIn('P6 Company A Doc', api_b.export_audit({})['csv'])
        with self.assertRaises(AccessError):
            api_b.get_document(dto['id'])
        with self.assertRaises(AccessError):
            api_b.download_document(dto['id'])
        with self.assertRaises(AccessError):
            api_b.create_share_link(dto['id'], {'expiry': fields.Datetime.now() + timedelta(days=1)})
        board = api_b.get_approval_board('approved')
        self.assertFalse(any(row.get('document') == 'P6 Company A Doc' for row in board['rows']))

    def test_22_rpc_cannot_bypass_backend(self):
        owner = self._user('p6_rpc_owner')
        stranger = self._user('p6_rpc_stranger')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 RPC Secret',
            'access_level': 'private',
            'type_id': self._type('P6 RPC Type', False).id,
        }, self._file())
        api = self.api.with_user(stranger)
        with self.assertRaises(AccessError):
            api.get_document(dto['id'])
        with self.assertRaises(AccessError):
            api.download_document(dto['id'])
        with self.assertRaises(AccessError):
            api.upload_new_version(dto['id'], self._file('x.pdf'))
        with self.assertRaises(AccessError):
            api.archive_document(dto['id'])
        with self.assertRaises(AccessError):
            api.restore_document(dto['id'])
        with self.assertRaises(AccessError):
            api.create_share_link(dto['id'], {'expiry': fields.Datetime.now() + timedelta(days=1)})
        with self.assertRaises(AccessError):
            api.add_access(dto['id'], {'partner_type': 'user', 'user_id': stranger.id, 'role': 'editor'})
        matrix = self.api.with_user(owner).get_access_matrix(dto['id'])
        owner_rule = next(row for row in matrix['rows'] if row['role'] == 'owner')
        with self.assertRaises(AccessError):
            api.revoke_access(dto['id'], owner_rule['id'])
        with self.assertRaises(AccessError):
            api.delete_document(dto['id'])
        board = api.get_approval_board('approved', {'document_id': dto['id']})
        self.assertFalse(board['selected'])

    def test_23_approval_decision_creates_new_notification_after_reject(self):
        owner = self._user('p6_note_cycle_owner')
        reviewer = self._user('p6_note_cycle_reviewer')
        dto = self.api.with_user(owner).upload_document({
            'name': 'P6 Decision Notes',
            'type_id': self._type('P6 Decision Type', True).id,
        }, self._file())
        first = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        self.api.with_user(reviewer).reject(first['id'], 'No')
        again = self.api.with_user(owner).submit_for_approval(dto['id'], [
            {'name': 'Review', 'approver_id': reviewer.id},
        ])
        self.api.with_user(reviewer).approve(again['id'])
        decisions = self.env['document.management.notification'].sudo().search([
            ('document_id', '=', dto['id']),
            ('user_id', '=', owner.id),
            ('kind', '=', 'approval_decision'),
        ])
        self.assertGreaterEqual(len(decisions), 2)

    def test_24_frozen_architecture_counts(self):
        models = [
            name for name in self.env.registry
            if name.startswith('document.management.')
        ]
        self.assertEqual(len(models), 18)
        menus = self.env['ir.ui.menu'].search([
            ('name', '=', 'Document Management'),
            ('parent_id', '=', False),
        ])
        self.assertTrue(menus)
        children = self.env['ir.ui.menu'].search([('parent_id', 'in', menus.ids)])
        self.assertEqual(len(children), 8)
        actions = self.env['ir.actions.client'].search([('tag', '=', 'document_management_app')])
        self.assertEqual(len(actions), 8)
        self.assertEqual(
            self.env['ir.module.module'].search([('name', '=', 'document_management')]).dependencies_id.mapped('name'),
            ['base', 'web'],
        )
