# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError, UserError

DM_EXPIRY_SOON_DAYS = 30
DM_MAX_FILE_BYTES = 50 * 1024 * 1024
DM_ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.jpg', '.jpeg', '.png'}
DM_ALLOWED_MIMETYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/jpeg',
    'image/png',
}

DOCUMENT_STATES = [
    ('draft', 'Draft'),
    ('pending_approval', 'Pending Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('returned', 'Returned'),
    ('archived', 'Archived'),
]
DOCUMENT_STATE_VALUES = {item[0] for item in DOCUMENT_STATES}

ACCESS_LEVELS = [
    ('private', 'Private'),
    ('role_restricted', 'Role Restricted'),
    ('internal', 'Internal'),
    ('shared', 'Shared'),
]
ACCESS_LEVEL_VALUES = {item[0] for item in ACCESS_LEVELS}

CLASSIFICATIONS = [
    ('public', 'Public'),
    ('internal', 'Internal'),
    ('confidential', 'Confidential'),
]

EXPIRY_STATUSES = [
    ('none', 'None'),
    ('active', 'Active'),
    ('expiring_soon', 'Expiring Soon'),
    ('expired', 'Expired'),
]

ACCESS_ROLES = [
    ('owner', 'Owner'),
    ('editor', 'Editor'),
    ('viewer', 'Viewer'),
]

ACCESS_PARTNER_TYPES = [
    ('user', 'User'),
    ('group', 'Group'),
]

ACCESS_ORIGINS = [
    ('direct', 'Direct'),
]

ACCESS_RULE_STATES = [
    ('active', 'Active'),
    ('revoked', 'Revoked'),
]

SHARE_LINK_STATES = [
    ('active', 'Active'),
    ('expired', 'Expired'),
    ('revoked', 'Revoked'),
]

APPROVAL_REQUEST_STATES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('returned', 'Returned'),
]

APPROVAL_STEP_STATES = [
    ('waiting', 'Waiting'),
    ('active', 'Active'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('returned', 'Returned'),
    ('skipped', 'Skipped'),
]

AUDIT_EVENT_TYPES = [
    ('created', 'Created'),
    ('uploaded', 'Uploaded'),
    ('metadata_modified', 'Metadata Modified'),
    ('downloaded', 'Downloaded'),
    ('access_changed', 'Access Changed'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('returned', 'Returned'),
    ('expiry_renewed', 'Expiry Renewed'),
    ('archived', 'Archived'),
    ('restored', 'Restored'),
    ('deleted', 'Deleted'),
    ('unauthorized_access', 'Unauthorized Access'),
    ('viewed', 'Viewed'),
]

NOTIFICATION_KINDS = [
    ('expiry_soon', 'Expiring Soon'),
    ('expired', 'Expired'),
    ('approval_submitted', 'Approval Submitted'),
    ('approval_decision', 'Approval Decision'),
    ('access_granted', 'Access Granted'),
]

DOCUMENT_PROTECTED_FIELDS = {
    'state',
    'code',
    'prior_state',
    'current_version_id',
}

VERSION_PROTECTED_FIELDS = {
    'major',
    'minor',
    'attachment_id',
    'is_current',
}

ROLE_PERMISSIONS = {
    'owner': {
        'perm_read': True,
        'perm_write': True,
        'perm_download': True,
        'perm_share': True,
    },
    'editor': {
        'perm_read': True,
        'perm_write': True,
        'perm_download': True,
        'perm_share': False,
    },
    'viewer': {
        'perm_read': True,
        'perm_write': False,
        'perm_download': True,
        'perm_share': False,
    },
}

ALLOWED_TRANSITIONS = {
    'draft': {'pending_approval', 'approved', 'archived'},
    'pending_approval': {'approved', 'rejected', 'returned'},
    'returned': {'pending_approval', 'archived'},
    'rejected': {'pending_approval', 'archived'},
    'approved': {'archived'},
    'archived': set(),
}

METADATA_FIELDS = {
    'name',
    'description',
    'access_level',
    'classification',
    'owner_id',
    'type_id',
    'category_id',
    'folder_id',
    'tag_ids',
    'department_label',
    'property_ref',
    'asset_ref',
    'effective_date',
    'expiry_date',
    'expiry_notify',
}


class DocumentManagementMixin(models.AbstractModel):
    _name = 'document.management.mixin'
    _description = 'Document Management Access Helpers'

    def _dm_require_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _dm_require_user(self):
        self._dm_require_group(
            'document_management.group_dm_user',
            'Only Document Management Users can perform this action.',
        )

    def _dm_require_manager(self):
        self._dm_require_group(
            'document_management.group_dm_manager',
            'Only Document Management Managers can perform this action.',
        )

    def _dm_require_admin(self):
        self._dm_require_group(
            'document_management.group_dm_admin',
            'Only Document Management Administrators can perform this action.',
        )

    def _dm_guard_lifecycle_fields(self, vals, protected, message, creating=False):
        if self.env.context.get('dm_lifecycle'):
            return
        blocked = set(protected).intersection(vals)
        if creating:
            if vals.get('state') in (None, False, 'draft'):
                blocked.discard('state')
            if not vals.get('code'):
                blocked.discard('code')
            blocked.discard('prior_state')
        if blocked:
            raise UserError(message)
