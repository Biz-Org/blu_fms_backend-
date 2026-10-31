# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .access_service import DocumentAccessService
from .audit_service import DocumentAuditService
from .file_service import DocumentFileService
from .notification_service import DocumentNotificationService


class DocumentService:
    def __init__(self, env):
        self.env = env

    def _access(self):
        return DocumentAccessService(self.env)

    def _audit(self):
        return DocumentAuditService(self.env)

    def _files(self):
        return DocumentFileService(self.env)

    def _notifications(self):
        return DocumentNotificationService(self.env)

    def _visible(self, extra_domain=None, active_test=True, limit=None, offset=0, order='id desc'):
        records = self.env['document.management.document']
        if not active_test:
            records = records.with_context(active_test=False)
        return self._access().visible_documents(
            extra_domain=extra_domain,
            limit=limit,
            offset=offset,
            order=order,
            records=records,
        )

    def _file_format(self, file_name, mimetype):
        if file_name and '.' in file_name:
            return file_name.rsplit('.', 1)[-1].upper()
        return mimetype or False

    def _catalogs(self):
        return {
            'types': [{'id': rec.id, 'name': rec.name, 'requires_approval': rec.requires_approval}
                      for rec in self.env['document.management.document.type'].search([])],
            'categories': [{'id': rec.id, 'name': rec.name}
                           for rec in self.env['document.management.category'].search([])],
            'folders': [{'id': rec.id, 'name': rec.name, 'parent_id': rec.parent_id.id if rec.parent_id else False}
                        for rec in self.env['document.management.folder'].search([])],
            'tags': [{'id': rec.id, 'name': rec.name}
                     for rec in self.env['document.management.tag'].search([])],
            'groups': [{'id': rec.id, 'name': rec.name}
                       for rec in self.env['document.management.access.group'].search([])],
        }

    def _document_dto(self, document, include_details=False):
        favorite = document.favorite_ids.filtered(lambda f: f.user_id == self.env.user)
        version = document.current_version_id
        dto = {
            'id': document.id,
            'name': document.name,
            'code': document.code,
            'description': document.description,
            'state': document.state,
            'access_level': document.access_level,
            'classification': document.classification,
            'owner_id': document.owner_id.id,
            'owner': document.owner_id.name,
            'type_id': document.type_id.id if document.type_id else False,
            'type': document.type_id.name if document.type_id else False,
            'category_id': document.category_id.id if document.category_id else False,
            'category': document.category_id.name if document.category_id else False,
            'folder_id': document.folder_id.id if document.folder_id else False,
            'folder': document.folder_id.name if document.folder_id else False,
            'tag_ids': document.tag_ids.ids,
            'tags': document.tag_ids.mapped('name'),
            'department_label': document.department_label,
            'property_ref': document.property_ref,
            'asset_ref': document.asset_ref,
            'effective_date': document.effective_date,
            'expiry_date': document.expiry_date,
            'expiry_notify': document.expiry_notify,
            'requires_approval': document.requires_approval,
            'current_version_id': document.current_version_id.id if document.current_version_id else False,
            'current_version': document.current_version_id.name if document.current_version_id else False,
            'active': document.active,
            'expiry_status': document.expiry_status,
            'prior_state': document.prior_state,
            'company_id': document.company_id.id,
            'favorited': bool(favorite),
            'file_name': version.file_name if version else False,
            'file_size': version.file_size if version else 0,
            'mimetype': version.mimetype if version else False,
            'format': self._file_format(version.file_name, version.mimetype) if version else False,
            'author': version.author_id.name if version and version.author_id else document.owner_id.name,
            'write_date': document.write_date,
            'create_date': document.create_date,
            'permissions': {
                'read': self._access().can(document, 'read'),
                'write': self._access().can(document, 'write'),
                'download': self._access().can(document, 'download'),
                'share': self._access().can(document, 'share'),
                'archive': self._access().can(document, 'archive'),
                'delete': self._access().can(document, 'delete'),
            },
        }
        if include_details:
            from .approval_service import DocumentApprovalService
            dto['file'] = {
                'name': version.file_name if version else False,
                'size': version.file_size if version else 0,
                'mimetype': version.mimetype if version else False,
                'format': self._file_format(version.file_name, version.mimetype) if version else False,
            }
            dto['versions'] = [{
                'id': item.id,
                'name': item.name,
                'is_current': item.is_current,
                'file_name': item.file_name,
                'file_size': item.file_size,
                'mimetype': item.mimetype,
                'format': self._file_format(item.file_name, item.mimetype),
                'author': item.author_id.name if item.author_id else False,
                'note': item.note,
                'create_date': item.create_date,
            } for item in document.version_ids]
            dto['comments'] = [{
                'id': comment.id,
                'user': comment.user_id.name,
                'body': comment.body,
                'create_date': comment.create_date,
            } for comment in document.comment_ids]
            dto['approvals'] = [
                DocumentApprovalService(self.env)._request_dto(request)
                for request in document.approval_ids
            ]
            dto['access'] = self._access().get_access_matrix(document.id)
            dto['activity'] = [{
                'id': event.id,
                'timestamp': event.timestamp,
                'user': event.user_id.name if event.user_id else False,
                'action': event.event_type,
                'version': event.version_name,
                'document': event.document_name,
            } for event in self.env['document.management.audit.event'].sudo().search([
                ('document_id', '=', document.id),
            ], order='timestamp desc, id desc', limit=50)]
        return dto

    def _find_duplicate(self, name, folder_id=None, company_id=None):
        if not name:
            return self.env['document.management.document']
        domain = [
            ('name', '=', name),
            ('company_id', '=', company_id or self.env.company.id),
        ]
        domain.append(('folder_id', '=', folder_id or False))
        return self.env['document.management.document'].with_context(active_test=False).search(domain, limit=1)

    def _prepare_vals(self, vals):
        vals = dict(vals or {})
        vals.pop('state', None)
        vals.pop('code', None)
        vals.pop('prior_state', None)
        vals.pop('current_version_id', None)
        vals.pop('create_new_version', None)
        vals.pop('approval_steps', None)
        if not vals.get('name'):
            raise UserError('Document name is required.')
        vals.setdefault('company_id', self.env.company.id)
        vals.setdefault('owner_id', self.env.user.id)
        return vals

    def _duplicate_payload(self, existing):
        return {
            'duplicate': True,
            'document_id': existing.id,
            'code': existing.code,
            'name': existing.name,
            'current_version': existing.current_version_id.name if existing.current_version_id else False,
            'current_version_id': existing.current_version_id.id if existing.current_version_id else False,
            'message': 'A document with the same name already exists in this folder.',
        }

    def get_dashboard_data(self, filters=None):
        documents = self._visible(active_test=False)
        active = documents.filtered(lambda d: d.state != 'archived')
        return {
            'kpis': {
                'documents_total': len(active),
                'storage_used': sum(active.mapped('version_ids.file_size')),
                'pending_approval': len(active.filtered(lambda d: d.state == 'pending_approval')),
                'expiring_soon': len(active.filtered(lambda d: d.expiry_status == 'expiring_soon')),
            },
            'distribution': [{
                'id': category.id,
                'name': category.name,
                'count': len(active.filtered(lambda d: d.category_id == category)),
            } for category in active.mapped('category_id')],
            'status_summary': {
                'active': len(active),
                'archived': len(documents.filtered(lambda d: d.state == 'archived')),
                'shared': len(active.filtered(lambda d: d.access_level == 'shared')),
                'restricted': len(active.filtered(lambda d: d.access_level == 'role_restricted')),
            },
            'recent': [self._document_dto(doc) for doc in active[:8]],
            'quick_action_counts': {
                'pending_approvals': len(active.filtered(lambda d: d.state == 'pending_approval')),
                'expiring': len(active.filtered(lambda d: d.expiry_status in ('expiring_soon', 'expired'))),
            },
        }

    def get_repository_data(self, view=None, filters=None, search=None, offset=0, limit=40):
        filters = filters or {}
        view = view or filters.get('view') or 'all'
        search = search or filters.get('search')
        domain = []
        active_test = True
        order = 'id desc'
        if view == 'archived':
            active_test = False
            domain.append(('state', '=', 'archived'))
        elif view == 'favorites':
            domain.append(('favorite_ids.user_id', '=', self.env.user.id))
        elif view == 'my':
            domain.append(('owner_id', '=', self.env.user.id))
        elif view == 'shared':
            domain.append(('access_level', '=', 'shared'))
        elif view == 'recent':
            order = 'write_date desc, id desc'
        if filters.get('state') or filters.get('status'):
            domain.append(('state', '=', filters.get('state') or filters.get('status')))
        if filters.get('folder_id'):
            domain.append(('folder_id', '=', filters['folder_id']))
        if filters.get('category_id'):
            domain.append(('category_id', '=', filters['category_id']))
        if filters.get('type_id'):
            domain.append(('type_id', '=', filters['type_id']))
        if filters.get('department') or filters.get('department_label'):
            domain.append(('department_label', 'ilike', filters.get('department') or filters.get('department_label')))
        if search:
            domain.extend(['|', '|', ('name', 'ilike', search), ('code', 'ilike', search), ('description', 'ilike', search)])
        items = self._visible(extra_domain=domain, active_test=active_test, limit=limit, offset=offset, order=order)
        total_items = self._visible(extra_domain=domain, active_test=active_test)
        selected = False
        if filters.get('document_id'):
            selected = self.get_document(filters['document_id'])
        catalogs = self._catalogs()
        return {
            'items': [self._document_dto(doc) for doc in items],
            'categories': catalogs['categories'],
            'types': catalogs['types'],
            'folders': catalogs['folders'],
            'selected_panel': selected,
            'total': len(total_items),
            'view': view,
        }

    def get_document(self, document_id):
        if not document_id:
            return False
        document = self._access().browse_document(document_id, 'read')
        return self._document_dto(document, include_details=True)

    def create_draft(self, vals=None, file_payload=None):
        raw_vals = dict(vals or {})
        file_payload = dict(file_payload or {})
        create_new_version = bool(
            raw_vals.get('create_new_version') or file_payload.get('create_new_version')
        )
        folder_id = raw_vals.get('folder_id') or file_payload.get('folder_id')
        existing = self._find_duplicate(raw_vals.get('name'), folder_id)
        if existing and not create_new_version:
            return self._duplicate_payload(existing)
        if existing and create_new_version:
            if not file_payload.get('datas'):
                raise UserError('A file is required to create a new version.')
            return self.upload_new_version(existing.id, file_payload)
        vals = self._prepare_vals(raw_vals)
        document = self.env['document.management.document'].create(vals)
        self._access().ensure_owner_rule(document)
        if file_payload.get('datas'):
            file_payload['folder_id'] = document.folder_id.id if document.folder_id else False
            file_payload['name'] = document.name
            payload = self._files().decode_payload(file_payload)
            self._files().add_version(document, payload)
        return self._document_dto(document, include_details=True)

    def upload_document(self, vals=None, file_payload=None):
        raw_vals = dict(vals or {})
        file_payload = dict(file_payload or {})
        if not file_payload.get('datas'):
            raise UserError('A file is required.')
        create_new_version = bool(
            raw_vals.get('create_new_version') or file_payload.get('create_new_version')
        )
        folder_id = raw_vals.get('folder_id') or file_payload.get('folder_id')
        existing = self._find_duplicate(raw_vals.get('name'), folder_id)
        if existing and not create_new_version:
            return self._duplicate_payload(existing)
        if existing and create_new_version:
            return self.upload_new_version(existing.id, file_payload)
        vals = self._prepare_vals(raw_vals)
        document = self.env['document.management.document'].create(vals)
        self._access().ensure_owner_rule(document)
        file_payload['folder_id'] = document.folder_id.id if document.folder_id else False
        file_payload['name'] = document.name
        payload = self._files().decode_payload(file_payload)
        self._files().add_version(document, payload)
        steps = raw_vals.get('approval_steps') or file_payload.get('approval_steps')
        if not document.requires_approval:
            document._dm_set_state('approved')
        else:
            document._dm_set_state('pending_approval')
            if steps:
                from .approval_service import DocumentApprovalService
                DocumentApprovalService(self.env).submit_for_approval(document.id, steps)
        return self._document_dto(document, include_details=True)

    def upload_new_version(self, document_id, file_payload=None, note=None):
        document = self._access().browse_document(document_id, 'write')
        file_payload = dict(file_payload or {})
        if not file_payload.get('datas'):
            raise UserError('A file is required.')
        payload = self._files().decode_payload(file_payload)
        self._files().add_version(document, payload, note=note)
        return self._document_dto(document, include_details=True)

    def restore_version(self, document_id, version_id):
        document = self._access().browse_document(document_id, 'write')
        version = self.env['document.management.version'].browse(version_id)
        if not version.exists():
            raise UserError('Version not found.')
        self._files().restore_version(document, version)
        return self._document_dto(document, include_details=True)

    def archive_document(self, document_id):
        document = self._access().browse_document(document_id, 'archive')
        document._dm_archive()
        self._audit().log('archived', document=document)
        return self._document_dto(document)

    def restore_document(self, document_id):
        document = self.env['document.management.document'].with_context(active_test=False).browse(document_id)
        if not document.exists():
            raise UserError('Document not found.')
        self._access().require(document, 'restore')
        document._dm_restore()
        self._audit().log('restored', document=document)
        return self._document_dto(document)

    def delete_document(self, document_id):
        document = self.env['document.management.document'].with_context(active_test=False).browse(document_id)
        if not document.exists():
            raise UserError('Document not found.')
        self._access().require(document, 'delete')
        if document.state != 'archived':
            raise UserError('Documents must be archived before they can be deleted.')
        self._audit().log('deleted', document=document)
        attachments = document.version_ids.mapped('attachment_id')
        document.with_context(dm_lifecycle=True).write({'current_version_id': False})
        document.unlink()
        attachments.sudo().unlink()
        return True

    def toggle_favorite(self, document_id):
        document = self._access().browse_document(document_id, 'read')
        existing = self.env['document.management.favorite'].search([
            ('document_id', '=', document.id),
            ('user_id', '=', self.env.user.id),
        ], limit=1)
        if existing:
            existing.unlink()
            return {'favorited': False, 'document_id': document.id}
        self.env['document.management.favorite'].create({
            'document_id': document.id,
            'user_id': self.env.user.id,
        })
        return {'favorited': True, 'document_id': document.id}

    def add_comment(self, document_id, body):
        document = self._access().browse_document(document_id, 'read')
        if not (body or '').strip():
            raise UserError('Comment body is required.')
        comment = self.env['document.management.comment'].create({
            'document_id': document.id,
            'user_id': self.env.user.id,
            'body': body.strip(),
        })
        return {
            'id': comment.id,
            'user': comment.user_id.name,
            'body': comment.body,
            'create_date': comment.create_date,
            'document_id': document.id,
        }

    def renew_document(self, document_id, expiry_date=None, file_payload=None):
        document = self._access().browse_document(document_id, 'write')
        vals = {}
        if expiry_date:
            vals['expiry_date'] = expiry_date
        if vals:
            document.with_context(dm_skip_audit=True).write(vals)
        file_payload = dict(file_payload or {})
        if file_payload.get('datas'):
            payload = self._files().decode_payload(file_payload)
            self._files().add_version(document, payload, note='Renewal upload')
        self._audit().log('expiry_renewed', document=document)
        self._notifications().ensure_expiry_notifications(document)
        return self._document_dto(document, include_details=True)

    def create_category(self, vals=None):
        vals = dict(vals or {})
        if not vals.get('name'):
            raise UserError('Category name is required.')
        record = self.env['document.management.category'].create({
            'name': vals['name'],
            'sequence': vals.get('sequence', 10),
            'company_id': self.env.company.id,
        })
        return {'id': record.id, 'name': record.name}

    def create_type(self, vals=None):
        vals = dict(vals or {})
        if not vals.get('name'):
            raise UserError('Document type name is required.')
        record = self.env['document.management.document.type'].create({
            'name': vals['name'],
            'requires_approval': bool(vals.get('requires_approval', True)),
            'company_id': self.env.company.id,
        })
        return {'id': record.id, 'name': record.name, 'requires_approval': record.requires_approval}

    def create_folder(self, vals=None):
        vals = dict(vals or {})
        if not vals.get('name'):
            raise UserError('Folder name is required.')
        record = self.env['document.management.folder'].create({
            'name': vals['name'],
            'parent_id': vals.get('parent_id') or False,
            'company_id': self.env.company.id,
        })
        return {'id': record.id, 'name': record.name, 'parent_id': record.parent_id.id if record.parent_id else False}

    def create_tag(self, vals=None):
        vals = dict(vals or {})
        if not vals.get('name'):
            raise UserError('Tag name is required.')
        record = self.env['document.management.tag'].create({
            'name': vals['name'],
            'company_id': self.env.company.id,
        })
        return {'id': record.id, 'name': record.name}
