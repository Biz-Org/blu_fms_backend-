# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError

from .common import audit_denied, audit_record, has_group


class RfqService:
    def __init__(self, env):
        self.env = env

    def _officer(self, rfq, message):
        if not has_group(self.env, 'group_procurement_officer'):
            audit_denied(self.env, rfq.company_id, 'modified', message, model=rfq._name, reference=rfq.name)
            raise AccessError(message)

    def issue(self, rfqs):
        for rfq in rfqs:
            self._officer(rfq, 'Only an officer can issue an RFQ.')
            if rfq.state != 'draft':
                raise UserError('Only a draft RFQ can be issued.')
            if not rfq.supplier_ids:
                raise UserError('Invite at least one supplier before issuing the RFQ.')
            before = rfq.state
            rfq._set_state('issued')
            audit_record(rfq, 'modified', before=before, after='issued', detail='Issued.')
        return True

    def start_evaluation(self, rfqs):
        for rfq in rfqs:
            self._officer(rfq, 'Only an officer can evaluate an RFQ.')
            if rfq.response_count < 1:
                raise UserError('At least one supplier response is required before evaluation.')
            if rfq.state not in ('supplier_responded', 'partially_responded'):
                raise UserError('This RFQ is not ready for evaluation.')
            before = rfq.state
            rfq._set_state('under_evaluation')
            audit_record(rfq, 'modified', before=before, after='under_evaluation')
        return True

    def close(self, rfqs):
        for rfq in rfqs:
            self._officer(rfq, 'Only an officer can close an RFQ.')
            if rfq.state not in ('under_evaluation', 'supplier_responded', 'partially_responded'):
                raise UserError('This RFQ cannot be closed.')
            before = rfq.state
            rfq._set_state('closed')
            audit_record(rfq, 'modified', before=before, after='closed')
        return True

    def cancel(self, rfqs):
        for rfq in rfqs:
            self._officer(rfq, 'Only an officer can cancel an RFQ.')
            if rfq.state not in ('draft', 'issued', 'partially_responded'):
                raise UserError('This RFQ cannot be cancelled.')
            before = rfq.state
            rfq._set_state('cancelled')
            audit_record(rfq, 'modified', before=before, after='cancelled')
        return True
