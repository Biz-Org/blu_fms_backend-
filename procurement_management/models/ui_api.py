# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError


class ProcurementManagementUiApi(models.AbstractModel):
    """RPC entry for the twelve procurement screens.

    Methods return authorization-aware DTOs. An empty database returns empty
    lists and zero totals. Persistent model names are declared on their own
    model classes.
    """

    _name = 'procurement.management.ui.api'
    _description = 'Procurement Management UI API'

    @api.model
    def health(self):
        """Confirm the UI API is reachable. Returns no procurement records."""
        return {
            'ok': True,
            'module': 'procurement_management',
        }

    def _check(self, xml_id):
        if not self.env.user.has_group('procurement_management.%s' % xml_id):
            raise AccessError('You are not allowed to open this procurement screen.')

    def _user_in_groups(self, groups):
        if not groups:
            return False
        return bool(set(self.env.user.groups_id.ids) & set(groups.ids))

    @api.model
    def get_dashboard(self):
        self._check('group_procurement_user')
        orders = self.env['procurement.management.purchase.order']
        spend_orders = orders.search([
            ('state', 'in', ['issued', 'acknowledged', 'closed']),
        ])
        recent = orders.search([], limit=5, order='id desc')
        return {
            'total_spend': sum(spend_orders.mapped('amount_total')),
            'pending_requisitions': self.env['procurement.management.requisition'].search_count([
                ('state', '=', 'pending'),
            ]),
            'open_rfqs': self.env['procurement.management.rfq'].search_count([
                ('state', 'in', ['issued', 'supplier_responded', 'partially_responded', 'under_evaluation']),
            ]),
            'open_purchase_orders': orders.search_count([
                ('state', 'in', ['issued', 'acknowledged']),
            ]),
            'pending_receipts': self.env['procurement.management.receipt'].search_count([
                ('state', 'in', ['expected', 'pending_receipt', 'receiving']),
            ]),
            'invoice_exceptions': self.env['procurement.management.invoice.match'].search_count([
                ('state', 'in', ['mismatch', 'under_review']),
            ]),
            'currency': self.env.company.currency_id.name or '',
            'spend_series': self._spend_series(spend_orders),
            'recent_orders': [{
                'id': order.id,
                'name': order.name,
                'supplier': order.partner_id.name,
                'date': order.delivery_date,
                'amount': order.amount_total,
                'display_status': order.display_status,
            } for order in recent],
            'priority': self._priority_items(),
        }

    def _priority_items(self):
        items = []
        requests = self.env['procurement.management.approval.request'].search([
            ('state', '=', 'pending'),
        ])
        for request in requests:
            groups = request.sudo().decision_ids.filtered(lambda row: row.decision == 'pending').mapped('group_id')
            if self._user_in_groups(groups):
                screen = {
                    'requisition': 'requisitions',
                    'purchase_order': 'purchase_orders',
                    'supplier_selection': 'comparison',
                }.get(request.purpose, 'dashboard')
                target_id = request.res_id
                if request.purpose == 'supplier_selection':
                    quotation = self.env['procurement.management.quotation'].sudo().browse(request.res_id).exists()
                    target_id = quotation.rfq_id.id if quotation else False
                items.append({
                    'kind': 'approval',
                    'id': request.id,
                    'reference': request.name,
                    'label': 'Pending approval',
                    'screen': screen,
                    'target_id': target_id,
                })
        holds = self.env['procurement.management.receipt'].search([
            '|', ('state', '=', 'inspection'), ('inspection_result', '=', 'hold_qa'),
        ])
        for receipt in holds:
            items.append({
                'kind': 'receipt_hold',
                'id': receipt.id,
                'reference': receipt.name,
                'label': 'Receipt on hold',
                'screen': 'goods_receipts',
                'target_id': receipt.id,
            })
        mismatches = self.env['procurement.management.invoice.match'].search([
            ('state', '=', 'mismatch'),
        ])
        for match in mismatches:
            items.append({
                'kind': 'invoice_mismatch',
                'id': match.id,
                'reference': match.name,
                'label': 'Invoice mismatch',
                'screen': 'invoice_matching',
                'target_id': match.id,
            })
        return items

    def _spend_series(self, orders):
        buckets = {}
        for order in orders.sorted(key=lambda item: item.create_date or item.write_date or item.id):
            stamp = order.create_date
            label = stamp.strftime('%b %Y') if stamp else 'Undated'
            buckets[label] = buckets.get(label, 0.0) + (order.amount_total or 0.0)
        return [{'label': label, 'spend': amount} for label, amount in buckets.items()]

    @api.model
    def get_requisitions(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state:
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', '|', ('name', 'ilike', search), ('title', 'ilike', search), ('department', 'ilike', search)])
        rows = self.env['procurement.management.requisition'].search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'name': row.name,
            'title': row.title,
            'requester': row.requester_id.name,
            'company': row.company_id.name,
            'department': row.department or '',
            'property_project': row.property_project or '',
            'state': row.state,
            'required_date': row.required_date,
            'amount_total': row.amount_total,
        } for row in rows]

    @api.model
    def get_rfqs(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state:
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', ('name', 'ilike', search), ('description', 'ilike', search)])
        rows = self.env['procurement.management.rfq'].search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'name': row.name,
            'requisition': row.requisition_id.name or '',
            'deadline': row.deadline,
            'state': row.state,
            'estimated_value': row.estimated_value,
            'response_count': row.response_count,
            'supplier_count': len(row.supplier_ids),
        } for row in rows]

    @api.model
    def get_comparison(self, rfq_id=False):
        self._check('group_procurement_user')
        empty = {
            'rfq_id': False,
            'rfq_name': '',
            'state': False,
            'selection_status': False,
            'commercial_weight': 0,
            'technical_weight': 0,
            'recommended_quotation_id': False,
            'rows': [],
        }
        if not rfq_id:
            return empty
        rfq = self.env['procurement.management.rfq'].search([('id', '=', rfq_id)], limit=1)
        if not rfq:
            return empty
        from ..services.comparison_service import ComparisonService
        return ComparisonService(self.env).dto(rfq)

    @api.model
    def get_approval_matrices(self):
        self._check('group_procurement_manager')
        rows = self.env['procurement.management.approval.matrix'].search([])
        return [{
            'id': row.id,
            'name': row.name,
            'company': row.company_id.name,
            'min_value': row.min_value,
            'max_value': row.max_value,
            'department': row.department or '',
            'property_location': row.property_location or '',
            'category': row.category or '',
            'sequence': row.sequence,
            'state': row.state,
            'levels': [{
                'id': level.id,
                'sequence': level.sequence,
                'approver_group': level.approver_group_id.name,
                'required_signoff': level.required_signoff,
                'mode': level.mode,
                'escalation_hours': level.escalation_hours,
            } for level in row.level_ids],
        } for row in rows]

    @api.model
    def get_purchase_orders(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state and state not in ('partial', 'overdue'):
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', ('name', 'ilike', search), ('partner_id.name', 'ilike', search)])
        orders = self.env['procurement.management.purchase.order']
        if state in ('partial', 'overdue'):
            matched = orders.search(domain).filtered(lambda order: order.display_status == state)
            start = offset or 0
            rows = matched[start:start + limit] if limit else matched[start:]
        else:
            rows = orders.search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'name': row.name,
            'supplier': row.partner_id.name,
            'requisition': row.requisition_id.name or '',
            'company': row.company_id.name,
            'property_project': row.property_project or '',
            'amount_total': row.amount_total,
            'delivery_date': row.delivery_date,
            'state': row.state,
            'display_status': row.display_status,
            'acknowledged': bool(row.acknowledged_on),
            'closed': bool(row.closed_on),
        } for row in rows]

    @api.model
    def get_goods_receipts(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state:
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', ('name', 'ilike', search), ('order_id.name', 'ilike', search)])
        rows = self.env['procurement.management.receipt'].search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'name': row.name,
            'purchase_order': row.order_id.name,
            'supplier': row.partner_id.name,
            'date': row.receipt_date,
            'state': row.state,
            'inspection_result': row.inspection_result or '',
        } for row in rows]

    @api.model
    def get_invoice_matches(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state:
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', ('name', 'ilike', search), ('supplier_invoice_number', 'ilike', search)])
        rows = self.env['procurement.management.invoice.match'].search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'name': row.name,
            'supplier_invoice_number': row.supplier_invoice_number,
            'supplier': row.partner_id.name,
            'purchase_order': row.order_id.name,
            'invoice_amount': row.invoice_amount,
            'matched_amount': row.matched_amount,
            'variance': row.amount_variance,
            'state': row.state,
            'duplicate_flag': row.duplicate_flag,
            'exception_reason': row.exception_reason or '',
            'resolution': row.resolution or '',
        } for row in rows]

    @api.model
    def get_suppliers(self, search=None, state=None, limit=None, offset=0):
        self._check('group_procurement_user')
        domain = []
        if state:
            domain.append(('state', '=', state))
        if search:
            domain.extend(['|', '|', ('partner_id.name', 'ilike', search), ('vendor_code', 'ilike', search), ('category', 'ilike', search)])
        rows = self.env['procurement.management.supplier.profile'].search(domain, limit=limit or None, offset=offset or 0)
        return [{
            'id': row.id,
            'partner': row.partner_id.name,
            'vendor_code': row.vendor_code or '',
            'category': row.category or '',
            'score': row.score,
            'preferred': row.preferred,
            'state': row.state,
            'contracts': [{
                'id': contract.id,
                'name': contract.name,
                'reference': contract.reference,
                'type': contract.contract_type or '',
                'date_start': contract.date_start,
                'date_end': contract.date_end,
                'state': contract.state,
            } for contract in row.contract_ids],
        } for row in rows]

    @api.model
    def get_reports(self):
        self._check('group_procurement_user')
        rows = self.env['procurement.management.report.definition'].search([])
        return [self._definition_dto(row) for row in rows]

    @api.model
    def get_report_builder(self):
        self._check('group_procurement_user')
        rows = self.env['procurement.management.report.definition'].search([])
        return {
            'definitions': [self._definition_dto(row, include_runs=True) for row in rows],
            'report_types': ['spend', 'performance', 'requisitions', 'rfq', 'custom'],
            'formats': ['csv', 'xlsx', 'pdf'],
            'schedules': ['none', 'weekly', 'monthly'],
        }

    def _definition_dto(self, row, include_runs=False):
        payload = {
            'id': row.id,
            'name': row.name,
            'report_type': row.report_type,
            'date_from': row.date_from,
            'date_to': row.date_to,
            'department': row.department or '',
            'supplier': row.partner_id.name or '',
            'category': row.category or '',
            'status': row.status or '',
            'metrics': row.metrics or '',
            'group_by': row.group_by or '',
            'sort_by': row.sort_by or '',
            'schedule': row.schedule,
            'weekday': row.weekday,
            'month_day': row.month_day,
            'recipient_emails': row.recipient_emails or '',
            'last_run_on': row.last_run_on,
            'partner_id': row.partner_id.id,
        }
        if include_runs:
            payload['runs'] = [{
                'id': run.id,
                'name': run.name,
                'state': run.state,
                'file_format': run.file_format or '',
                'error_detail': run.error_detail or '',
                'started_on': run.started_on,
                'finished_on': run.finished_on,
            } for run in row.run_ids]
        return payload

    @api.model
    def get_audit(self, search=None, limit=80, offset=0):
        self._check('group_procurement_manager')
        domain = []
        if search:
            domain = ['|', '|', '|',
                      ('reference', 'ilike', search),
                      ('action', 'ilike', search),
                      ('detail', 'ilike', search),
                      ('res_model', 'ilike', search)]
        events = self.env['procurement.management.audit.event'].search(
            domain, limit=limit or 80, offset=offset or 0, order='id desc',
        )
        return [{
            'id': event.id,
            'timestamp': event.event_time,
            'user': event.user_id.name,
            'company': event.company_id.name,
            'action': event.action,
            'model': event.res_model or '',
            'reference': event.reference or '',
            'status': event.status,
            'before': event.before_value or '',
            'after': event.after_value or '',
            'detail': event.detail or '',
        } for event in events]
