# -*- coding: utf-8 -*-
"""Approval workflow.

OPEN — self-approval is not frozen.
Set ir.config_parameter procurement_management.self_approval to A or B.
Option A: the submitter cannot approve their own selection or PO request.
Option B: the submitter may approve when they belong to the configured group.
Until that parameter is set, only the configured approver group is checked.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError

from .common import (
    DECISION_CTX,
    REQUEST_CTX,
    assert_self_approval,
    audit,
    audit_denied,
    audit_record,
    has_group,
    normalize,
)


class ApprovalService:
    def __init__(self, env):
        self.env = env

    def match(self, company, amount, department, property_location, category):
        matrices = self.env['procurement.management.approval.matrix'].sudo().search([
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
        ])
        ranked = []
        for matrix in matrices:
            if amount < matrix.min_value:
                continue
            if matrix.max_value and amount > matrix.max_value:
                continue
            specificity = 0
            if not self._dimension_ok(matrix.department, department):
                continue
            if not self._dimension_ok(matrix.property_location, property_location):
                continue
            if not self._dimension_ok(matrix.category, category):
                continue
            specificity += int(bool(normalize(matrix.department)))
            specificity += int(bool(normalize(matrix.property_location)))
            specificity += int(bool(normalize(matrix.category)))
            ranked.append((-specificity, matrix.sequence, matrix.id, matrix))
        if not ranked:
            return self.env['procurement.management.approval.matrix']
        ranked.sort()
        return ranked[0][3]

    def _dimension_ok(self, configured, actual):
        if not normalize(configured):
            return True
        return normalize(configured) == normalize(actual)

    def start(self, document, purpose, amount, department, property_location, category):
        matrix = self.match(document.company_id, amount, department, property_location, category)
        if not matrix:
            audit_denied(
                self.env, document.company_id, 'approved',
                'No approval matrix matches this document.',
                model=document._name, reference=document.display_name,
            )
            raise UserError('No approval matrix matches this document.')
        request = self.env['procurement.management.approval.request'].sudo().with_context(**{
            REQUEST_CTX: True,
            'pm_state_write': True,
        }).create({
            'name': '%s approval' % document.display_name,
            'company_id': document.company_id.id,
            'res_model': document._name,
            'res_id': document.id,
            'purpose': purpose,
            'amount': amount,
            'matrix_id': matrix.id,
            'requester_id': self.env.user.id,
        })
        self._open_chain(request)
        if request.state == 'pending':
            from .notification_service import NotificationService
            NotificationService(self.env).approval_requested(request)
        audit_record(document, 'approved' if request.state == 'approved' else 'modified',
                     after=request.state, detail='Approval request %s.' % request.name)
        return request

    def _open_chain(self, request):
        levels = request.matrix_id.level_ids.sorted(key=lambda level: (level.sequence, level.id))
        required = levels.filtered('required_signoff')
        if not required:
            self._finish(request, 'approved')
            return
        if required[0].mode == 'parallel':
            for level in required:
                self._add_decision(request, level, level.approver_group_id, hop=0)
            request.sudo().with_context(**{REQUEST_CTX: True}).write({'current_level_id': required[0].id})
        else:
            self._add_decision(request, required[0], required[0].approver_group_id, hop=0)
            request.sudo().with_context(**{REQUEST_CTX: True}).write({'current_level_id': required[0].id})

    def _add_decision(self, request, level, group, hop):
        return self.env['procurement.management.approval.decision'].sudo().with_context(**{
            DECISION_CTX: True,
        }).create({
            'request_id': request.id,
            'level_id': level.id,
            'group_id': group.id,
            'decision': 'pending',
            'hop': hop,
        })

    def decide(self, request, outcome, comment=''):
        request.ensure_one()
        if request.state != 'pending':
            raise UserError('This approval request is no longer pending.')
        if outcome not in ('approved', 'rejected', 'returned'):
            raise UserError('Unsupported approval decision.')
        pending = request.decision_ids.filtered(lambda row: row.decision == 'pending')
        actionable = pending.filtered(lambda row: self._user_in_group(row.group_id))
        mode = self._mode(request)
        if mode == 'sequential' and request.current_level_id:
            actionable = actionable.filtered(lambda row: row.level_id == request.current_level_id)
        if not actionable:
            audit_denied(
                self.env, request.company_id, 'approved',
                'You are not the active approver.',
                model=request._name, reference=request.name,
            )
            raise AccessError('You are not the active approver for this request.')
        decision = actionable.sorted(key=lambda row: (row.hop, row.id))[:1]
        assert_self_approval(
            self.env, request.requester_id, self.env.user,
            request.company_id, request.name,
        )
        decision.sudo().with_context(**{DECISION_CTX: True}).write({
            'decision': outcome,
            'user_id': self.env.user.id,
            'comment': comment or '',
            'decided_on': fields.Datetime.now(),
        })
        if outcome in ('rejected', 'returned'):
            request._set_state(outcome)
            self._apply(request, outcome)
            from .notification_service import NotificationService
            NotificationService(self.env).approval_decided(request)
            audit(self.env, request.company_id, 'rejected' if outcome == 'rejected' else 'modified',
                  model=request.res_model, reference=request.name, after=outcome, detail=comment or '')
            return request
        if mode == 'sequential':
            nxt = self._next_required(request, decision.level_id)
            if nxt:
                self._add_decision(request, nxt, nxt.approver_group_id, hop=0)
                request.sudo().with_context(**{REQUEST_CTX: True}).write({'current_level_id': nxt.id})
                from .notification_service import NotificationService
                NotificationService(self.env).approval_requested(request)
            else:
                self._finish(request, 'approved')
        else:
            still_pending = request.decision_ids.filtered(
                lambda row: row.decision == 'pending' and row.level_id.required_signoff
            )
            if not still_pending:
                self._finish(request, 'approved')
        return request

    def _finish(self, request, outcome):
        request._set_state(outcome)
        self._apply(request, outcome)
        from .notification_service import NotificationService
        NotificationService(self.env).approval_decided(request)
        audit(self.env, request.company_id, 'approved', model=request.res_model,
              reference=request.name, after=outcome)

    def _apply(self, request, outcome):
        document = self.env[request.res_model].browse(request.res_id).exists()
        if not document:
            return
        if request.purpose == 'requisition':
            mapping = {'approved': 'approved', 'rejected': 'rejected', 'returned': 'returned'}
            if outcome in mapping:
                document._set_state(mapping[outcome])
        elif request.purpose == 'purchase_order':
            if outcome == 'approved':
                document._set_state('approved')
            elif outcome in ('rejected', 'returned'):
                document._set_state('draft')
        elif request.purpose == 'supplier_selection':
            quotation = document if document._name == 'procurement.management.quotation' else None
            rfq = quotation.rfq_id if quotation else document
            if outcome == 'approved' and quotation:
                quotation._set_state('selected')
                rfq.with_context(pm_state_write=True).write({
                    'selection_status': 'effective',
                    'selected_quotation_id': quotation.id,
                })
                from .purchase_order_service import PurchaseOrderService
                PurchaseOrderService(self.env).create_from_quotation(quotation)
            elif quotation:
                quotation._set_state('rejected')
                rfq.with_context(pm_state_write=True).write({'selection_status': 'rejected'})

    def _mode(self, request):
        levels = request.matrix_id.level_ids
        return levels[:1].mode or 'sequential'

    def _next_required(self, request, level):
        levels = request.matrix_id.level_ids.filtered('required_signoff').sorted(
            key=lambda row: (row.sequence, row.id)
        )
        found = False
        for candidate in levels:
            if found:
                return candidate
            if candidate == level:
                found = True
        return self.env['procurement.management.approval.level']

    def _user_in_group(self, group):
        return bool(self.env['res.users'].search_count([
            ('id', '=', self.env.user.id),
            ('groups_id', 'in', group.id),
        ]))

    def escalate_due(self):
        now = fields.Datetime.now()
        decisions = self.env['procurement.management.approval.decision'].sudo().search([
            ('decision', '=', 'pending'),
            ('hop', '=', 0),
        ])
        count = 0
        for decision in decisions:
            level = decision.level_id
            if not level.escalation_group_id:
                continue
            due = decision.create_date + timedelta(hours=level.escalation_hours or 0.0)
            if due > now:
                continue
            decision.sudo().with_context(**{DECISION_CTX: True}).write({
                'decision': 'escalated',
                'decided_on': now,
            })
            self._add_decision(decision.request_id, level, level.escalation_group_id, hop=1)
            if decision.request_id.current_level_id == level:
                decision.request_id.sudo().with_context(**{REQUEST_CTX: True}).write({'current_level_id': level.id})
            audit(
                self.env, decision.company_id, 'modified',
                model=decision._name, reference=decision.request_id.name,
                before='pending', after='escalated',
                detail='Escalated to %s.' % level.escalation_group_id.name,
            )
            from .notification_service import NotificationService
            NotificationService(self.env).approval_requested(decision.request_id)
            count += 1
        return count

    def submit_matrix_review(self, matrices):
        if not has_group(self.env, 'group_procurement_manager'):
            audit_denied(self.env, self.env.company, 'modified', 'Only a manager can submit a matrix for review.')
            raise AccessError('Only a procurement manager can submit a matrix for review.')
        for matrix in matrices:
            if matrix.state != 'draft':
                raise UserError('Only a draft matrix can be submitted for review.')
            matrix._set_state('review')
        return True

    def activate_matrix(self, matrices):
        if not has_group(self.env, 'group_procurement_admin'):
            audit_denied(self.env, self.env.company, 'approved', 'Only an administrator can activate a matrix.')
            raise AccessError('Only a procurement administrator can activate a matrix.')
        for matrix in matrices:
            if matrix.state not in ('draft', 'review', 'inactive'):
                raise UserError('This matrix cannot be activated.')
            matrix._set_state('active')
            audit_record(matrix, 'approved', after='active')
        return True

    def deactivate_matrix(self, matrices):
        if not has_group(self.env, 'group_procurement_admin'):
            raise AccessError('Only a procurement administrator can deactivate a matrix.')
        for matrix in matrices:
            matrix._set_state('inactive')
        return True

    def open_request(self, document, purpose):
        return self.env['procurement.management.approval.request'].search([
            ('res_model', '=', document._name),
            ('res_id', '=', document.id),
            ('purpose', '=', purpose),
            ('state', '=', 'pending'),
        ], limit=1)
