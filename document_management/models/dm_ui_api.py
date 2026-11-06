# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError

from ..services.access_service import DocumentAccessService
from ..services.approval_service import DocumentApprovalService
from ..services.audit_service import DocumentAuditService
from ..services.document_service import DocumentService
from ..services.file_service import DocumentFileService
from ..services.notification_service import DocumentNotificationService
from ..services.search_service import DocumentSearchService


class DocumentManagementUiApi(models.TransientModel):
    _name = 'document.management.ui.api'
    _description = 'Document Management UI API'
    _inherit = ['document.management.mixin']

    def _documents(self):
        return DocumentService(self.env)

    def _files(self):
        return DocumentFileService(self.env)

    def _access(self):
        return DocumentAccessService(self.env)

    def _approvals(self):
        return DocumentApprovalService(self.env)

    def _search(self):
        return DocumentSearchService(self.env)

    def _audit(self):
        return DocumentAuditService(self.env)

    def _notifications(self):
        return DocumentNotificationService(self.env)

    def _ai(self):
        return self.env['document.management.ai.provider']

    @api.model
    def get_session_context(self):
        self._dm_require_user()
        user = self.env.user
        unread = self.env['document.management.notification'].search_count([
            ('user_id', '=', user.id),
            ('is_read', '=', False),
        ])
        group = self.env.ref('document_management.group_dm_user')
        users = self.env['res.users'].search([
            ('groups_id', 'in', [group.id]),
            ('company_ids', 'in', [self.env.company.id]),
            ('active', '=', True),
        ])
        return {
            'uid': user.id,
            'name': user.name,
            'is_user': user.has_group('document_management.group_dm_user'),
            'is_manager': user.has_group('document_management.group_dm_manager'),
            'is_admin': user.has_group('document_management.group_dm_admin'),
            'unread_notification_count': unread,
            'catalogs': self._documents()._catalogs(),
            'users': [{'id': item.id, 'name': item.name} for item in users],
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        self._dm_require_user()
        self._notifications().ensure_expiry_notifications()
        return self._documents().get_dashboard_data(filters)

    @api.model
    def get_repository_data(self, view=None, filters=None, search=None, offset=0, limit=40):
        self._dm_require_user()
        return self._documents().get_repository_data(view, filters, search, offset, limit)

    @api.model
    def get_document(self, document_id):
        self._dm_require_user()
        return self._documents().get_document(document_id)

    @api.model
    def validate_upload(self, filename, mimetype, size, folder_id=None, name=None):
        self._dm_require_user()
        return self._files().validate_upload(filename, mimetype, size, folder_id, name)

    @api.model
    def create_draft(self, vals=None, file_payload=None):
        self._dm_require_user()
        return self._documents().create_draft(vals, file_payload)

    @api.model
    def upload_document(self, vals=None, file_payload=None):
        self._dm_require_user()
        return self._documents().upload_document(vals, file_payload)

    @api.model
    def upload_new_version(self, document_id, file_payload=None, note=None):
        self._dm_require_user()
        return self._documents().upload_new_version(document_id, file_payload, note)

    @api.model
    def restore_version(self, document_id, version_id):
        self._dm_require_user()
        return self._documents().restore_version(document_id, version_id)

    @api.model
    def download_document(self, document_id, version_id=None):
        self._dm_require_user()
        return self._files().download_document(document_id, version_id)

    @api.model
    def get_file(self, document_id, version_id=None):
        self._dm_require_user()
        return self._files().get_file(document_id, version_id)

    @api.model
    def archive_document(self, document_id):
        self._dm_require_user()
        return self._documents().archive_document(document_id)

    @api.model
    def restore_document(self, document_id):
        self._dm_require_user()
        return self._documents().restore_document(document_id)

    @api.model
    def delete_document(self, document_id):
        self._dm_require_admin()
        return self._documents().delete_document(document_id)

    @api.model
    def toggle_favorite(self, document_id):
        self._dm_require_user()
        return self._documents().toggle_favorite(document_id)

    @api.model
    def add_comment(self, document_id, body):
        self._dm_require_user()
        return self._documents().add_comment(document_id, body)

    @api.model
    def get_access_matrix(self, document_id):
        self._dm_require_user()
        return self._access().get_access_matrix(document_id)

    @api.model
    def add_access(self, document_id, vals=None):
        self._dm_require_user()
        return self._access().add_access(document_id, vals)

    @api.model
    def revoke_access(self, document_id, rule_id):
        self._dm_require_user()
        return self._access().revoke_access(document_id, rule_id)

    @api.model
    def create_share_link(self, document_id, vals=None):
        self._dm_require_user()
        return self._access().create_share_link(document_id, vals)

    @api.model
    def revoke_share_link(self, document_id, link_id):
        self._dm_require_user()
        return self._access().revoke_share_link(document_id, link_id)

    @api.model
    def get_approval_board(self, tab=None, filters=None):
        self._dm_require_user()
        self._notifications().ensure_expiry_notifications()
        return self._approvals().get_approval_board(tab, filters)

    @api.model
    def submit_for_approval(self, document_id, steps=None):
        self._dm_require_user()
        return self._approvals().submit_for_approval(document_id, steps)

    @api.model
    def approve(self, request_id, comment=None):
        self._dm_require_user()
        return self._approvals().approve(request_id, comment)

    @api.model
    def reject(self, request_id, comment=None):
        self._dm_require_user()
        return self._approvals().reject(request_id, comment)

    @api.model
    def request_changes(self, request_id, comment=None):
        self._dm_require_user()
        return self._approvals().request_changes(request_id, comment)

    @api.model
    def renew_document(self, document_id, expiry_date=None, file_payload=None):
        self._dm_require_user()
        return self._documents().renew_document(document_id, expiry_date, file_payload)

    @api.model
    def keyword_search(self, query=None, filters=None):
        self._dm_require_user()
        return self._search().keyword_search(query, filters)

    @api.model
    def ai_search(self, query=None, filters=None):
        self._dm_require_user()
        provider = self._ai()
        if not provider.is_configured():
            return {
                'configured': False,
                'available': False,
                'message': 'AI Search is not configured',
                'answer': False,
                'citations': [],
                'sources': [],
                'related': [],
            }
        raise UserError('AI Search is not configured')

    @api.model
    def export_search_csv(self, query=None, filters=None, mode=None):
        self._dm_require_user()
        return self._search().export_search_csv(query, filters, mode)

    @api.model
    def get_audit_data(self, filters=None, offset=0, limit=50):
        self._dm_require_user()
        return self._audit().get_audit_data(filters, offset, limit)

    @api.model
    def export_audit(self, filters=None):
        self._dm_require_user()
        return self._audit().export_audit(filters)

    @api.model
    def list_notifications(self):
        self._dm_require_user()
        return self._notifications().list_notifications()

    @api.model
    def mark_notification_read(self, notification_id):
        self._dm_require_user()
        return self._notifications().mark_read(notification_id)

    @api.model
    def create_category(self, vals=None):
        self._dm_require_manager()
        return self._documents().create_category(vals)

    @api.model
    def create_type(self, vals=None):
        self._dm_require_manager()
        return self._documents().create_type(vals)

    @api.model
    def create_folder(self, vals=None):
        self._dm_require_manager()
        return self._documents().create_folder(vals)

    @api.model
    def create_tag(self, vals=None):
        self._dm_require_user()
        return self._documents().create_tag(vals)

    @api.model
    def create_access_group(self, vals=None):
        self._dm_require_manager()
        return self._access().create_access_group(vals)
