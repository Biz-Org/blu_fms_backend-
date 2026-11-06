# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

from .access_service import DocumentAccessService
from .audit_service import DocumentAuditService
from .notification_service import DocumentNotificationService


class DocumentApprovalService:
    def __init__(self, env):
        self.env = env

    def _access(self):
        return DocumentAccessService(self.env)

    def _audit(self):
        return DocumentAuditService(self.env)

    def _notifications(self):
        return DocumentNotificationService(self.env)

    def _is_manager(self):
        return self.env.su or self.env.user.has_group('document_management.group_dm_manager')

    def _reviewer_name(self, request):
        if not request:
            return False
        active = request.step_ids.filtered(lambda step: step.state == 'active')[:1]
        return active.approver_id.name if active else False

    def _request_dto(self, request):
        active = request.step_ids.filtered(lambda step: step.state == 'active')[:1]
        document = request.document_id
        version = request.version_id or document.current_version_id
        return {
            'id': request.id,
            'document_id': document.id,
            'document': document.name,
            'type': document.type_id.name if document.type_id else False,
            'department': document.department_label,
            'version_id': version.id if version else False,
            'version': version.name if version else False,
            'file_name': version.file_name if version else False,
            'file_size': version.file_size if version else 0,
            'format': version.file_name.rsplit('.', 1)[-1].upper() if version and version.file_name and '.' in version.file_name else False,
            'requester': request.requester_id.name,
            'requester_id': request.requester_id.id,
            'state': request.state,
            'status': request.state,
            'submitted_at': request.submitted_at,
            'decided_at': request.decided_at,
            'current_reviewer': active.approver_id.name if active else False,
            'current_reviewer_id': active.approver_id.id if active else False,
            'actions': {
                'approve': request.state == 'pending',
                'reject': request.state == 'pending',
                'request_changes': request.state == 'pending',
                'renew': False,
                'replace': False,
            },
            'steps': [{
                'id': step.id,
                'sequence': step.sequence,
                'name': step.name,
                'approver_id': step.approver_id.id,
                'approver': step.approver_id.name,
                'state': step.state,
                'comment': step.comment,
                'decided_at': step.decided_at,
                'decided_by': step.decided_by.name if step.decided_by else False,
            } for step in request.step_ids],
        }

    def _document_row(self, document, tab):
        request = document.approval_ids.filtered(lambda r: r.state == 'pending')[:1]
        version = document.current_version_id
        return {
            'id': request.id if request else document.id,
            'request_id': request.id if request else False,
            'document_id': document.id,
            'document': document.name,
            'type': document.type_id.name if document.type_id else False,
            'department': document.department_label,
            'requester': request.requester_id.name if request else document.owner_id.name,
            'submitted_at': request.submitted_at if request else document.write_date,
            'status': document.state,
            'expiry_status': document.expiry_status,
            'expiry_date': document.expiry_date,
            'file_size': version.file_size if version else 0,
            'format': version.file_name.rsplit('.', 1)[-1].upper() if version and version.file_name and '.' in version.file_name else False,
            'current_reviewer': self._reviewer_name(request),
            'actions': {
                'approve': bool(request),
                'reject': bool(request),
                'request_changes': bool(request),
                'renew': tab in ('expiring_soon', 'expired'),
                'replace': tab in ('expiring_soon', 'expired'),
            },
        }

    def _drawer_dto(self, document, request=None):
        request = request or document.approval_ids[:1]
        version = (request.version_id if request else False) or document.current_version_id
        return {
            'document_id': document.id,
            'document': document.name,
            'code': document.code,
            'state': document.state,
            'requester': request.requester_id.name if request else document.owner_id.name,
            'department': document.department_label,
            'submitted_at': request.submitted_at if request else False,
            'file_name': version.file_name if version else False,
            'file_size': version.file_size if version else 0,
            'format': version.file_name.rsplit('.', 1)[-1].upper() if version and version.file_name and '.' in version.file_name else False,
            'type': document.type_id.name if document.type_id else False,
            'category': document.category_id.name if document.category_id else False,
            'access_level': document.access_level,
            'expiry_date': document.expiry_date,
            'expiry_status': document.expiry_status,
            'description': document.description,
            'current_reviewer': self._reviewer_name(request),
            'reviewer_notes': request.step_ids.mapped('comment') if request else [],
            'request': self._request_dto(request) if request else False,
            'steps': self._request_dto(request)['steps'] if request else [],
        }

    def get_approval_board(self, tab=None, filters=None):
        filters = filters or {}
        documents = self._access().visible_documents(active_test=True)
        tab = tab or filters.get('tab') or 'pending'
        if tab in ('pending_approval', 'pending'):
            tab = 'pending'
        rows = []
        if tab == 'pending':
            pool = documents.filtered(lambda d: d.state == 'pending_approval')
            rows = [self._document_row(document, tab) for document in pool]
        elif tab == 'approved':
            pool = documents.filtered(lambda d: d.state == 'approved')
            rows = [self._document_row(document, tab) for document in pool]
        elif tab == 'expiring_soon':
            pool = documents.filtered(lambda d: d.expiry_status == 'expiring_soon')
            rows = [self._document_row(document, tab) for document in pool]
        elif tab == 'expired':
            pool = documents.filtered(lambda d: d.expiry_status == 'expired')
            rows = [self._document_row(document, tab) for document in pool]
        selected = False
        selected_id = filters.get('request_id') or filters.get('document_id') or filters.get('selected_id')
        if selected_id:
            request = self.env['document.management.approval.request'].browse(selected_id)
            if request.exists() and self._access().can(request.document_id, 'read'):
                selected = self._drawer_dto(request.document_id, request)
            else:
                document = self.env['document.management.document'].browse(selected_id)
                if document.exists() and self._access().can(document, 'read'):
                    selected = self._drawer_dto(document)
        return {
            'kpis': {
                'pending_approval': len(documents.filtered(lambda d: d.state == 'pending_approval')),
                'approved': len(documents.filtered(lambda d: d.state == 'approved')),
                'expiring_soon': len(documents.filtered(lambda d: d.expiry_status == 'expiring_soon')),
                'expired': len(documents.filtered(lambda d: d.expiry_status == 'expired')),
            },
            'rows': rows,
            'selected': selected,
            'tab': tab,
        }

    def submit_for_approval(self, document_id, steps=None):
        document = self._access().browse_document(document_id, 'write')
        if not document.requires_approval:
            raise UserError('This document is configured to skip approval.')
        if not document.current_version_id:
            raise UserError('Upload a file before submitting for approval.')
        if not steps:
            raise UserError('At least one approval step is required.')
        pending = document.approval_ids.filtered(lambda request: request.state == 'pending')
        if pending:
            raise UserError('An approval request is already pending.')
        if document.state == 'pending_approval':
            pass
        elif document.state in ('draft', 'returned', 'rejected'):
            document._dm_set_state('pending_approval')
        else:
            raise UserError('Document cannot be submitted from its current state.')
        request = self.env['document.management.approval.request'].create({
            'document_id': document.id,
            'version_id': document.current_version_id.id,
            'requester_id': self.env.user.id,
            'state': 'pending',
            'submitted_at': fields.Datetime.now(),
        })
        for index, step in enumerate(steps):
            if not step.get('approver_id'):
                raise UserError('Each approval step requires an approver.')
            self.env['document.management.approval.step'].create({
                'request_id': request.id,
                'sequence': step.get('sequence') or (index + 1) * 10,
                'name': step.get('name') or 'Step %s' % (index + 1),
                'approver_id': step['approver_id'],
                'state': 'active' if index == 0 else 'waiting',
            })
        self._audit().log('submitted', document=document, version_name=document.current_version_id.name)
        self._notifications().create_notification(
            document.owner_id,
            document,
            'approval_submitted',
            '%s was submitted for approval' % document.name,
        )
        for step in request.step_ids:
            self._notifications().create_notification(
                step.approver_id,
                document,
                'approval_submitted',
                '%s is waiting for your approval' % document.name,
            )
        return self._request_dto(request)

    def _active_step(self, request):
        if request.state != 'pending':
            raise UserError('This approval request is no longer pending.')
        steps = request.step_ids.filtered(lambda s: s.state == 'active').sorted('sequence')
        if not steps:
            raise UserError('There is no active approval step.')
        return steps[0]

    def _require_decider(self, document, step):
        if step.approver_id == self.env.user or self._is_manager():
            return True
        self._audit().deny(document, 'Only the active approver can decide this step.')

    def _close_request(self, request, state, document, event_type, comment):
        now = fields.Datetime.now()
        request.write({
            'state': state,
            'decided_at': now,
        })
        waiting = request.step_ids.filtered(lambda s: s.state == 'waiting')
        if waiting:
            waiting.write({'state': 'skipped'})
        document._dm_set_state(state)
        self._audit().log(event_type, document=document, version_name=request.version_id.name)
        self._notifications().create_notification(
            document.owner_id,
            document,
            'approval_decision',
            '%s was %s' % (document.name, state),
        )
        return self._request_dto(request)

    def approve(self, request_id, comment=None):
        request = self.env['document.management.approval.request'].browse(request_id)
        if not request.exists():
            raise UserError('Approval request not found.')
        document = request.document_id
        self._access().require(document, 'read')
        step = self._active_step(request)
        self._require_decider(document, step)
        step.write({
            'state': 'approved',
            'comment': comment or False,
            'decided_at': fields.Datetime.now(),
            'decided_by': self.env.user.id,
        })
        nxt = request.step_ids.filtered(lambda s: s.state == 'waiting').sorted('sequence')
        if nxt:
            nxt[0].write({'state': 'active'})
            self._audit().log(
                'approved',
                document=document,
                version_name=request.version_id.name,
                metadata={'step': step.sequence, 'final': False},
            )
            self._notifications().create_notification(
                document.owner_id,
                document,
                'approval_decision',
                '%s was approved at step %s' % (document.name, step.name or step.sequence),
            )
            self._notifications().create_notification(
                nxt[0].approver_id,
                document,
                'approval_submitted',
                '%s is waiting for your approval' % document.name,
            )
            return self._request_dto(request)
        request.write({
            'state': 'approved',
            'decided_at': fields.Datetime.now(),
        })
        document._dm_set_state('approved')
        self._audit().log(
            'approved',
            document=document,
            version_name=request.version_id.name,
            metadata={'step': step.sequence, 'final': True},
        )
        self._notifications().create_notification(
            document.owner_id,
            document,
            'approval_decision',
            '%s was approved' % document.name,
        )
        return self._request_dto(request)

    def reject(self, request_id, comment=None):
        if not (comment or '').strip():
            raise UserError('A comment is required to reject a document.')
        request = self.env['document.management.approval.request'].browse(request_id)
        if not request.exists():
            raise UserError('Approval request not found.')
        document = request.document_id
        self._access().require(document, 'read')
        step = self._active_step(request)
        self._require_decider(document, step)
        step.write({
            'state': 'rejected',
            'comment': comment.strip(),
            'decided_at': fields.Datetime.now(),
            'decided_by': self.env.user.id,
        })
        return self._close_request(request, 'rejected', document, 'rejected', comment)

    def request_changes(self, request_id, comment=None):
        if not (comment or '').strip():
            raise UserError('A comment is required to request changes.')
        request = self.env['document.management.approval.request'].browse(request_id)
        if not request.exists():
            raise UserError('Approval request not found.')
        document = request.document_id
        self._access().require(document, 'read')
        step = self._active_step(request)
        self._require_decider(document, step)
        step.write({
            'state': 'returned',
            'comment': comment.strip(),
            'decided_at': fields.Datetime.now(),
            'decided_by': self.env.user.id,
        })
        return self._close_request(request, 'returned', document, 'returned', comment)
