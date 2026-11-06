# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .common import audit_denied, audit_record, has_group


class InvoiceMatchService:
    def __init__(self, env):
        self.env = env

    def _officer(self):
        if not has_group(self.env, 'group_procurement_officer'):
            raise UserError('Only a procurement officer can match invoices.')

    def check_duplicate(self, company, partner, number):
        if not number:
            raise UserError('A supplier invoice number is required.')
        existing = self.env['procurement.management.invoice.match'].sudo().search_count([
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('supplier_invoice_number', '=', number),
        ])
        if existing:
            audit_denied(
                self.env, company, 'created',
                'Duplicate supplier invoice %s.' % number,
                model='procurement.management.invoice.match', reference=number,
            )
            raise UserError(
                'This supplier invoice number is already recorded for the supplier in this company.'
            )

    def auto_match(self, matches):
        self._officer()
        for match in matches:
            if match.state not in ('pending', 'mismatch'):
                raise UserError('This invoice match cannot be recalculated.')
            if match._is_clean():
                before = match.state
                match._set_state('matched')
                audit_record(match, 'approved', before=before, after='matched', detail='Auto-match.')
            else:
                before = match.state
                match.with_context(pm_state_write=True).write({
                    'state': 'mismatch',
                    'exception_reason': 'Quantity or amount variance.',
                })
                audit_record(match, 'modified', before=before, after='mismatch', detail='Variance detected.')
        return True

    def approve(self, matches):
        if not has_group(self.env, 'group_procurement_manager'):
            audit_denied(self.env, self.env.company, 'approved', 'Only a manager can approve an invoice match.')
            raise UserError('Only a procurement manager can approve an invoice match.')
        for match in matches:
            if match.state != 'pending':
                raise UserError('Only a pending invoice match can be approved.')
            if not match._is_clean():
                raise UserError('An invoice with a variance cannot be approved.')
            match._set_state('matched')
            audit_record(match, 'approved', before='pending', after='matched')
        return True

    def reject(self, matches, note=''):
        if not has_group(self.env, 'group_procurement_manager'):
            raise UserError('Only a procurement manager can reject an invoice match.')
        for match in matches:
            if match.state != 'mismatch':
                raise UserError('Only a mismatched invoice can be rejected.')
            match.with_context(pm_state_write=True).write({
                'state': 'under_review',
                'resolution': 'rejected',
                'resolution_note': note or '',
            })
            audit_record(match, 'rejected', before='mismatch', after='under_review', detail=note or 'Rejected.')
        return True

    def resolve(self, matches, note):
        self._officer()
        if not note:
            raise UserError('A resolution note is required.')
        for match in matches:
            if match.state not in ('mismatch', 'under_review'):
                raise UserError('This invoice match is not open for resolution.')
            values = {
                'resolution': 'resolved',
                'resolution_note': note,
            }
            if match._is_clean():
                values['state'] = 'pending'
                values['exception_reason'] = False
            else:
                values['state'] = 'mismatch'
            match.with_context(pm_state_write=True).write(values)
            audit_record(match, 'modified', after=match.state, detail=note)
        return True
