# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

from ..models.dm_mixin import ROLE_PERMISSIONS
from .audit_service import DocumentAuditService
from .notification_service import DocumentNotificationService


class DocumentAccessService:
    def __init__(self, env):
        self.env = env

    def _audit(self):
        return DocumentAuditService(self.env)

    def _notifications(self):
        return DocumentNotificationService(self.env)

    def _is_admin(self):
        return self.env.su or self.env.user.has_group('document_management.group_dm_admin')

    def _is_manager(self):
        return self._is_admin() or self.env.user.has_group('document_management.group_dm_manager')

    def _same_company(self, document):
        if not document or not document.company_id:
            return False
        return document.company_id in self.env.user.company_ids or self.env.su

    def _folder_chain(self, folder):
        folders = folder
        parent = folder.parent_id
        while parent:
            folders |= parent
            parent = parent.parent_id
        return folders

    def _is_assigned_approver(self, document):
        pending = document.approval_ids.filtered(lambda request: request.state == 'pending')
        return self.env.user in pending.mapped('step_ids.approver_id')

    def _matching_rules(self, document):
        user = self.env.user
        rules = document.access_rule_ids.filtered(lambda r: r.state == 'active')
        if document.folder_id:
            for folder in self._folder_chain(document.folder_id):
                rules |= folder.access_rule_ids.filtered(lambda r: r.state == 'active')
        matched = self.env['document.management.access.rule']
        for rule in rules:
            if rule.partner_type == 'user' and rule.user_id == user:
                matched |= rule
            elif rule.partner_type == 'group' and user in rule.group_id.member_ids:
                matched |= rule
        return matched

    def visible_documents(self, extra_domain=None, limit=None, offset=0, order='id desc', records=None, active_test=True):
        Document = records if records is not None else self.env['document.management.document']
        if records is None and not active_test:
            Document = Document.with_context(active_test=False)
        # sudo so inherited folder ACL deeper than the record-rule parent hop is still found
        Document = Document.sudo()
        documents = Document.search(extra_domain or [], offset=offset, limit=limit, order=order)
        return documents.filtered(lambda document: self.can(document, 'read'))

    def can(self, document, perm):
        if not document or not document.exists():
            return False
        if not self._same_company(document):
            return False
        if perm == 'delete':
            return self._is_admin()
        if perm == 'restore':
            return self._is_manager()
        if self._is_manager() or document.owner_id == self.env.user:
            return perm != 'delete' or self._is_admin()
        if perm == 'read' and self._is_assigned_approver(document):
            return True
        if perm == 'read' and document.access_level == 'internal':
            return self.env.user.has_group('document_management.group_dm_user')
        field_by_perm = {
            'read': 'perm_read',
            'write': 'perm_write',
            'download': 'perm_download',
            'share': 'perm_share',
            'archive': 'perm_write',
        }
        fname = field_by_perm.get(perm)
        if not fname:
            return False
        return any(rule[fname] for rule in self._matching_rules(document))

    def require(self, document, perm, message=None):
        if self.can(document, perm):
            return document
        self._audit().deny(
            document,
            message or 'You are not allowed to perform this document action.',
            metadata={'permission': perm},
        )

    def browse_document(self, document_id, perm='read'):
        if not document_id:
            return self.env['document.management.document']
        document = self.env['document.management.document'].sudo().with_context(
            active_test=False
        ).browse(int(document_id))
        if not document.exists():
            raise UserError('Document not found.')
        self.require(document, perm)
        return document

    def role_permissions(self, role):
        perms = ROLE_PERMISSIONS.get(role)
        if not perms:
            raise UserError('Invalid access role.')
        return dict(perms)

    def get_access_matrix(self, document_id):
        if not document_id:
            return {
                'kpis': {
                    'access_level': False,
                    'active_users': 0,
                    'groups': 0,
                    'external_links': 0,
                    'users_this_week': 0,
                },
                'rows': [],
            }
        document = self.browse_document(document_id, 'read')
        rows = []
        for rule in document.access_rule_ids:
            rows.append(self._rule_row(rule, 'direct'))
        if document.folder_id:
            for folder in self._folder_chain(document.folder_id):
                for rule in folder.access_rule_ids:
                    rows.append(self._rule_row(rule, 'inherited'))
        for link in document.share_link_ids:
            rows.append({
                'id': link.id,
                'name': link.name,
                'type': 'link',
                'role': 'viewer',
                'perm_read': link.perm_read,
                'perm_write': False,
                'perm_download': link.perm_download,
                'perm_share': False,
                'origin': 'direct',
                'status': link.state,
                'expiry': link.expiry,
                'url': '/document_management/share/%s' % link.token,
            })
        active_user_rules = document.access_rule_ids.filtered(
            lambda r: r.state == 'active' and r.partner_type == 'user'
        )
        active_group_rules = document.access_rule_ids.filtered(
            lambda r: r.state == 'active' and r.partner_type == 'group'
        )
        active_links = document.share_link_ids.filtered(lambda r: r.state == 'active')
        week_ago = fields.Datetime.now() - timedelta(days=7)
        users_this_week = len(active_user_rules.filtered(
            lambda r: r.create_date and r.create_date >= week_ago
        ))
        return {
            'kpis': {
                'access_level': document.access_level,
                'active_users': len(active_user_rules),
                'groups': len(active_group_rules),
                'external_links': len(active_links),
                'users_this_week': users_this_week,
            },
            'rows': rows,
        }

    def _rule_row(self, rule, origin):
        return {
            'id': rule.id,
            'name': rule.user_id.name if rule.partner_type == 'user' else rule.group_id.name,
            'type': rule.partner_type,
            'role': rule.role,
            'perm_read': rule.perm_read,
            'perm_write': rule.perm_write,
            'perm_download': rule.perm_download,
            'perm_share': rule.perm_share,
            'origin': origin,
            'status': rule.state,
        }

    def add_access(self, document_id, vals=None):
        vals = dict(vals or {})
        document = self.browse_document(document_id, 'share')
        role = vals.get('role') or 'viewer'
        if role == 'owner' and not (self._is_manager() or document.owner_id == self.env.user):
            raise UserError('Only the owner or a manager can assign the owner role.')
        perms = self.role_permissions(role)
        perm_map = {
            'perm_read': 'read',
            'perm_write': 'write',
            'perm_download': 'download',
            'perm_share': 'share',
        }
        if not self._is_manager():
            for fname, perm in perm_map.items():
                if perms.get(fname) and not self.can(document, perm):
                    raise UserError('You cannot grant a permission you do not have.')
        partner_type = vals.get('partner_type') or 'user'
        create_vals = {
            'document_id': document.id,
            'partner_type': partner_type,
            'role': role,
            'state': 'active',
            **perms,
        }
        if partner_type == 'user':
            if not vals.get('user_id'):
                raise UserError('A user is required.')
            create_vals['user_id'] = vals['user_id']
        elif partner_type == 'group':
            if not vals.get('group_id'):
                raise UserError('An access group is required.')
            create_vals['group_id'] = vals['group_id']
        else:
            raise UserError('Invalid access partner type.')
        rule = self.env['document.management.access.rule'].create(create_vals)
        self._audit().log('access_changed', document=document, metadata={'action': 'add', 'rule_id': rule.id})
        if rule.user_id:
            self._notifications().create_notification(
                rule.user_id,
                document,
                'access_granted',
                'Access granted to %s' % document.name,
            )
        elif rule.group_id:
            for member in rule.group_id.member_ids:
                self._notifications().create_notification(
                    member,
                    document,
                    'access_granted',
                    'Access granted to %s' % document.name,
                )
        return self.get_access_matrix(document.id)

    def revoke_access(self, document_id, rule_id):
        document = self.browse_document(document_id, 'share')
        rule = self.env['document.management.access.rule'].browse(rule_id)
        if not rule.exists() or rule.document_id != document:
            raise UserError('Access rule not found.')
        if rule.role == 'owner':
            raise UserError('Owner access cannot be revoked.')
        rule.write({'state': 'revoked'})
        self._audit().log('access_changed', document=document, metadata={'action': 'revoke', 'rule_id': rule.id})
        return self.get_access_matrix(document.id)

    def create_share_link(self, document_id, vals=None):
        vals = dict(vals or {})
        document = self.browse_document(document_id, 'share')
        if document.state == 'archived':
            raise UserError('Archived documents cannot be shared.')
        if not vals.get('expiry'):
            raise UserError('Share-link expiry is required.')
        expiry = vals['expiry']
        if isinstance(expiry, str) and 'T' in expiry:
            expiry = expiry.replace('T', ' ')
            if expiry.count(':') == 1:
                expiry += ':00'
        link = self.env['document.management.share.link'].create({
            'document_id': document.id,
            'name': vals.get('name') or 'Share link',
            'perm_read': True,
            'perm_download': bool(vals.get('perm_download', True)),
            'expiry': expiry,
        })
        self._audit().log('access_changed', document=document, metadata={'action': 'share_link', 'link_id': link.id})
        return {
            'id': link.id,
            'url': '/document_management/share/%s' % link.token,
            'expiry': link.expiry,
            'state': link.state,
        }

    def revoke_share_link(self, document_id, link_id):
        document = self.browse_document(document_id, 'share')
        link = self.env['document.management.share.link'].browse(link_id)
        if not link.exists() or link.document_id != document:
            raise UserError('Share link not found.')
        link.write({
            'revoked_by': self.env.user.id,
            'revoked_at': fields.Datetime.now(),
        })
        self._audit().log('access_changed', document=document, metadata={'action': 'revoke_link', 'link_id': link.id})
        return True

    def create_access_group(self, vals=None):
        vals = dict(vals or {})
        if not vals.get('name'):
            raise UserError('Access group name is required.')
        group = self.env['document.management.access.group'].create({
            'name': vals['name'],
            'member_ids': vals.get('member_ids') or False,
            'company_id': self.env.company.id,
        })
        return {'id': group.id, 'name': group.name}

    def ensure_owner_rule(self, document):
        existing = document.access_rule_ids.filtered(
            lambda r: r.partner_type == 'user' and r.user_id == document.owner_id and r.role == 'owner'
        )
        if existing:
            return existing[0]
        return self.env['document.management.access.rule'].create({
            'document_id': document.id,
            'partner_type': 'user',
            'user_id': document.owner_id.id,
            'role': 'owner',
            **self.role_permissions('owner'),
        })
