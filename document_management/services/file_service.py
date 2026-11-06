# -*- coding: utf-8 -*-
import base64
import os

from odoo.exceptions import UserError

from ..models.dm_mixin import (
    DM_ALLOWED_EXTENSIONS,
    DM_ALLOWED_MIMETYPES,
    DM_MAX_FILE_BYTES,
)
from .access_service import DocumentAccessService
from .audit_service import DocumentAuditService


class DocumentFileService:
    def __init__(self, env):
        self.env = env

    def _access(self):
        return DocumentAccessService(self.env)

    def _audit(self):
        return DocumentAuditService(self.env)

    def validate_upload(self, filename, mimetype, size, folder_id=None, name=None):
        errors = []
        normalized = (filename or '').replace('\\', '/')
        safe_name = os.path.basename(normalized)
        if not safe_name or '/' in normalized or safe_name != normalized:
            errors.append('Filename is invalid.')
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in DM_ALLOWED_EXTENSIONS:
            errors.append('File type is not allowed.')
        if not mimetype or mimetype not in DM_ALLOWED_MIMETYPES:
            errors.append('File MIME type is not allowed.')
        try:
            file_size = int(size or 0)
        except (TypeError, ValueError):
            file_size = 0
            errors.append('File size is invalid.')
        if file_size > DM_MAX_FILE_BYTES:
            errors.append('File exceeds the 50 MB size limit.')
        if file_size <= 0 and 'File size is invalid.' not in errors:
            errors.append('A file is required.')
        duplicate = False
        document_id = False
        if name:
            domain = [
                ('name', '=', name),
                ('company_id', '=', self.env.company.id),
            ]
            if folder_id:
                domain.append(('folder_id', '=', folder_id))
            else:
                domain.append(('folder_id', '=', False))
            match = self.env['document.management.document'].search(domain, limit=1)
            if match:
                duplicate = True
                document_id = match.id
        return {
            'ok': not errors,
            'errors': errors,
            'duplicate': duplicate,
            'document_id': document_id,
        }

    def decode_payload(self, file_payload):
        file_payload = file_payload or {}
        filename = file_payload.get('filename')
        mimetype = file_payload.get('mimetype')
        datas = file_payload.get('datas')
        if not datas:
            raise UserError('A file is required.')
        raw = base64.b64decode(datas)
        size = file_payload.get('size') or len(raw)
        result = self.validate_upload(
            filename,
            mimetype,
            size,
            file_payload.get('folder_id'),
            file_payload.get('name'),
        )
        if not result['ok']:
            raise UserError(result['errors'][0])
        return {
            'filename': os.path.basename(filename),
            'mimetype': mimetype,
            'datas': datas,
            'raw': raw,
            'size': int(size),
            'duplicate': result['duplicate'],
            'document_id': result['document_id'],
        }

    def create_attachment(self, version, payload):
        attachment = self.env['ir.attachment'].create({
            'name': payload['filename'],
            'datas': payload['datas'],
            'mimetype': payload['mimetype'],
            'public': False,
            'res_model': 'document.management.version',
            'res_id': version.id if version else 0,
        })
        if attachment.public:
            attachment.public = False
        return attachment

    def add_version(self, document, payload, note=None):
        current = document.current_version_id
        if current:
            major, minor = current.major, current.minor + 1
            current.with_context(dm_lifecycle=True).write({'is_current': False})
        else:
            major, minor = 1, 0
        attachment = self.create_attachment(self.env['document.management.version'], payload)
        version = self.env['document.management.version'].create({
            'document_id': document.id,
            'name': 'v%s.%s' % (major, minor),
            'major': major,
            'minor': minor,
            'note': note or False,
            'is_current': True,
            'author_id': self.env.user.id,
            'attachment_id': attachment.id,
            'file_name': payload['filename'],
            'file_size': payload['size'],
            'mimetype': payload['mimetype'],
        })
        attachment.write({
            'res_model': 'document.management.version',
            'res_id': version.id,
            'public': False,
        })
        document.with_context(dm_lifecycle=True).write({'current_version_id': version.id})
        self._audit().log(
            'uploaded',
            document=document,
            version_name=version.name,
        )
        return version

    def restore_version(self, document, version):
        if version.document_id != document:
            raise UserError('Version does not belong to this document.')
        if not version.attachment_id:
            raise UserError('Version file is missing.')
        payload = {
            'filename': version.file_name or version.attachment_id.name,
            'mimetype': version.mimetype or version.attachment_id.mimetype,
            'datas': version.attachment_id.datas,
            'size': version.file_size or version.attachment_id.file_size,
        }
        return self.add_version(document, payload, note='Restored from %s' % version.name)

    def _file_payload(self, document, version):
        self._access().require(document, 'download')
        if document.state == 'archived':
            self._audit().deny(document, 'Archived documents cannot be downloaded.')
        version = version or document.current_version_id
        if not version or not version.attachment_id:
            raise UserError('No file is available for this document.')
        attachment = version.attachment_id.sudo()
        if attachment.public:
            self._audit().deny(document, 'Public attachments are not allowed.')
        self._audit().log('downloaded', document=document, version_name=version.name)
        return {
            'name': version.file_name or attachment.name,
            'mimetype': version.mimetype or attachment.mimetype,
            'datas': attachment.datas,
        }

    def download_document(self, document_id, version_id=None):
        document = self._access().browse_document(document_id, 'download')
        version = False
        if version_id:
            version = self.env['document.management.version'].browse(version_id)
        return self._file_payload(document, version)

    def get_file(self, document_id, version_id=None):
        return self.download_document(document_id, version_id)
