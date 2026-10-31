# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .dm_mixin import (
    ACCESS_LEVELS,
    ALLOWED_TRANSITIONS,
    CLASSIFICATIONS,
    DOCUMENT_PROTECTED_FIELDS,
    DOCUMENT_STATES,
    EXPIRY_STATUSES,
    METADATA_FIELDS,
    DM_EXPIRY_SOON_DAYS,
)


class DocumentManagementDocument(models.Model):
    _name = 'document.management.document'
    _description = 'Document'
    _inherit = ['document.management.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, copy=False, index=True)
    description = fields.Text()
    state = fields.Selection(
        DOCUMENT_STATES,
        required=True,
        default='draft',
        index=True,
    )
    access_level = fields.Selection(
        ACCESS_LEVELS,
        required=True,
        default='role_restricted',
        index=True,
    )
    classification = fields.Selection(
        CLASSIFICATIONS,
        required=True,
        default='internal',
    )
    owner_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    type_id = fields.Many2one(
        'document.management.document.type',
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    category_id = fields.Many2one(
        'document.management.category',
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    folder_id = fields.Many2one(
        'document.management.folder',
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    tag_ids = fields.Many2many(
        'document.management.tag',
        'document_management_document_tag_rel',
        'document_id',
        'tag_id',
        check_company=True,
    )
    department_label = fields.Char()
    property_ref = fields.Char()
    asset_ref = fields.Char()
    effective_date = fields.Date()
    expiry_date = fields.Date()
    expiry_notify = fields.Boolean(default=True)
    requires_approval = fields.Boolean(default=True)
    current_version_id = fields.Many2one(
        'document.management.version',
        ondelete='set null',
        copy=False,
    )
    prior_state = fields.Char()
    active = fields.Boolean(compute='_compute_active', store=True)
    expiry_status = fields.Selection(
        EXPIRY_STATUSES,
        compute='_compute_expiry_status',
        store=True,
        index=True,
    )
    version_ids = fields.One2many('document.management.version', 'document_id')
    access_rule_ids = fields.One2many('document.management.access.rule', 'document_id')
    share_link_ids = fields.One2many('document.management.share.link', 'document_id')
    approval_ids = fields.One2many('document.management.approval.request', 'document_id')
    comment_ids = fields.One2many('document.management.comment', 'document_id')
    favorite_ids = fields.One2many('document.management.favorite', 'document_id')
    audit_ids = fields.One2many('document.management.audit.event', 'document_id')
    notification_ids = fields.One2many('document.management.notification', 'document_id')

    _sql_constraints = [
        (
            'code_company_uniq',
            'unique(company_id, code)',
            'Document code must be unique per company.',
        ),
    ]

    @api.depends('state')
    def _compute_active(self):
        for rec in self:
            rec.active = rec.state != 'archived'

    @api.depends('expiry_date')
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=DM_EXPIRY_SOON_DAYS)
        for rec in self:
            if not rec.expiry_date:
                rec.expiry_status = 'none'
            elif rec.expiry_date < today:
                rec.expiry_status = 'expired'
            elif rec.expiry_date <= soon:
                rec.expiry_status = 'expiring_soon'
            else:
                rec.expiry_status = 'active'

    @api.constrains('effective_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.effective_date and rec.expiry_date and rec.expiry_date < rec.effective_date:
                raise ValidationError('Expiry date must be on or after the effective date.')

    @api.model_create_multi
    def create(self, vals_list):
        Type = self.env['document.management.document.type']
        for vals in vals_list:
            self._dm_guard_lifecycle_fields(
                vals,
                DOCUMENT_PROTECTED_FIELDS,
                'Document lifecycle fields cannot be set directly.',
                creating=True,
            )
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('document.management.document')
                    or 'DM00000'
                )
            if vals.get('type_id') and 'requires_approval' not in vals:
                vals['requires_approval'] = Type.browse(vals['type_id']).requires_approval
        records = super().create(vals_list)
        if not self.env.context.get('dm_skip_audit'):
            from ..services.audit_service import DocumentAuditService
            audit = DocumentAuditService(self.env)
            for rec in records:
                audit.log('created', document=rec)
        return records

    def write(self, vals):
        self._dm_guard_lifecycle_fields(
            vals,
            DOCUMENT_PROTECTED_FIELDS,
            'Document lifecycle fields cannot be changed directly.',
        )
        result = super().write(vals)
        if METADATA_FIELDS.intersection(vals) and not self.env.context.get('dm_skip_audit'):
            from ..services.audit_service import DocumentAuditService
            audit = DocumentAuditService(self.env)
            for rec in self:
                audit.log('metadata_modified', document=rec)
        return result

    @api.constrains('current_version_id', 'version_ids')
    def _check_one_current_version(self):
        for rec in self:
            currents = rec.version_ids.filtered('is_current')
            if len(currents) > 1:
                raise ValidationError('A document must have exactly one current version.')
            if rec.current_version_id and currents and rec.current_version_id != currents:
                raise ValidationError('The current version pointer must match the current version record.')

    def _dm_set_state(self, new_state):
        self.ensure_one()
        if new_state not in ALLOWED_TRANSITIONS.get(self.state, set()):
            raise UserError('Invalid document state transition from %s to %s.' % (self.state, new_state))
        if self.state == 'draft' and new_state == 'approved' and self.requires_approval:
            raise UserError('This document requires approval before it can be approved.')
        if self.state == 'draft' and new_state == 'pending_approval' and not self.requires_approval:
            raise UserError('This document is configured to skip approval.')
        self.with_context(dm_lifecycle=True).write({'state': new_state})
        return True

    def _dm_archive(self):
        self.ensure_one()
        if self.state == 'archived':
            raise UserError('Document is already archived.')
        if self.state not in ('draft', 'returned', 'rejected', 'approved'):
            raise UserError('Document cannot be archived from its current state.')
        self.with_context(dm_lifecycle=True).write({
            'prior_state': self.state,
            'state': 'archived',
        })
        return True

    def _dm_restore(self):
        self.ensure_one()
        if self.state != 'archived':
            raise UserError('Only archived documents can be restored.')
        target = self.prior_state if self.prior_state in dict(DOCUMENT_STATES) else 'draft'
        if target == 'archived':
            target = 'draft'
        self.with_context(dm_lifecycle=True).write({
            'state': target,
            'prior_state': False,
        })
        return True
