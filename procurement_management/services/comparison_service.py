# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError

from .approval_service import ApprovalService
from .common import audit_denied, has_group


class ComparisonService:
    def __init__(self, env):
        self.env = env

    def recommend(self, rfq):
        quotations = rfq.quotation_ids.filtered(lambda item: item.state != 'rejected')
        if not quotations:
            return self.env['procurement.management.quotation']
        return quotations.sorted(key=lambda item: (item.amount_total, item.id))[:1]

    def update_weights(self, rfq, commercial_weight, technical_weight):
        if not has_group(self.env, 'group_procurement_officer'):
            raise AccessError('Only an officer can change comparison weights.')
        if rfq.state in ('closed', 'cancelled'):
            raise UserError('Weights cannot be changed on a closed RFQ.')
        rfq.write({
            'commercial_weight': commercial_weight,
            'technical_weight': technical_weight,
        })
        return True

    def select_supplier(self, quotation):
        quotation.ensure_one()
        rfq = quotation.rfq_id
        if not has_group(self.env, 'group_procurement_officer'):
            audit_denied(
                self.env, rfq.company_id, 'approved',
                'Only an officer can select a supplier.',
                model=quotation._name, reference=quotation.name,
            )
            raise AccessError('Only a procurement officer can select a supplier.')
        if rfq.state != 'under_evaluation':
            raise UserError('Supplier selection is only available while the RFQ is under evaluation.')
        if rfq.selection_status == 'pending':
            raise UserError('A supplier selection is already waiting for approval.')
        if quotation.state == 'rejected':
            raise UserError('A rejected quotation cannot be selected.')
        if quotation.rfq_id != rfq:
            raise UserError('The quotation does not belong to this RFQ.')
        request = ApprovalService(self.env).start(
            quotation, 'supplier_selection', quotation.amount_total,
            rfq.department, rfq.property_project, rfq.category,
        )
        if request.state == 'pending':
            rfq.with_context(pm_state_write=True).write({'selection_status': 'pending'})
        return request

    def reject_quotation(self, quotation, comment=''):
        quotation.ensure_one()
        rfq = quotation.rfq_id
        if not has_group(self.env, 'group_procurement_officer'):
            audit_denied(
                self.env, rfq.company_id, 'rejected',
                'Only an officer can reject a quotation.',
                model=quotation._name, reference=quotation.name,
            )
            raise AccessError('Only a procurement officer can reject a quotation.')
        if rfq.state != 'under_evaluation':
            raise UserError('Quotations can be rejected only while the RFQ is under evaluation.')
        if rfq.selection_status == 'pending':
            raise UserError('A supplier selection is already waiting for approval.')
        if quotation.state in ('selected', 'rejected'):
            raise UserError('This quotation can no longer be rejected.')
        quotation._set_state('rejected')
        from .common import audit_record
        audit_record(quotation, 'rejected', before='under_evaluation', after='rejected', detail=comment or '')
        return True

    def save_evaluation(self, rfq, commercial_weight, technical_weight, rows):
        self.update_weights(rfq, commercial_weight, technical_weight)
        for row in rows or []:
            quotation = rfq.quotation_ids.filtered(lambda item: item.id == row.get('id'))[:1]
            if not quotation:
                continue
            quotation.write({
                'commercial_score': row.get('commercial_score') or 0.0,
                'technical_score': row.get('technical_score') or 0.0,
                'evaluation_notes': row.get('evaluation_notes') or '',
            })
        return True

    def dto(self, rfq):
        rfq.ensure_one()
        recommended = self.recommend(rfq)
        rows = []
        for quotation in rfq.quotation_ids:
            rows.append({
                'id': quotation.id,
                'name': quotation.name,
                'supplier': quotation.partner_id.name,
                'amount_untaxed': quotation.amount_untaxed,
                'amount_tax': quotation.amount_tax,
                'freight_amount': quotation.freight_amount,
                'amount_total': quotation.amount_total,
                'commercial_score': quotation.commercial_score,
                'technical_score': quotation.technical_score,
                'weighted_score': quotation.weighted_score,
                'evaluation_notes': quotation.evaluation_notes or '',
                'state': quotation.state,
                'lines': [{
                    'description': line.description,
                    'quantity': line.quantity,
                    'unit_text': line.unit_text or '',
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                } for line in quotation.line_ids],
            })
        return {
            'rfq_id': rfq.id,
            'rfq_name': rfq.name,
            'state': rfq.state,
            'selection_status': rfq.selection_status,
            'commercial_weight': rfq.commercial_weight,
            'technical_weight': rfq.technical_weight,
            'recommended_quotation_id': recommended.id or False,
            'rows': rows,
        }
