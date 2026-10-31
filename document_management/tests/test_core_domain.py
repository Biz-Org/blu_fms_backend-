# -*- coding: utf-8 -*-
"""Phase 3 core-domain tests."""
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
@tagged('post_install', '-at_install', 'dm_core')
class TestDmCoreDomain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()
        cls.api = cls.env['document.management.ui.api']
        cls.pdf = {
            'filename': 'policy.pdf',
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 test-file').decode(),
            'size': 18,
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

    def _create_uploaded(self, name='Core Doc', requires_approval=True, **vals):
        doc_type = self.env['document.management.document.type'].create({
            'name': 'Type %s' % name,
            'requires_approval': requires_approval,
        })
        vals.setdefault('name', name)
        vals.setdefault('type_id', doc_type.id)
        return self.api.upload_document(vals, self._file())

    def test_01_document_creation(self):
        dto = self.api.create_draft({'name': 'Created Draft'}, None)
        self.assertEqual(dto['name'], 'Created Draft')
        self.assertEqual(dto['state'], 'draft')
        self.assertTrue(dto['id'])

    def test_02_code_generation(self):
        first = self.api.create_draft({'name': 'Code One'}, None)
        second = self.api.create_draft({'name': 'Code Two'}, None)
        self.assertTrue(first['code'].startswith('DM'))
        self.assertNotEqual(first['code'], second['code'])
        same_company = self.env['document.management.document'].search([
            ('company_id', '=', self.env.company.id),
            ('code', '=', first['code']),
        ])
        self.assertEqual(len(same_company), 1)

    def test_03_company_isolation(self):
        other = self.env['res.company'].create({'name': 'DM Other Co'})
        user = self._user('dm_other_user', company=other)
        dto = self.api.create_draft({'name': 'Company A Doc'}, None)
        with self.assertRaises(AccessError):
            self.api.with_user(user).with_company(other).get_document(dto['id'])

    def test_04_document_visibility(self):
        owner = self._user('dm_owner_vis')
        stranger = self._user('dm_stranger_vis')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Private Visibility',
            'access_level': 'private',
        }, None)
        visible = self.api.with_user(stranger).keyword_search('Private Visibility')
        self.assertEqual(visible['total'], 0)
        self.assertTrue(self.api.with_user(owner).get_document(dto['id']))

    def test_05_owner_permissions(self):
        owner = self._user('dm_owner_perm')
        dto = self.api.with_user(owner).create_draft({'name': 'Owner Perms'}, None)
        detail = self.api.with_user(owner).get_document(dto['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertTrue(detail['permissions']['write'])
        self.assertTrue(detail['permissions']['download'])
        self.assertTrue(detail['permissions']['share'])

    def test_06_editor_permissions(self):
        owner = self._user('dm_owner_editor')
        editor = self._user('dm_editor')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Editor Doc',
            'access_level': 'role_restricted',
        }, None)
        self.api.with_user(owner).add_access(dto['id'], {
            'partner_type': 'user',
            'user_id': editor.id,
            'role': 'editor',
            'perm_share': True,
        })
        detail = self.api.with_user(editor).get_document(dto['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertTrue(detail['permissions']['write'])
        self.assertTrue(detail['permissions']['download'])
        self.assertFalse(detail['permissions']['share'])

    def test_07_viewer_permissions(self):
        owner = self._user('dm_owner_viewer')
        viewer = self._user('dm_viewer')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Viewer Doc',
            'access_level': 'role_restricted',
        }, None)
        self.api.with_user(owner).add_access(dto['id'], {
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
            'perm_write': True,
        })
        detail = self.api.with_user(viewer).get_document(dto['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertFalse(detail['permissions']['write'])
        self.assertTrue(detail['permissions']['download'])
        self.assertFalse(detail['permissions']['share'])

    def test_08_internal_access(self):
        owner = self._user('dm_owner_internal')
        colleague = self._user('dm_colleague')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Internal Doc',
            'access_level': 'internal',
        }, None)
        detail = self.api.with_user(colleague).get_document(dto['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertFalse(detail['permissions']['write'])
        self.assertFalse(detail['permissions']['download'])
        self.assertFalse(detail['permissions']['share'])

    def test_09_private_access(self):
        owner = self._user('dm_owner_private')
        stranger = self._user('dm_private_stranger')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Really Private',
            'access_level': 'private',
        }, None)
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).get_document(dto['id'])

    def test_10_role_restricted_access(self):
        owner = self._user('dm_owner_rr')
        stranger = self._user('dm_rr_stranger')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Restricted Doc',
            'access_level': 'role_restricted',
        }, None)
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).get_document(dto['id'])

    def test_11_folder_inherited_access(self):
        owner = self._user('dm_owner_folder')
        viewer = self._user('dm_folder_viewer')
        parent = self.env['document.management.folder'].create({'name': 'Parent Folder'})
        child = self.env['document.management.folder'].create({
            'name': 'Child Folder',
            'parent_id': parent.id,
        })
        self.env['document.management.access.rule'].create({
            'folder_id': parent.id,
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
        })
        dto = self.api.with_user(owner).create_draft({
            'name': 'Inherited Doc',
            'folder_id': child.id,
            'access_level': 'role_restricted',
        }, None)
        detail = self.api.with_user(viewer).get_document(dto['id'])
        self.assertTrue(detail['permissions']['read'])
        self.assertFalse(detail['permissions']['write'])
        matrix = self.api.with_user(owner).get_access_matrix(dto['id'])
        self.assertTrue(any(row.get('origin') == 'inherited' for row in matrix['rows']))

    def test_12_revoked_access(self):
        owner = self._user('dm_owner_revoke')
        viewer = self._user('dm_revoked')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Revoke Doc',
            'access_level': 'role_restricted',
        }, None)
        matrix = self.api.with_user(owner).add_access(dto['id'], {
            'partner_type': 'user',
            'user_id': viewer.id,
            'role': 'viewer',
        })
        rule_id = next(row['id'] for row in matrix['rows'] if row['type'] == 'user' and row['name'] == viewer.name)
        self.api.with_user(owner).revoke_access(dto['id'], rule_id)
        with self.assertRaises(AccessError):
            self.api.with_user(viewer).get_document(dto['id'])

    def test_13_upload_file_type_validation(self):
        result = self.api.validate_upload('virus.exe', 'application/octet-stream', 100)
        self.assertFalse(result['ok'])
        self.assertTrue(result['errors'])

    def test_14_fifty_mb_limit(self):
        result = self.api.validate_upload('file.pdf', 'application/pdf', 51 * 1024 * 1024)
        self.assertFalse(result['ok'])
        ok = self.api.validate_upload('file.pdf', 'application/pdf', 50 * 1024 * 1024)
        self.assertTrue(ok['ok'])

    def test_15_duplicate_detection(self):
        first = self.api.create_draft({'name': 'Same Name'}, None)
        duplicate = self.api.create_draft({'name': 'Same Name'}, None)
        self.assertTrue(duplicate.get('duplicate'))
        self.assertEqual(duplicate['document_id'], first['id'])
        versioned = self.api.upload_document(
            {'name': 'Same Name', 'create_new_version': True},
            self._file(),
        )
        self.assertEqual(versioned['id'], first['id'])
        self.assertEqual(versioned['current_version'], 'v1.0')

    def test_16_first_version_v10(self):
        dto = self.api.upload_document({'name': 'Versioned First'}, self._file())
        self.assertEqual(dto['current_version'], 'v1.0')
        version = self.env['document.management.version'].browse(dto['current_version_id'])
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 0)

    def test_17_new_version_minor_increment(self):
        dto = self.api.upload_document({'name': 'Versioned Next'}, self._file())
        updated = self.api.upload_new_version(dto['id'], self._file('policy-v2.pdf'))
        self.assertEqual(updated['current_version'], 'v1.1')
        again = self.api.upload_new_version(updated['id'], self._file('policy-v3.pdf'))
        self.assertEqual(again['current_version'], 'v1.2')

    def test_18_exactly_one_current_version(self):
        dto = self.api.upload_document({'name': 'One Current'}, self._file())
        self.api.upload_new_version(dto['id'], self._file('next.pdf'))
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(len(document.version_ids.filtered('is_current')), 1)
        self.assertEqual(document.current_version_id.name, 'v1.1')

    def test_19_restore_creates_new_version(self):
        dto = self.api.upload_document({'name': 'Restore Doc'}, self._file())
        first_id = dto['current_version_id']
        self.api.upload_new_version(dto['id'], self._file('changed.pdf'))
        restored = self.api.restore_version(dto['id'], first_id)
        self.assertEqual(restored['current_version'], 'v1.2')
        old = self.env['document.management.version'].browse(first_id)
        self.assertEqual(old.name, 'v1.0')
        self.assertFalse(old.is_current)
        with self.assertRaises(UserError):
            old.write({'note': 'rewrite history'})

    def test_20_lifecycle_transitions(self):
        dto = self._create_uploaded('Lifecycle Doc', requires_approval=True)
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'pending_approval')
        request = self.api.submit_for_approval(dto['id'], [{
            'name': 'Review',
            'approver_id': self.env.user.id,
        }])
        document.invalidate_recordset()
        self.assertEqual(document.state, 'pending_approval')
        self.api.approve(request['id'])
        document.invalidate_recordset()
        self.assertEqual(document.state, 'approved')

    def test_21_invalid_transitions(self):
        dto = self._create_uploaded('Invalid Transition', requires_approval=False)
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'approved')
        with self.assertRaises(UserError):
            document._dm_set_state('draft')
        with self.assertRaises(UserError):
            document.write({'state': 'archived'})

    def test_22_skip_approval(self):
        dto = self._create_uploaded('Skip Approval', requires_approval=False)
        self.assertEqual(dto['state'], 'approved')
        self.assertFalse(dto['requires_approval'])

    def test_23_approval_required(self):
        dto = self._create_uploaded('Needs Approval', requires_approval=True)
        self.assertEqual(dto['state'], 'pending_approval')
        document = self.env['document.management.document'].browse(dto['id'])
        with self.assertRaises(UserError):
            document.write({'state': 'approved'})

    def test_24_sequential_approval(self):
        approver_one = self._user('dm_approver_one')
        approver_two = self._user('dm_approver_two')
        dto = self._create_uploaded('Sequential', requires_approval=True)
        request = self.api.submit_for_approval(dto['id'], [
            {'name': 'First', 'approver_id': approver_one.id},
            {'name': 'Second', 'approver_id': approver_two.id},
        ])
        self.assertEqual(request['steps'][0]['state'], 'active')
        self.assertEqual(request['steps'][1]['state'], 'waiting')
        mid = self.api.with_user(approver_one).approve(request['id'])
        self.assertEqual(mid['state'], 'pending')
        self.assertEqual(mid['steps'][1]['state'], 'active')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'pending_approval')
        final = self.api.with_user(approver_two).approve(request['id'])
        self.assertEqual(final['state'], 'approved')
        document.invalidate_recordset()
        self.assertEqual(document.state, 'approved')
        manager = self._user('dm_approver_manager', 'document_management.group_dm_manager')
        override_doc = self._create_uploaded('Manager Override', requires_approval=True)
        override_req = self.api.submit_for_approval(override_doc['id'], [{
            'name': 'Assigned Other',
            'approver_id': approver_one.id,
        }])
        overridden = self.api.with_user(manager).approve(override_req['id'])
        self.assertEqual(overridden['state'], 'approved')

    def test_25_reject_and_request_changes_require_comment(self):
        approver = self._user('dm_approver_comment')
        dto = self._create_uploaded('Comment Required', requires_approval=True)
        request = self.api.submit_for_approval(dto['id'], [{
            'name': 'Review',
            'approver_id': approver.id,
        }])
        with self.assertRaises(UserError):
            self.api.with_user(approver).reject(request['id'], '')
        with self.assertRaises(UserError):
            self.api.with_user(approver).request_changes(request['id'], None)
        rejected = self.api.with_user(approver).reject(request['id'], 'Missing exhibit')
        self.assertEqual(rejected['state'], 'rejected')
        document = self.env['document.management.document'].browse(dto['id'])
        self.assertEqual(document.state, 'rejected')
        returned_doc = self._create_uploaded('Return Required', requires_approval=True)
        returned_req = self.api.submit_for_approval(returned_doc['id'], [{
            'name': 'Review',
            'approver_id': approver.id,
        }])
        changed = self.api.with_user(approver).request_changes(returned_req['id'], 'Please revise')
        self.assertEqual(changed['state'], 'returned')

    def test_26_expiry_status(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        none = self.api.create_draft({'name': 'No Expiry'}, None)
        self.assertEqual(none['expiry_status'], 'none')
        expired = self.api.create_draft({
            'name': 'Expired Doc',
            'expiry_date': today - timedelta(days=1),
        }, None)
        self.assertEqual(expired['expiry_status'], 'expired')
        soon = self.api.create_draft({
            'name': 'Soon Doc',
            'expiry_date': today + timedelta(days=10),
        }, None)
        self.assertEqual(soon['expiry_status'], 'expiring_soon')
        active = self.api.create_draft({
            'name': 'Active Expiry',
            'expiry_date': today + timedelta(days=60),
        }, None)
        self.assertEqual(active['expiry_status'], 'active')

    def test_27_expiry_notification_dedup(self):
        today = fields.Date.context_today(self.env['document.management.document'])
        owner = self._user('dm_expiry_owner')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Expiry Notify',
            'expiry_date': today - timedelta(days=1),
            'expiry_notify': True,
        }, None)
        document = self.env['document.management.document'].browse(dto['id'])
        service = DocumentNotificationService(self.env)
        service.ensure_expiry_notifications(document)
        service.ensure_expiry_notifications(document)
        notes = self.env['document.management.notification'].search([
            ('document_id', '=', document.id),
            ('user_id', '=', owner.id),
            ('kind', '=', 'expired'),
            ('is_read', '=', False),
        ])
        self.assertEqual(len(notes), 1)

    def test_28_favorites(self):
        owner = self._user('dm_fav_owner')
        dto = self.api.with_user(owner).create_draft({'name': 'Favorite Doc'}, None)
        added = self.api.with_user(owner).toggle_favorite(dto['id'])
        self.assertTrue(added['favorited'])
        again = self.api.with_user(owner).toggle_favorite(dto['id'])
        self.assertFalse(again['favorited'])
        self.assertEqual(self.env['document.management.favorite'].search_count([
            ('document_id', '=', dto['id']),
            ('user_id', '=', owner.id),
        ]), 0)

    def test_29_comments(self):
        owner = self._user('dm_comment_owner')
        stranger = self._user('dm_comment_stranger')
        dto = self.api.with_user(owner).create_draft({
            'name': 'Comment Doc',
            'access_level': 'private',
        }, None)
        comment = self.api.with_user(owner).add_comment(dto['id'], 'Looks good')
        self.assertEqual(comment['body'], 'Looks good')
        with self.assertRaises(AccessError):
            self.api.with_user(stranger).add_comment(dto['id'], 'No access')

    def test_30_share_link_creation(self):
        dto = self.api.upload_document({'name': 'Share Create'}, self._file())
        expiry = fields.Datetime.now() + timedelta(days=2)
        link = self.api.create_share_link(dto['id'], {'expiry': expiry, 'perm_download': True})
        self.assertTrue(link['url'].startswith('/document_management/share/'))
        token = link['url'].rsplit('/', 1)[-1]
        self.assertGreaterEqual(len(token), 32)
        record = self.env['document.management.share.link'].browse(link['id'])
        self.assertNotEqual(record.token, token[0:8])
        self.assertEqual(record.state, 'active')

    def test_31_share_link_expiry(self):
        dto = self.api.upload_document({'name': 'Share Expiry'}, self._file())
        link = self.env['document.management.share.link'].create({
            'document_id': dto['id'],
            'expiry': fields.Datetime.now() - timedelta(hours=1),
        })
        self.assertEqual(link.state, 'expired')

    def test_32_share_link_revocation(self):
        dto = self.api.upload_document({'name': 'Share Revoke'}, self._file())
        created = self.api.create_share_link(dto['id'], {
            'expiry': fields.Datetime.now() + timedelta(days=1),
        })
        self.assertTrue(self.api.revoke_share_link(dto['id'], created['id']))
        link = self.env['document.management.share.link'].browse(created['id'])
        self.assertEqual(link.state, 'revoked')

    def test_33_attachment_non_public(self):
        dto = self.api.upload_document({'name': 'Attachment Doc'}, self._file())
        version = self.env['document.management.version'].browse(dto['current_version_id'])
        self.assertFalse(version.attachment_id.public)
        self.assertEqual(version.attachment_id.res_model, 'document.management.version')
        self.assertEqual(version.attachment_id.res_id, version.id)

    def test_34_unauthorized_download_audit(self):
        owner = self._user('dm_dl_owner')
        colleague = self._user('dm_dl_colleague')
        dto = self.api.with_user(owner).upload_document({
            'name': 'No Download',
            'access_level': 'internal',
        }, self._file())
        try:
            self.api.with_user(colleague).download_document(dto['id'])
        except AccessError as exc:
            self.assertIn('not allowed', str(exc).lower())
        else:
            self.fail('Expected AccessError for unauthorized download')
        events = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'unauthorized_access'),
        ])
        self.assertTrue(events)

    def test_35_audit_append_only(self):
        dto = self.api.create_draft({'name': 'Audit Lock'}, None)
        event = self.env['document.management.audit.event'].sudo().search([
            ('document_id', '=', dto['id']),
            ('event_type', '=', 'created'),
        ], limit=1)
        self.assertTrue(event)
        self.assertEqual(event.document_name, 'Audit Lock')
        user = self._user('dm_audit_user')
        with self.assertRaises(UserError):
            event.with_user(user).write({'document_name': 'tamper'})
        with self.assertRaises(UserError):
            event.with_user(user).unlink()

    def test_36_keyword_search_authorization(self):
        owner = self._user('dm_search_owner')
        stranger = self._user('dm_search_stranger')
        self.api.with_user(owner).create_draft({
            'name': 'Secret Search Target',
            'description': 'unique-search-token',
            'access_level': 'private',
        }, None)
        hits = self.api.with_user(stranger).keyword_search('unique-search-token')
        self.assertEqual(hits['total'], 0)
        owner_hits = self.api.with_user(owner).keyword_search('unique-search-token')
        self.assertEqual(owner_hits['total'], 1)

    def test_37_ai_unconfigured_response(self):
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

    def test_38_notification_visibility(self):
        owner = self._user('dm_note_owner')
        other = self._user('dm_note_other')
        dto = self.api.with_user(owner).create_draft({'name': 'Note Doc'}, None)
        document = self.env['document.management.document'].browse(dto['id'])
        DocumentNotificationService(self.env).create_notification(
            owner,
            document,
            'access_granted',
            'Access granted to Note Doc',
        )
        mine = self.api.with_user(owner).list_notifications()
        theirs = self.api.with_user(other).list_notifications()
        self.assertTrue(any(item['document_id'] == dto['id'] for item in mine['items']))
        self.assertFalse(any(item['document_id'] == dto['id'] for item in theirs['items']))
        note_id = next(item['id'] for item in mine['items'] if item['document_id'] == dto['id'])
        self.assertTrue(self.api.with_user(owner).mark_notification_read(note_id))

    def test_39_admin_archive_first_delete(self):
        admin = self._user('dm_admin_del', 'document_management.group_dm_admin')
        skip_type = self.env['document.management.document.type'].create({
            'name': 'Delete Type',
            'requires_approval': False,
        })
        dto = self.api.with_user(admin).upload_document(
            {'name': 'Delete Me', 'type_id': skip_type.id},
            self._file(),
        )
        with self.assertRaises(UserError):
            self.api.with_user(admin).delete_document(dto['id'])
        self.api.with_user(admin).archive_document(dto['id'])
        self.assertTrue(self.api.with_user(admin).delete_document(dto['id']))
        self.assertFalse(self.env['document.management.document'].with_context(active_test=False).browse(dto['id']).exists())

    def test_40_multi_company_isolation(self):
        other = self.env['res.company'].create({'name': 'DM Isolated Co'})
        user_a = self._user('dm_comp_a')
        user_b = self._user('dm_comp_b', company=other)
        dto = self.api.with_user(user_a).create_draft({
            'name': 'Company Bound',
            'access_level': 'internal',
        }, None)
        hits = self.api.with_user(user_b).with_company(other).keyword_search('Company Bound')
        self.assertEqual(hits['total'], 0)
        with self.assertRaises(AccessError):
            self.api.with_user(user_b).with_company(other).get_document(dto['id'])

    def test_catalogs_start_empty_and_are_creatable(self):
        screenshot_names = ['Policies', 'Contracts', 'Vendors', 'Municipal']
        self.assertFalse(self.env['document.management.category'].search([('name', 'in', screenshot_names)]))
        category = self.api.create_category({'name': 'Runtime Category'})
        doc_type = self.api.create_type({'name': 'Runtime Type', 'requires_approval': False})
        folder = self.api.create_folder({'name': 'Runtime Folder'})
        tag = self.api.create_tag({'name': 'Runtime Tag'})
        self.assertTrue(category['id'])
        self.assertTrue(doc_type['id'])
        self.assertTrue(folder['id'])
        self.assertTrue(tag['id'])

    def test_session_and_repository_contracts(self):
        session = self.api.get_session_context()
        self.assertIn('uid', session)
        self.assertIn('unread_notification_count', session)
        self.api.create_draft({'name': 'Repo Item'}, None)
        repo = self.api.get_repository_data()
        self.assertGreaterEqual(repo['total'], 1)
        self.assertTrue(any(item['name'] == 'Repo Item' for item in repo['items']))
