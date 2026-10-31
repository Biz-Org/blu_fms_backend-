# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError

ALLOWED_AUDIT_ACTIONS = frozenset({
    'create', 'update', 'publish', 'activate', 'deactivate',
    'approve', 'reject', 'assign', 'reassign', 'complete',
    'retry', 'escalate', 'failure',
})


class WorkflowAuditService:
    """Centralized Workflow Engine audit/event recording."""

    def __init__(self, env):
        self.env = env

    def log(self, action, *, record=None, execution=None, details=None, model=None, res_id=None):
        if action not in ALLOWED_AUDIT_ACTIONS:
            raise ValidationError('Unsupported audit action: %s' % action)
        company = self.env.company
        if record is not None and getattr(record, 'company_id', False):
            company = record.company_id
        elif execution is not None and execution.company_id:
            company = execution.company_id
        vals = {
            'name': action,
            'action': action,
            'user_id': self.env.user.id,
            'model': model or (record._name if record is not None else False),
            'res_id': res_id if res_id is not None else (record.id if record is not None else False),
            'execution_id': execution.id if execution else False,
            'details': details or '',
            'company_id': company.id,
        }
        return self.env['workflow.engine.audit.event'].sudo().create(vals)
