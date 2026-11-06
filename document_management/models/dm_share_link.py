# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

from .dm_mixin import SHARE_LINK_STATES


class DocumentManagementShareLink(models.Model):
    _name = 'document.management.share.link'
    _description = 'Document Share Link'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char()
    document_id = fields.Many2one(
        'document.management.document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    token = fields.Char(required=True, index=True, copy=False)
    perm_read = fields.Boolean(default=True)
    perm_download = fields.Boolean(default=True)
    expiry = fields.Datetime(required=True)
    state = fields.Selection(
        SHARE_LINK_STATES,
        required=True,
        default='active',
        index=True,
        compute='_compute_state',
        store=True,
    )
    revoked_by = fields.Many2one('res.users', ondelete='set null')
    revoked_at = fields.Datetime()
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            'token_uniq',
            'unique(token)',
            'Share-link token must be unique.',
        ),
    ]

    @api.depends('expiry', 'revoked_at')
    def _compute_state(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.revoked_at:
                rec.state = 'revoked'
            elif rec.expiry and rec.expiry < now:
                rec.state = 'expired'
            else:
                rec.state = 'active'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(32)
            if not vals.get('name'):
                vals['name'] = 'Share link'
        return super().create(vals_list)

    @api.model
    def _dm_find_by_token(self, token):
        if not token:
            return self.browse()
        return self.sudo().search([('token', '=', token)], limit=1)

    def _dm_prepare_download(self):
        self.ensure_one()
        from ..services.audit_service import DocumentAuditService
        audit = DocumentAuditService(self.env)
        document = self.document_id
        if self.state != 'active' or self.revoked_at or not self.expiry or fields.Datetime.now() > self.expiry:
            audit.deny(document, 'Share link is not active.', metadata={'reason': 'inactive_share_link'})
        if not document or document.state == 'archived':
            audit.deny(document, 'Archived documents cannot be downloaded.', metadata={'reason': 'archived_share'})
        if not self.perm_read and not self.perm_download:
            audit.deny(document, 'Share link has no permissions.', metadata={'reason': 'share_denied'})
        if not self.perm_download:
            audit.deny(document, 'Share link does not allow download.', metadata={'reason': 'share_download_denied'})
        version = document.current_version_id
        if not version or not version.attachment_id:
            raise UserError('No file is available for this document.')
        attachment = version.attachment_id.sudo()
        if attachment.public:
            audit.deny(document, 'Public attachments are not allowed.', metadata={'reason': 'public_attachment'})
        audit.log('downloaded', document=document, version_name=version.name, metadata={'source': 'share_link'})
        return {
            'content': attachment.raw or b'',
            'filename': version.file_name or attachment.name or 'document',
            'mimetype': attachment.mimetype or 'application/octet-stream',
        }
