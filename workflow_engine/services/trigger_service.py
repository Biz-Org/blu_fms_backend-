# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError

from .audit_service import WorkflowAuditService
from .execution_service import WorkflowExecutionService
from .rule_service import WorkflowRuleService


class WorkflowTriggerService:
    """Approved cross-module trigger contract."""

    def __init__(self, env):
        self.env = env
        self.audit = WorkflowAuditService(env)
        self.rules = WorkflowRuleService(env)
        self.executions = WorkflowExecutionService(env)

    def trigger(self, source_module, source_model, event_code, record=None, payload=None):
        if not source_module or not source_model or not event_code:
            raise ValidationError(
                'source_module, source_model and event_code are required to trigger a workflow.'
            )
        payload = payload if isinstance(payload, dict) else (payload or {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            payload = {'value': payload}

        Trigger = self.env['workflow.engine.trigger']
        triggers = Trigger.search([
            ('active', '=', True),
            ('source_module', '=', source_module),
            ('source_model', '=', source_model),
            ('event_code', '=', event_code),
            ('version_id.state', '=', 'active'),
            ('version_id.definition_id.state', '=', 'active'),
        ], order='version_id, id')

        # Deterministic: unique active versions ordered by definition code then version number
        versions = triggers.mapped('version_id').sorted(
            key=lambda v: (v.definition_id.code or '', v.version, v.id)
        )
        created = self.env['workflow.engine.execution']
        for version in versions:
            version_triggers = triggers.filtered(lambda t: t.version_id == version)
            if not self._trigger_matches(version_triggers, record=record, payload=payload):
                continue
            execution = self.executions.create_execution(
                version,
                source_module=source_module,
                source_model=source_model,
                event_code=event_code,
                record=record,
                payload=payload,
            )
            self.executions.start(execution)
            created |= execution
        return {
            'ok': True,
            'execution_ids': created.ids,
            'executions': created,
            'count': len(created),
        }

    def _trigger_matches(self, triggers, record=None, payload=None):
        """Apply optional domain_json filters when present; otherwise match."""
        for trigger in triggers:
            domain = trigger.domain_json
            if not domain:
                return True
            if isinstance(domain, dict):
                # Simple equality filters against payload / record fields
                for key, expected in domain.items():
                    actual = None
                    if payload and key in payload:
                        actual = payload.get(key)
                    elif record is not None and hasattr(record, key):
                        actual = getattr(record, key)
                        if hasattr(actual, 'id'):
                            actual = actual.id
                    if str(actual) != str(expected):
                        break
                else:
                    return True
            elif isinstance(domain, list):
                # Only allow empty domain list as match; non-empty lists require ORM search
                # against the record model without eval.
                if not domain:
                    return True
                if record is None:
                    continue
                Model = self.env[record._name]
                found = Model.search([('id', '=', record.id)] + domain, limit=1)
                if found:
                    return True
        return False
