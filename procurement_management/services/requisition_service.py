# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError

from .approval_service import ApprovalService
from .common import audit_denied, audit_record, has_group


class RequisitionService:
    def __init__(self, env):
        self.env = env

    def submit(self, requisitions):
        approvals = ApprovalService(self.env)
        for requisition in requisitions:
            if requisition.state not in ('draft', 'returned'):
                raise UserError('Only a draft or returned requisition can be submitted.')
            if requisition.requester_id != self.env.user and not has_group(self.env, 'group_procurement_officer'):
                audit_denied(
                    self.env, requisition.company_id, 'modified',
                    'Only the requester can submit this requisition.',
                    model=requisition._name, reference=requisition.name,
                )
                raise AccessError('Only the requester can submit this requisition.')
            if not requisition.line_ids:
                raise UserError('Add at least one requisition line before submitting.')
            before = requisition.state
            request = approvals.start(
                requisition, 'requisition', requisition.amount_total,
                requisition.department, requisition.property_project, requisition.category,
            )
            if request.state == 'pending':
                requisition._set_state('pending')
            audit_record(requisition, 'modified', before=before, after=requisition.state, detail='Submitted.')
        return True

    def approve(self, requisitions, comment=''):
        approvals = ApprovalService(self.env)
        for requisition in requisitions:
            request = approvals.open_request(requisition, 'requisition')
            if not request:
                raise UserError('There is no pending approval for this requisition.')
            approvals.decide(request, 'approved', comment)
        return True

    def reject(self, requisitions, comment=''):
        approvals = ApprovalService(self.env)
        for requisition in requisitions:
            request = approvals.open_request(requisition, 'requisition')
            if not request:
                raise UserError('There is no pending approval for this requisition.')
            approvals.decide(request, 'rejected', comment)
        return True

    def return_request(self, requisitions, comment=''):
        approvals = ApprovalService(self.env)
        for requisition in requisitions:
            request = approvals.open_request(requisition, 'requisition')
            if not request:
                raise UserError('There is no pending approval for this requisition.')
            approvals.decide(request, 'returned', comment)
        return True

    def cancel(self, requisitions):
        for requisition in requisitions:
            if requisition.state not in ('draft', 'pending', 'returned'):
                raise UserError('This requisition cannot be cancelled.')
            if requisition.requester_id != self.env.user and not has_group(self.env, 'group_procurement_officer'):
                raise AccessError('You cannot cancel this requisition.')
            before = requisition.state
            requisition._set_state('cancelled')
            pending = ApprovalService(self.env).open_request(requisition, 'requisition')
            if pending:
                pending._set_state('cancelled')
            audit_record(requisition, 'modified', before=before, after='cancelled', detail='Cancelled.')
        return True

    def convert_rfq(self, requisitions):
        created = self.env['procurement.management.rfq']
        for requisition in requisitions:
            self._guard_convert(requisition)
            rfq = self.env['procurement.management.rfq'].create({
                'requisition_id': requisition.id,
                'company_id': requisition.company_id.id,
                'department': requisition.department,
                'property_project': requisition.property_project,
                'category': requisition.category,
                'description': self._line_text(requisition),
                'estimated_value': requisition.amount_total,
                'deadline': requisition.required_date,
            })
            self._mark_converted(requisition, rfq)
            created |= rfq
        return created

    def convert_po(self, requisitions, partner):
        if not partner:
            raise UserError('A supplier is required to convert a requisition into a purchase order.')
        created = self.env['procurement.management.purchase.order']
        for requisition in requisitions:
            self._guard_convert(requisition)
            order = self.env['procurement.management.purchase.order'].create({
                'partner_id': partner.id,
                'company_id': requisition.company_id.id,
                'requisition_id': requisition.id,
                'department': requisition.department,
                'property_project': requisition.property_project,
                'category': requisition.category,
                'delivery_date': requisition.required_date,
                'line_ids': [(0, 0, {
                    'description': line.description,
                    'quantity': line.quantity,
                    'unit_text': line.unit_text,
                    'price_unit': line.price_unit,
                    'cost_center': line.cost_center or requisition.cost_center,
                }) for line in requisition.line_ids],
            })
            self._mark_converted(requisition, order)
            created |= order
        return created

    def _guard_convert(self, requisition):
        if not has_group(self.env, 'group_procurement_officer'):
            audit_denied(
                self.env, requisition.company_id, 'modified',
                'Only an officer can convert a requisition.',
                model=requisition._name, reference=requisition.name,
            )
            raise AccessError('Only a procurement officer can convert a requisition.')
        if requisition.state != 'approved':
            raise UserError('Only an approved requisition can be converted.')
        if requisition.converted_res_id:
            raise UserError('This requisition was already converted.')

    def _mark_converted(self, requisition, document):
        requisition.with_context(pm_state_write=True).write({
            'state': 'converted',
            'converted_model': document._name,
            'converted_res_id': document.id,
        })
        audit_record(
            requisition, 'modified', before='approved', after='converted',
            detail='Converted to %s.' % document.display_name,
        )

    def _line_text(self, requisition):
        lines = []
        for line in requisition.line_ids:
            lines.append('%s x %s %s' % (line.quantity, line.unit_text or '', line.description))
        return '\n'.join(lines)
