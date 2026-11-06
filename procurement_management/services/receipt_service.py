# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .common import audit_record, has_group


class ReceiptService:
    def __init__(self, env):
        self.env = env

    def _officer(self, receipt):
        if not has_group(self.env, 'group_procurement_officer'):
            raise UserError('Only a procurement officer can process a goods receipt.')
        receipt.ensure_one()

    def start(self, receipts):
        for receipt in receipts:
            self._officer(receipt)
            if receipt.state not in ('expected', 'pending_receipt'):
                raise UserError('This receipt is not waiting to be received.')
            before = receipt.state
            receipt._set_state('receiving')
            audit_record(receipt, 'modified', before=before, after='receiving')
        return True

    def save_draft(self, receipts, quantities):
        for receipt in receipts:
            self._officer(receipt)
            if receipt.state == 'expected':
                receipt._set_state('receiving')
            self._apply_quantities(receipt, quantities, draft=True)
            audit_record(receipt, 'modified', after=receipt.state, detail='Draft quantities saved.')
        return True

    def confirm(self, receipts, quantities):
        for receipt in receipts:
            self._officer(receipt)
            if receipt.state not in ('expected', 'pending_receipt', 'receiving'):
                raise UserError('This receipt cannot be confirmed.')
            self._apply_quantities(receipt, quantities, draft=False)
            before = receipt.state
            receipt._set_state('pending_inspection')
            audit_record(receipt, 'modified', before=before, after='pending_inspection', detail='Receipt confirmed.')
        return True

    def inspect(self, receipts, result, notes=''):
        if result not in ('pass', 'hold_qa', 'reject'):
            raise UserError('Inspection result must be pass, hold for QA, or reject.')
        for receipt in receipts:
            self._officer(receipt)
            if receipt.state not in ('pending_inspection', 'inspection'):
                raise UserError('This receipt is not ready for inspection.')
            before = receipt.state
            if result == 'hold_qa':
                receipt.with_context(pm_state_write=True).write({
                    'state': 'inspection',
                    'inspection_result': 'hold_qa',
                })
                if notes:
                    receipt.line_ids.write({'inspection_notes': notes})
                audit_record(receipt, 'modified', before=before, after='inspection', detail='Held for QA.')
                continue
            receipt.with_context(pm_state_write=True).write({
                'state': 'completed',
                'inspection_result': result,
            })
            if notes:
                receipt.line_ids.write({'inspection_notes': notes})
            if result == 'pass':
                self._spawn_remainder(receipt)
            audit_record(receipt, 'modified', before=before, after='completed', detail='Inspection %s.' % result)
        return True

    def _apply_quantities(self, receipt, quantities, draft):
        if not quantities and not draft:
            raise UserError('Enter the received quantities.')
        received_any = False
        for line in receipt.line_ids:
            if line.id not in quantities and str(line.id) not in quantities:
                if draft:
                    continue
                raise UserError('A received quantity is required for every line.')
            qty = quantities.get(line.id, quantities.get(str(line.id)))
            if qty > line.ordered_qty + 0.0001:
                raise UserError('Received quantity cannot exceed the ordered quantity.')
            if qty < 0:
                raise UserError('Received quantity cannot be negative.')
            line.received_qty = qty
            received_any = received_any or qty > 0
        if not draft and not received_any:
            raise UserError('Received quantity must be greater than zero.')

    def _spawn_remainder(self, receipt):
        remainder = []
        for line in receipt.line_ids:
            left = line.ordered_qty - line.received_qty
            if left > 0.0001:
                remainder.append((0, 0, {
                    'order_line_id': line.order_line_id.id,
                    'description': line.description,
                    'ordered_qty': left,
                    'received_qty': 0.0,
                }))
        if not remainder:
            return self.env['procurement.management.receipt']
        return self.env['procurement.management.receipt'].create({
            'order_id': receipt.order_id.id,
            'partner_id': receipt.partner_id.id,
            'company_id': receipt.company_id.id,
            'state': 'expected',
            'line_ids': remainder,
        })
