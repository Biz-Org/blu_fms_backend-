# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.common import has_group, self_approval_policy
from ..services.comparison_service import ComparisonService
from ..services.supplier_service import SupplierService


ATTACHMENT_MODELS = {
    'procurement.management.requisition',
    'procurement.management.rfq',
    'procurement.management.quotation',
    'procurement.management.purchase.order',
    'procurement.management.receipt',
    'procurement.management.invoice.match',
    'procurement.management.contract',
}

PAGE = 20


class ProcurementUiScreens(models.AbstractModel):
    _inherit = 'procurement.management.ui.api'

    def _one(self, model, res_id):
        record = self.env[model].search([('id', '=', res_id)], limit=1)
        if not record:
            raise AccessError('You cannot open this record.')
        return record

    def _officer(self):
        return has_group(self.env, 'group_procurement_officer')

    def _manager(self):
        return has_group(self.env, 'group_procurement_manager')

    def _admin(self):
        return has_group(self.env, 'group_procurement_admin')

    def _counts(self, model, states):
        records = self.env[model]
        return {state: records.search_count([('state', '=', state)]) for state in states}

    def _ilike(self, field_names, term):
        if not term:
            return []
        leaves = [(name, 'ilike', term) for name in field_names]
        return (['|'] * (len(leaves) - 1)) + leaves

    def _counted(self, model, field_names, search=None, state=None):
        domain = []
        if state:
            domain.append(('state', '=', state))
        domain.extend(self._ilike(field_names, search))
        return self.env[model].search_count(domain)

    def _approval_view(self, model_name, res_id, purpose, requester=None):
        request = self.env['procurement.management.approval.request'].sudo().search([
            ('res_model', '=', model_name),
            ('res_id', '=', res_id),
            ('purpose', '=', purpose),
        ], order='id desc', limit=1)
        if not request:
            return {'request_state': False, 'can_decide': False, 'decisions': []}
        group_ids = set(self.env.user.groups_id.ids)
        pending = request.decision_ids.filtered(
            lambda row: row.decision == 'pending' and row.group_id.id in group_ids
        )
        levels = request.matrix_id.level_ids
        mode = levels[:1].mode or 'sequential'
        if mode == 'sequential' and request.current_level_id:
            pending = pending.filtered(lambda row: row.level_id == request.current_level_id)
        policy = self_approval_policy(self.env)
        blocked = policy == 'A' and request.requester_id == self.env.user
        return {
            'request_state': request.state,
            'can_decide': bool(pending) and request.state == 'pending' and not blocked,
            'self_approval': policy or '',
            'decisions': [{
                'group': row.group_id.display_name,
                'decision': row.decision,
                'comment': row.comment or '',
            } for row in request.decision_ids],
        }

    def _decide(self, document, purpose, command, comment=''):
        request = self.env['procurement.management.approval.request'].sudo().search([
            ('res_model', '=', document._name),
            ('res_id', '=', document.id),
            ('purpose', '=', purpose),
            ('state', '=', 'pending'),
        ], limit=1)
        if not request:
            raise UserError('There is no pending approval for this document.')
        request = request.with_user(self.env.user)
        if command == 'approve':
            request.action_approve(comment or '')
        elif command == 'reject':
            request.action_reject(comment or '')
        elif command == 'return':
            request.action_return(comment or '')
        else:
            raise UserError('Unsupported approval action.')

    def _attachments(self, record):
        rows = self.env['ir.attachment'].search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
        ])
        return [{'id': row.id, 'name': row.name, 'mimetype': row.mimetype or ''} for row in rows]

    @api.model
    def get_navigation(self):
        self._check('group_procurement_user')
        manager = self._manager()
        return {
            'approval_matrix': manager,
            'audit': manager,
            'reports_run': manager,
        }

    @api.model
    def get_requisition_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = ['draft', 'pending', 'approved', 'rejected', 'returned', 'cancelled', 'converted']
        counts = self._counts('procurement.management.requisition', states)
        return {
            'counts': counts,
            'total': self._counted(
                'procurement.management.requisition',
                ['name', 'title', 'department'], search, state,
            ),
            'actions': {'create': True},
        }

    @api.model
    def get_requisition_detail(self, requisition_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.requisition', requisition_id)
        approval = self._approval_view(record._name, record.id, 'requisition', record.requester_id)
        editable = record.state in ('draft', 'returned') and (
            record.requester_id == self.env.user or self._officer()
        )
        return {
            'id': record.id,
            'name': record.name,
            'title': record.title or '',
            'description': record.description or '',
            'justification': record.justification or '',
            'requester': record.requester_id.name,
            'department': record.department or '',
            'property_project': record.property_project or '',
            'category': record.category or '',
            'cost_center': record.cost_center or '',
            'required_date': record.required_date,
            'state': record.state,
            'amount_total': record.amount_total,
            'currency': record.currency_id.name or '',
            'lines': [{
                'id': line.id,
                'description': line.description,
                'quantity': line.quantity,
                'unit_text': line.unit_text or '',
                'price_unit': line.price_unit,
                'cost_center': line.cost_center or '',
                'price_subtotal': line.price_subtotal,
            } for line in record.line_ids],
            'attachments': self._attachments(record),
            'approval': approval,
            'actions': {
                'edit': editable,
                'submit': record.state in ('draft', 'returned'),
                'cancel': record.state in ('draft', 'pending', 'returned'),
                'approve': approval['can_decide'],
                'reject': approval['can_decide'],
                'return': approval['can_decide'],
                'convert': record.state == 'approved' and self._officer() and not record.converted_res_id,
            },
        }

    def _line_commands(self, existing, rows):
        seen = set()
        commands = []
        for row in rows or []:
            vals = {
                'description': row.get('description') or 'Item',
                'quantity': row.get('quantity') or 1.0,
                'unit_text': row.get('unit_text') or '',
                'price_unit': row.get('price_unit') or 0.0,
                'cost_center': row.get('cost_center') or '',
            }
            line_id = row.get('id')
            if line_id and existing.filtered(lambda line: line.id == line_id):
                commands.append((1, line_id, vals))
                seen.add(line_id)
            else:
                commands.append((0, 0, vals))
        for line in existing:
            if line.id not in seen:
                if not self._officer():
                    raise UserError('You cannot remove a requisition line.')
                commands.append((2, line.id, 0))
        return commands

    @api.model
    def save_requisition(self, payload):
        self._check('group_procurement_user')
        payload = payload or {}
        if not (payload.get('title') or '').strip():
            raise UserError('A requisition needs a title.')
        values = {
            'title': payload.get('title'),
            'description': payload.get('description') or '',
            'justification': payload.get('justification') or '',
            'department': payload.get('department') or '',
            'property_project': payload.get('property_project') or '',
            'category': payload.get('category') or '',
            'cost_center': payload.get('cost_center') or '',
            'required_date': payload.get('required_date') or False,
        }
        model = self.env['procurement.management.requisition']
        if payload.get('id'):
            record = self._one(model._name, payload['id'])
            values['line_ids'] = self._line_commands(record.line_ids, payload.get('lines'))
            record.write(values)
        else:
            values['line_ids'] = [(0, 0, {
                'description': row.get('description') or 'Item',
                'quantity': row.get('quantity') or 1.0,
                'unit_text': row.get('unit_text') or '',
                'price_unit': row.get('price_unit') or 0.0,
                'cost_center': row.get('cost_center') or '',
            }) for row in payload.get('lines') or []]
            record = model.create(values)
        return self.get_requisition_detail(record.id)

    @api.model
    def requisition_command(self, requisition_id, command, comment='', partner_id=False):
        self._check('group_procurement_user')
        record = self._one('procurement.management.requisition', requisition_id)
        if command == 'submit':
            record.action_submit()
        elif command == 'cancel':
            record.action_cancel()
        elif command == 'convert_rfq':
            record.action_convert_rfq()
        elif command == 'convert_po':
            partner = self.env['res.partner'].browse(partner_id).exists()
            if not partner:
                raise UserError('Choose a supplier before converting to a purchase order.')
            record.action_convert_po(partner)
        elif command in ('approve', 'reject', 'return'):
            self._decide(record, 'requisition', command, comment)
        else:
            raise UserError('Unsupported requisition action.')
        return self.get_requisition_detail(record.id)

    @api.model
    def get_rfq_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = [
            'draft', 'issued', 'supplier_responded', 'partially_responded',
            'under_evaluation', 'closed', 'cancelled',
        ]
        counts = self._counts('procurement.management.rfq', states)
        return {
            'counts': counts,
            'total': self._counted(
                'procurement.management.rfq', ['name', 'description'], search, state,
            ),
            'actions': {'create': self._officer()},
        }

    @api.model
    def get_rfq_detail(self, rfq_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.rfq', rfq_id)
        officer = self._officer()
        return {
            'id': record.id,
            'name': record.name,
            'description': record.description or '',
            'department': record.department or '',
            'property_project': record.property_project or '',
            'category': record.category or '',
            'deadline': record.deadline,
            'estimated_value': record.estimated_value,
            'commercial_weight': record.commercial_weight,
            'technical_weight': record.technical_weight,
            'state': record.state,
            'selection_status': record.selection_status,
            'requisition': record.requisition_id.name or '',
            'currency': record.currency_id.name or '',
            'suppliers': [{
                'id': invitation.id,
                'partner_id': invitation.partner_id.id,
                'partner': invitation.partner_id.name,
                'response_status': invitation.response_status,
            } for invitation in record.supplier_ids],
            'quotations': [{
                'id': quotation.id,
                'name': quotation.name,
                'supplier': quotation.partner_id.name,
                'partner_id': quotation.partner_id.id,
                'amount_total': quotation.amount_total,
                'amount_tax': quotation.amount_tax,
                'freight_amount': quotation.freight_amount,
                'state': quotation.state,
                'commercial_score': quotation.commercial_score,
                'technical_score': quotation.technical_score,
                'weighted_score': quotation.weighted_score,
                'evaluation_notes': quotation.evaluation_notes or '',
                'lines': [{
                    'description': line.description,
                    'quantity': line.quantity,
                    'unit_text': line.unit_text or '',
                    'price_unit': line.price_unit,
                } for line in quotation.line_ids],
            } for quotation in record.quotation_ids],
            'actions': {
                'edit': officer and record.state == 'draft',
                'issue': officer and record.state == 'draft',
                'evaluate': officer and record.response_count >= 1 and record.state in (
                    'supplier_responded', 'partially_responded'
                ),
                'close': officer and record.state in (
                    'under_evaluation', 'supplier_responded', 'partially_responded'
                ),
                'cancel': officer and record.state in ('draft', 'issued', 'partially_responded'),
                'quote': officer and record.state not in ('closed', 'cancelled', 'draft'),
            },
        }

    @api.model
    def save_rfq(self, payload):
        self._check('group_procurement_officer')
        payload = payload or {}
        values = {
            'description': payload.get('description') or '',
            'department': payload.get('department') or '',
            'property_project': payload.get('property_project') or '',
            'category': payload.get('category') or '',
            'deadline': payload.get('deadline') or False,
            'estimated_value': payload.get('estimated_value') or 0.0,
            'commercial_weight': payload.get('commercial_weight') if payload.get('commercial_weight') is not None else 40.0,
            'technical_weight': payload.get('technical_weight') if payload.get('technical_weight') is not None else 60.0,
        }
        model = self.env['procurement.management.rfq']
        if payload.get('id'):
            record = self._one(model._name, payload['id'])
            record.write(values)
            wanted = set(payload.get('partner_ids') or [])
            current = {invitation.partner_id.id: invitation for invitation in record.supplier_ids}
            for partner_id, invitation in current.items():
                if partner_id not in wanted:
                    if not self._admin():
                        raise UserError('An administrator must remove a supplier invitation.')
                    invitation.unlink()
            for partner_id in wanted:
                if partner_id not in current:
                    record.write({'supplier_ids': [(0, 0, {'partner_id': partner_id})]})
        else:
            values['requisition_id'] = payload.get('requisition_id') or False
            values['supplier_ids'] = [(0, 0, {'partner_id': partner_id}) for partner_id in payload.get('partner_ids') or []]
            record = model.create(values)
        return self.get_rfq_detail(record.id)

    @api.model
    def save_quotation(self, payload):
        self._check('group_procurement_officer')
        payload = payload or {}
        rfq = self._one('procurement.management.rfq', payload.get('rfq_id'))
        partner = self.env['res.partner'].browse(payload.get('partner_id')).exists()
        if not partner:
            raise UserError('Choose the supplier who sent this quotation.')
        lines = [(0, 0, {
            'description': row.get('description') or 'Item',
            'quantity': row.get('quantity') or 1.0,
            'unit_text': row.get('unit_text') or '',
            'price_unit': row.get('price_unit') or 0.0,
        }) for row in payload.get('lines') or []]
        if not lines:
            raise UserError('A quotation needs at least one line.')
        self.env['procurement.management.quotation'].create({
            'rfq_id': rfq.id,
            'partner_id': partner.id,
            'company_id': rfq.company_id.id,
            'amount_tax': payload.get('amount_tax') or 0.0,
            'freight_amount': payload.get('freight_amount') or 0.0,
            'line_ids': lines,
        })
        return self.get_rfq_detail(rfq.id)

    @api.model
    def rfq_command(self, rfq_id, command):
        self._check('group_procurement_officer')
        record = self._one('procurement.management.rfq', rfq_id)
        actions = {
            'issue': record.action_issue,
            'evaluate': record.action_start_evaluation,
            'close': record.action_close,
            'cancel': record.action_cancel,
        }
        action = actions.get(command)
        if not action:
            raise UserError('Unsupported RFQ action.')
        action()
        return self.get_rfq_detail(record.id)

    @api.model
    def get_comparison_screen(self, rfq_id=False):
        self._check('group_procurement_user')
        payload = self.get_comparison(rfq_id)
        options = self.env['procurement.management.rfq'].search([], limit=50)
        payload['options'] = [{'id': row.id, 'name': row.name, 'state': row.state} for row in options]
        officer = self._officer()
        state = payload.get('state')
        selection = payload.get('selection_status')
        open_eval = officer and state == 'under_evaluation' and selection != 'pending'
        payload['actions'] = {
            'save': open_eval,
            'reject': open_eval,
            'select': officer and state == 'under_evaluation' and selection not in ('pending', 'effective'),
        }
        payload['currency'] = self.env.company.currency_id.name or ''
        return payload

    @api.model
    def comparison_save(self, rfq_id, commercial_weight, technical_weight, rows):
        self._check('group_procurement_officer')
        rfq = self._one('procurement.management.rfq', rfq_id)
        ComparisonService(self.env).save_evaluation(rfq, commercial_weight, technical_weight, rows or [])
        return self.get_comparison_screen(rfq.id)

    @api.model
    def comparison_reject(self, quotation_id, comment=''):
        self._check('group_procurement_officer')
        quotation = self._one('procurement.management.quotation', quotation_id)
        ComparisonService(self.env).reject_quotation(quotation, comment or '')
        return self.get_comparison_screen(quotation.rfq_id.id)

    @api.model
    def comparison_select(self, quotation_id, justification=''):
        self._check('group_procurement_officer')
        quotation = self._one('procurement.management.quotation', quotation_id)
        if justification:
            quotation.write({'evaluation_notes': justification})
        request = ComparisonService(self.env).select_supplier(quotation)
        screen = self.get_comparison_screen(quotation.rfq_id.id)
        order = self.env['procurement.management.purchase.order'].search([
            ('quotation_id', '=', quotation.id),
            ('state', '!=', 'cancelled'),
        ], limit=1)
        screen['selection_result'] = request.state
        screen['purchase_order'] = order.name or ''
        return screen

    @api.model
    def get_matrix_meta(self):
        self._check('group_procurement_manager')
        states = ['draft', 'review', 'active', 'inactive']
        counts = self._counts('procurement.management.approval.matrix', states)
        return {
            'counts': counts,
            'total': sum(counts.values()),
            'actions': {'create': True, 'activate': self._admin()},
        }

    @api.model
    def list_groups(self, search=None):
        self._check('group_procurement_manager')
        domain = [('name', 'ilike', search)] if search else []
        groups = self.env['res.groups'].search(domain, limit=80, order='name')
        return [{'id': group.id, 'name': group.display_name} for group in groups]

    @api.model
    def list_companies(self):
        self._check('group_procurement_user')
        return [{'id': company.id, 'name': company.name} for company in self.env.user.company_ids]

    @api.model
    def get_matrix_detail(self, matrix_id):
        self._check('group_procurement_manager')
        record = self._one('procurement.management.approval.matrix', matrix_id)
        mode = record.level_ids[:1].mode or 'sequential'
        return {
            'id': record.id,
            'name': record.name,
            'company_id': record.company_id.id,
            'company': record.company_id.name,
            'min_value': record.min_value,
            'max_value': record.max_value,
            'department': record.department or '',
            'property_location': record.property_location or '',
            'category': record.category or '',
            'sequence': record.sequence,
            'state': record.state,
            'mode': mode,
            'levels': [{
                'id': level.id,
                'sequence': level.sequence,
                'approver_group_id': level.approver_group_id.id,
                'approver_group': level.approver_group_id.display_name,
                'required_signoff': level.required_signoff,
                'mode': level.mode,
                'escalation_hours': level.escalation_hours,
                'escalation_group_id': level.escalation_group_id.id,
                'escalation_group': level.escalation_group_id.display_name or '',
            } for level in record.level_ids],
            'actions': {
                'edit': record.state in ('draft', 'review', 'inactive'),
                'review': record.state == 'draft',
                'activate': self._admin() and record.state in ('draft', 'review', 'inactive'),
                'deactivate': self._admin() and record.state == 'active',
            },
        }

    def _sync_levels(self, record, level_rows):
        existing = list(record.level_ids)
        if len(level_rows) < len(existing):
            if not self._admin():
                raise UserError('An administrator must remove approval levels.')
            for level in existing[len(level_rows):]:
                level.unlink()
            existing = existing[:len(level_rows)]
        Level = self.env['procurement.management.approval.level']
        for index, vals in enumerate(level_rows):
            if index < len(existing):
                existing[index].write(vals)
            else:
                Level.create(dict(vals, matrix_id=record.id))

    @api.model
    def save_matrix(self, payload):
        self._check('group_procurement_manager')
        payload = payload or {}
        if not (payload.get('name') or '').strip():
            raise UserError('A matrix needs a name.')
        company_id = payload.get('company_id') or self.env.company.id
        if company_id not in self.env.user.company_ids.ids:
            raise AccessError('You cannot configure a matrix for that company.')
        mode = payload.get('mode') or 'sequential'
        if mode not in ('sequential', 'parallel'):
            raise UserError('Approval mode must be sequential or parallel.')
        level_values = []
        for index, level in enumerate(payload.get('levels') or [], start=1):
            if not level.get('approver_group_id'):
                raise UserError('Each approval level needs an approver group.')
            level_values.append((0, 0, {
                'sequence': level.get('sequence') or index * 10,
                'approver_group_id': level['approver_group_id'],
                'required_signoff': bool(level.get('required_signoff', True)),
                'mode': mode,
                'escalation_hours': level.get('escalation_hours') or 0.0,
                'escalation_group_id': level.get('escalation_group_id') or False,
            }))
        values = {
            'name': payload.get('name'),
            'company_id': company_id,
            'min_value': payload.get('min_value') or 0.0,
            'max_value': payload.get('max_value') or 0.0,
            'department': payload.get('department') or False,
            'property_location': payload.get('property_location') or False,
            'category': payload.get('category') or False,
            'sequence': payload.get('sequence') or 10,
        }
        model = self.env['procurement.management.approval.matrix']
        level_rows = [command[2] for command in level_values]
        if payload.get('id'):
            record = self._one(model._name, payload['id'])
            record.write(values)
            self._sync_levels(record, level_rows)
        else:
            values['level_ids'] = level_values
            record = model.create(values)
        command = payload.get('command')
        if command == 'review':
            record.action_submit_review()
        elif command == 'activate':
            record.action_activate()
        elif command == 'deactivate':
            record.action_deactivate()
        elif command:
            raise UserError('Unsupported matrix action.')
        return self.get_matrix_detail(record.id)

    @api.model
    def get_purchase_order_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = ['draft', 'pending', 'approved', 'issued', 'acknowledged', 'closed', 'cancelled']
        counts = self._counts('procurement.management.purchase.order', states)
        open_orders = self.env['procurement.management.purchase.order'].search([
            ('state', 'in', ['issued', 'acknowledged']),
        ])
        counts['partial'] = len(open_orders.filtered(lambda order: order.display_status == 'partial'))
        counts['overdue'] = len(open_orders.filtered(lambda order: order.display_status == 'overdue'))
        orders = self.env['procurement.management.purchase.order']
        if state in ('partial', 'overdue'):
            domain = self._ilike(['name', 'partner_id.name'], search)
            total = len(orders.search(domain).filtered(lambda order: order.display_status == state))
        else:
            total = self._counted(
                'procurement.management.purchase.order',
                ['name', 'partner_id.name'], search, state,
            )
        return {'counts': counts, 'total': total, 'actions': {'create': False}}

    @api.model
    def get_purchase_order_detail(self, order_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.purchase.order', order_id)
        approval = self._approval_view(record._name, record.id, 'purchase_order', record.create_uid)
        officer = self._officer()
        return {
            'id': record.id,
            'name': record.name,
            'supplier': record.partner_id.name,
            'partner_id': record.partner_id.id,
            'department': record.department or '',
            'property_project': record.property_project or '',
            'category': record.category or '',
            'delivery_date': record.delivery_date,
            'state': record.state,
            'display_status': record.display_status,
            'amount_total': record.amount_total,
            'currency': record.currency_id.name or '',
            'lines': [{
                'id': line.id,
                'description': line.description,
                'quantity': line.quantity,
                'unit_text': line.unit_text or '',
                'price_unit': line.price_unit,
                'cost_center': line.cost_center or '',
                'price_subtotal': line.price_subtotal,
            } for line in record.line_ids],
            'receipts': [{
                'id': receipt.id,
                'name': receipt.name,
                'state': receipt.state,
                'date': receipt.receipt_date,
            } for receipt in record.receipt_ids],
            'invoices': [{
                'id': match.id,
                'name': match.name,
                'state': match.state,
                'variance': match.amount_variance,
            } for match in record.invoice_ids],
            'approval': approval,
            'actions': {
                'submit': officer and record.state == 'draft',
                'approve': approval['can_decide'],
                'reject': approval['can_decide'],
                'return': approval['can_decide'],
                'issue': officer and record.state == 'approved',
                'acknowledge': officer and record.state == 'issued',
                'close': officer and record.state in ('issued', 'acknowledged'),
                'cancel': officer and record.state in ('draft', 'pending'),
                'print': True,
                'receive': officer and record.state in ('issued', 'acknowledged') and bool(record.receipt_ids),
                'edit_lines': officer and record.state in ('draft', 'approved', 'issued', 'acknowledged'),
            },
        }

    @api.model
    def purchase_order_command(self, order_id, command, comment=''):
        self._check('group_procurement_user')
        record = self._one('procurement.management.purchase.order', order_id)
        if command == 'submit':
            record.action_submit()
        elif command == 'issue':
            record.action_issue()
        elif command == 'acknowledge':
            record.action_acknowledge()
        elif command == 'close':
            record.action_close()
        elif command == 'cancel':
            record.action_cancel()
        elif command in ('approve', 'reject', 'return'):
            self._decide(record, 'purchase_order', command, comment)
        else:
            raise UserError('Unsupported purchase order action.')
        return self.get_purchase_order_detail(record.id)

    @api.model
    def save_purchase_order_lines(self, order_id, lines):
        self._check('group_procurement_officer')
        record = self._one('procurement.management.purchase.order', order_id)
        for row in lines or []:
            line = record.line_ids.filtered(lambda item: item.id == row.get('id'))[:1]
            if not line:
                continue
            line.write({
                'description': row.get('description') or line.description,
                'quantity': row.get('quantity') or line.quantity,
                'unit_text': row.get('unit_text') or '',
                'price_unit': row.get('price_unit') if row.get('price_unit') is not None else line.price_unit,
                'cost_center': row.get('cost_center') or '',
            })
        return self.get_purchase_order_detail(record.id)

    @api.model
    def print_purchase_order(self, order_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.purchase.order', order_id)
        report = self.env.ref('procurement_management.action_report_pm_purchase_order', raise_if_not_found=False)
        if not report:
            return {'ok': False, 'error': 'PDF export is unavailable because the purchase order report is missing.'}
        try:
            pdf, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'procurement_management.action_report_pm_purchase_order', [record.id],
            )
        except Exception as exc:
            return {'ok': False, 'error': 'PDF export is unavailable. %s' % exc}
        if not pdf or not bytes(pdf).startswith(b'%PDF'):
            return {'ok': False, 'error': 'PDF export is unavailable. The server did not return a PDF document.'}
        return {
            'ok': True,
            'filename': '%s.pdf' % record.name,
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(bytes(pdf)).decode(),
        }

    @api.model
    def get_receipt_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = [
            'expected', 'pending_receipt', 'receiving',
            'pending_inspection', 'inspection', 'completed',
        ]
        counts = self._counts('procurement.management.receipt', states)
        return {
            'counts': counts,
            'total': self._counted(
                'procurement.management.receipt', ['name', 'order_id.name'], search, state,
            ),
        }

    @api.model
    def get_receipt_detail(self, receipt_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.receipt', receipt_id)
        officer = self._officer()
        return {
            'id': record.id,
            'name': record.name,
            'purchase_order': record.order_id.name,
            'order_id': record.order_id.id,
            'supplier': record.partner_id.name,
            'date': record.receipt_date,
            'state': record.state,
            'inspection_result': record.inspection_result or '',
            'delivery_notes': record.delivery_notes or '',
            'lines': [{
                'id': line.id,
                'description': line.description,
                'ordered_qty': line.ordered_qty,
                'received_qty': line.received_qty,
                'remaining_qty': max((line.ordered_qty or 0.0) - (line.received_qty or 0.0), 0.0),
                'batch_lot': line.batch_lot or '',
                'inspection_notes': line.inspection_notes or '',
            } for line in record.line_ids],
            'actions': {
                'start': officer and record.state == 'expected',
                'save': officer and record.state in ('expected', 'pending_receipt', 'receiving'),
                'confirm': officer and record.state in ('expected', 'pending_receipt', 'receiving'),
                'inspect': officer and record.state in ('pending_inspection', 'inspection'),
                'invoice': officer and record.state == 'completed' and record.inspection_result == 'pass' and not self.env['procurement.management.invoice.match'].search_count([
                    ('receipt_id', '=', record.id),
                ]),
            },
        }

    @api.model
    def receipt_command(self, receipt_id, command, quantities=None, result=None, notes='', delivery_notes=None, lines=None):
        self._check('group_procurement_officer')
        record = self._one('procurement.management.receipt', receipt_id)
        if delivery_notes is not None:
            record.write({'delivery_notes': delivery_notes or ''})
        for row in lines or []:
            line = record.line_ids.filtered(lambda item: item.id == row.get('id'))[:1]
            if line and row.get('batch_lot') is not None:
                line.write({'batch_lot': row.get('batch_lot') or ''})
        if command == 'start':
            record.action_start()
        elif command == 'save':
            record.action_save_draft(quantities or {})
        elif command == 'confirm':
            record.action_confirm(quantities or {})
        elif command == 'inspect':
            record.action_inspect(result, notes or '')
        else:
            raise UserError('Unsupported receipt action.')
        fresh = self.env['procurement.management.receipt'].search([('id', '=', record.id)], limit=1)
        return self.get_receipt_detail(fresh.id if fresh else record.id)

    @api.model
    def get_invoice_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = ['pending', 'matched', 'mismatch', 'under_review']
        counts = self._counts('procurement.management.invoice.match', states)
        return {
            'counts': counts,
            'total': self._counted(
                'procurement.management.invoice.match',
                ['name', 'supplier_invoice_number'], search, state,
            ),
            'actions': {'create': self._officer()},
        }

    @api.model
    def get_invoice_detail(self, match_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.invoice.match', match_id)
        officer = self._officer()
        manager = self._manager()
        return {
            'id': record.id,
            'name': record.name,
            'supplier_invoice_number': record.supplier_invoice_number,
            'supplier': record.partner_id.name,
            'purchase_order': record.order_id.name,
            'receipt': record.receipt_id.name or '',
            'invoice_date': record.invoice_date,
            'invoice_amount': record.invoice_amount,
            'matched_amount': record.matched_amount,
            'variance': record.amount_variance,
            'state': record.state,
            'duplicate_flag': record.duplicate_flag,
            'exception_reason': record.exception_reason or '',
            'resolution': record.resolution or '',
            'resolution_note': record.resolution_note or '',
            'currency': record.currency_id.name or '',
            'lines': [{
                'id': line.id,
                'description': line.description,
                'po_qty': line.po_qty,
                'receipt_qty': line.receipt_qty,
                'invoice_qty': line.invoice_qty,
                'po_price': line.po_price,
                'invoice_price': line.invoice_price,
                'variance_qty': line.variance_qty,
                'variance_amount': line.variance_amount,
                'matched_amount': line.matched_amount,
            } for line in record.line_ids],
            'actions': {
                'auto_match': officer and record.state in ('pending', 'mismatch'),
                'reject': manager and record.state == 'mismatch',
                'resolve': officer and record.state in ('mismatch', 'under_review'),
                'approve': manager and record.state == 'pending' and record._is_clean(),
            },
        }

    @api.model
    def save_invoice(self, payload):
        self._check('group_procurement_officer')
        payload = payload or {}
        order = self._one('procurement.management.purchase.order', payload.get('order_id'))
        if not (payload.get('supplier_invoice_number') or '').strip():
            raise UserError('Enter the supplier invoice number.')
        lines = [(0, 0, {
            'description': row.get('description') or 'Item',
            'order_line_id': row.get('order_line_id') or False,
            'po_qty': row.get('po_qty') or 0.0,
            'receipt_qty': row.get('receipt_qty') or 0.0,
            'invoice_qty': row.get('invoice_qty') or 0.0,
            'po_price': row.get('po_price') or 0.0,
            'invoice_price': row.get('invoice_price') or 0.0,
        }) for row in payload.get('lines') or []]
        match = self.env['procurement.management.invoice.match'].create({
            'supplier_invoice_number': payload.get('supplier_invoice_number'),
            'partner_id': order.partner_id.id,
            'order_id': order.id,
            'receipt_id': payload.get('receipt_id') or False,
            'company_id': order.company_id.id,
            'invoice_date': payload.get('invoice_date') or fields.Date.context_today(self),
            'invoice_amount': payload.get('invoice_amount') or 0.0,
            'line_ids': lines,
        })
        return self.get_invoice_detail(match.id)

    @api.model
    def invoice_from_receipt(self, receipt_id, supplier_invoice_number):
        self._check('group_procurement_officer')
        record = self._one('procurement.management.receipt', receipt_id)
        if record.state != 'completed' or record.inspection_result != 'pass':
            raise UserError('Invoice matching starts after a passed goods receipt.')
        lines = []
        amount = 0.0
        for line in record.line_ids:
            price = line.order_line_id.price_unit or 0.0
            qty = line.received_qty or 0.0
            lines.append({
                'description': line.description,
                'order_line_id': line.order_line_id.id,
                'po_qty': line.ordered_qty,
                'receipt_qty': qty,
                'invoice_qty': qty,
                'po_price': price,
                'invoice_price': price,
            })
            amount += qty * price
        return self.save_invoice({
            'order_id': record.order_id.id,
            'receipt_id': record.id,
            'supplier_invoice_number': supplier_invoice_number,
            'invoice_amount': amount,
            'lines': lines,
        })

    @api.model
    def invoice_command(self, match_id, command, note=''):
        self._check('group_procurement_user')
        record = self._one('procurement.management.invoice.match', match_id)
        if command == 'auto_match':
            record.action_auto_match()
        elif command == 'approve':
            record.action_approve()
        elif command == 'reject':
            record.action_reject(note or '')
        elif command == 'resolve':
            record.action_resolve(note or '')
        else:
            raise UserError('Unsupported invoice action.')
        return self.get_invoice_detail(record.id)

    @api.model
    def invoice_auto_match_batch(self):
        self._check('group_procurement_officer')
        matches = self.env['procurement.management.invoice.match'].search([
            ('state', 'in', ['pending', 'mismatch']),
        ], limit=40)
        if matches:
            matches.action_auto_match()
        return {'processed': len(matches)}

    @api.model
    def get_supplier_meta(self, search=None, state=None):
        self._check('group_procurement_user')
        states = ['active', 'preferred', 'suspended']
        counts = self._counts('procurement.management.supplier.profile', states)
        return {
            'counts': counts,
            'total': self._counted(
                'procurement.management.supplier.profile',
                ['partner_id.name', 'vendor_code', 'category'], search, state,
            ),
            'actions': {'create': self._officer()},
        }

    @api.model
    def get_supplier_detail(self, profile_id):
        self._check('group_procurement_user')
        record = self._one('procurement.management.supplier.profile', profile_id)
        contacts = record.partner_id.child_ids
        orders = self.env['procurement.management.purchase.order'].search([
            ('partner_id', '=', record.partner_id.id),
            ('company_id', '=', record.company_id.id),
        ], limit=20)
        return {
            'id': record.id,
            'partner_id': record.partner_id.id,
            'partner': record.partner_id.name,
            'email': record.partner_id.email or '',
            'phone': record.partner_id.phone or '',
            'city': record.partner_id.city or '',
            'state_name': record.partner_id.state_id.code or record.partner_id.state_id.name or '',
            'currency': record.company_id.currency_id.name or '',
            'vendor_code': record.vendor_code or '',
            'category': record.category or '',
            'score': record.score,
            'preferred': record.preferred,
            'state': record.state,
            'contacts': [{
                'id': contact.id,
                'name': contact.name,
                'function': contact.function or '',
                'email': contact.email or '',
                'phone': contact.phone or '',
            } for contact in contacts],
            'contracts': [{
                'id': contract.id,
                'name': contract.name,
                'reference': contract.reference,
                'type': contract.contract_type or '',
                'date_start': contract.date_start,
                'date_end': contract.date_end,
                'state': contract.state,
                'payment_terms': contract.payment_terms or '',
                'incoterms': contract.incoterms or '',
                'credit_limit': contract.credit_limit,
            } for contract in record.contract_ids],
            'orders': [{
                'id': order.id,
                'name': order.name,
                'amount_total': order.amount_total,
                'state': order.state,
                'display_status': order.display_status,
                'delivery_date': order.delivery_date,
            } for order in orders],
            'actions': {'edit': self._officer()},
        }

    @api.model
    def search_partners(self, term):
        self._check('group_procurement_officer')
        term = (term or '').strip()
        if not term:
            return []
        partners = self.env['res.partner'].search([('name', 'ilike', term)], limit=20)
        return [{'id': partner.id, 'name': partner.name, 'email': partner.email or ''} for partner in partners]

    @api.model
    def save_supplier(self, payload):
        self._check('group_procurement_officer')
        payload = payload or {}
        partner_id = payload.get('partner_id')
        if not partner_id and (payload.get('partner_name') or '').strip():
            partner = self.env['res.partner'].sudo().create({
                'name': payload.get('partner_name').strip(),
                'email': payload.get('email') or False,
                'phone': payload.get('phone') or False,
                'is_company': True,
            })
            partner_id = partner.id
        if not partner_id:
            raise UserError('Choose or name the supplier.')
        values = {
            'vendor_code': payload.get('vendor_code') or False,
            'category': payload.get('category') or False,
            'score': payload.get('score') or 0.0,
        }
        model = self.env['procurement.management.supplier.profile']
        if payload.get('id'):
            record = self._one(model._name, payload['id'])
            record.write(values)
        else:
            values.update({
                'partner_id': partner_id,
                'company_id': self.env.company.id,
            })
            record = model.create(values)
        if payload.get('state'):
            SupplierService(self.env).set_status(record, payload['state'])
        return self.get_supplier_detail(record.id)

    @api.model
    def save_supplier_contact(self, profile_id, name, email='', phone='', function=''):
        self._check('group_procurement_officer')
        record = self._one('procurement.management.supplier.profile', profile_id)
        if not (name or '').strip():
            raise UserError('A contact needs a name.')
        SupplierService(self.env).add_contact(
            record, name.strip(), email or '', phone or '', function or '',
        )
        return self.get_supplier_detail(record.id)

    @api.model
    def save_contract(self, payload):
        self._check('group_procurement_officer')
        payload = payload or {}
        profile = self._one('procurement.management.supplier.profile', payload.get('profile_id'))
        if not (payload.get('name') or '').strip():
            raise UserError('A contract needs a name.')
        values = {
            'name': payload.get('name'),
            'contract_type': payload.get('contract_type') or 'MSA',
            'date_start': payload.get('date_start') or False,
            'date_end': payload.get('date_end') or False,
            'notes': payload.get('notes') or '',
            'payment_terms': payload.get('payment_terms') or '',
            'incoterms': payload.get('incoterms') or '',
            'credit_limit': payload.get('credit_limit') or 0.0,
            'company_id': profile.company_id.id,
        }
        if payload.get('id'):
            contract = self._one('procurement.management.contract', payload['id'])
            contract.write(values)
        else:
            values['profile_id'] = profile.id
            self.env['procurement.management.contract'].create(values)
        return self.get_supplier_detail(profile.id)

    @api.model
    def get_report_home(self):
        self._check('group_procurement_user')
        definitions = self.get_reports()
        runs = self.env['procurement.management.report.run'].search([], limit=8)
        categories = []
        for key, title in (
            ('spend', 'Spend Analysis'),
            ('performance', 'Supplier Performance'),
            ('requisitions', 'Requisitions'),
            ('rfq', 'RFQs & Quotations'),
            ('custom', 'Saved Custom Reports'),
        ):
            categories.append({
                'key': key,
                'title': title,
                'count': len([row for row in definitions if row['report_type'] == key]),
            })
        return {
            'categories': categories,
            'definitions': definitions,
            'recent': [{
                'id': run.id,
                'name': run.name,
                'state': run.state,
                'file_format': run.file_format or '',
                'error_detail': run.error_detail or '',
                'finished_on': run.finished_on,
            } for run in runs],
            'scheduled': [row for row in definitions if row.get('schedule') and row['schedule'] != 'none'],
            'actions': {'configure': self._manager()},
        }

    @api.model
    def save_report_definition(self, payload):
        self._check('group_procurement_manager')
        payload = payload or {}
        if not (payload.get('name') or '').strip():
            raise UserError('A report needs a name.')
        values = {
            'name': payload.get('name'),
            'report_type': payload.get('report_type') or 'spend',
            'date_from': payload.get('date_from') or False,
            'date_to': payload.get('date_to') or False,
            'department': payload.get('department') or False,
            'partner_id': payload.get('partner_id') or False,
            'category': payload.get('category') or False,
            'status': payload.get('status') or False,
            'metrics': payload.get('metrics') or False,
            'group_by': payload.get('group_by') or False,
            'sort_by': payload.get('sort_by') or False,
            'schedule': payload.get('schedule') or 'none',
            'weekday': payload.get('weekday') or 0,
            'month_day': payload.get('month_day') or 0,
            'recipient_emails': payload.get('recipient_emails') or False,
        }
        model = self.env['procurement.management.report.definition']
        if payload.get('id'):
            record = self._one(model._name, payload['id'])
            record.write(values)
        else:
            record = model.create(values)
        return record.id

    @api.model
    def report_preview(self, definition_id):
        self._check('group_procurement_manager')
        record = self._one('procurement.management.report.definition', definition_id)
        return record.action_preview()

    @api.model
    def report_export(self, definition_id, file_format):
        self._check('group_procurement_manager')
        record = self._one('procurement.management.report.definition', definition_id)
        result = record.action_export(file_format)
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('error') or 'Report export failed.', 'run_id': result.get('run_id')}
        attachment = self.env['ir.attachment'].browse(result.get('attachment_id'))
        datas = attachment.datas
        if isinstance(datas, bytes):
            datas = datas.decode()
        return {
            'ok': True,
            'run_id': result.get('run_id'),
            'filename': attachment.name,
            'mimetype': attachment.mimetype,
            'datas': datas,
        }

    @api.model
    def get_audit_meta(self, search=None):
        self._check('group_procurement_manager')
        events = self.env['procurement.management.audit.event']
        today = fields.Date.context_today(self.env.user)
        start = fields.Datetime.to_datetime(today)
        domain = self._ilike(['reference', 'action', 'detail', 'res_model'], search)
        return {
            'total': events.search_count(domain),
            'today': events.search_count([('event_time', '>=', start)]),
            'approvals': events.search_count([('action', 'in', ['approved', 'rejected'])]),
        }

    @api.model
    def export_audit(self):
        self._check('group_procurement_manager')
        from ..services.audit_service import AuditService
        text = AuditService(self.env).export_csv()
        return {
            'ok': True,
            'filename': 'procurement-audit.csv',
            'mimetype': 'text/csv',
            'datas': base64.b64encode(text.encode()).decode(),
        }

    @api.model
    def add_attachment(self, model_name, res_id, filename, datas):
        self._check('group_procurement_user')
        if model_name not in ATTACHMENT_MODELS:
            raise UserError('Attachments are not accepted for this record.')
        record = self._one(model_name, res_id)
        record.check_access('write')
        if not filename or not datas:
            raise UserError('Choose a file to attach.')
        self.env['ir.attachment'].create({
            'name': filename,
            'datas': datas,
            'res_model': model_name,
            'res_id': record.id,
            'public': False,
        })
        return self._attachments(record)
