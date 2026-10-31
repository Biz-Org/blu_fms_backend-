# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import ValidationError

from .audit_service import WorkflowAuditService

ALLOWED_OPERATORS = frozenset({'=', '!=', 'in', '<', '<=', '>', '>='})
ALLOWED_CRITERIA = frozenset({'department', 'role', 'value', 'property', 'site', 'module'})
ALLOWED_RULE_TYPES = frozenset({'approval_routing', 'assignment', 'branch'})


class WorkflowRuleService:
    """Safe conditional rule evaluation without eval/exec."""

    def __init__(self, env):
        self.env = env

    def evaluate(self, rule, context=None):
        context = context or {}
        if not rule or not rule.active:
            return False
        if rule.rule_type not in ALLOWED_RULE_TYPES:
            raise ValidationError('Unsupported conditional rule type: %s' % rule.rule_type)
        if rule.operator not in ALLOWED_OPERATORS:
            raise ValidationError('Unsupported conditional operator: %s' % rule.operator)
        if rule.criterion not in ALLOWED_CRITERIA:
            raise ValidationError('Unsupported conditional criterion: %s' % rule.criterion)
        now = fields.Datetime.now()
        if rule.date_from and now < rule.date_from:
            return False
        if rule.date_to and now > rule.date_to:
            return False
        left = self._resolve_criterion(rule.criterion, context)
        return self._compare(left, rule.operator, rule.value)

    def find_matching(self, rule_type, context=None, definition=None, version=None):
        domain = [('active', '=', True), ('rule_type', '=', rule_type)]
        if definition:
            domain.append('|')
            domain.append(('definition_id', '=', False))
            domain.append(('definition_id', '=', definition.id))
        if version:
            domain.append('|')
            domain.append(('version_id', '=', False))
            domain.append(('version_id', '=', version.id))
        rules = self.env['workflow.engine.condition.rule'].search(domain, order='priority, id')
        matches = self.env['workflow.engine.condition.rule']
        for rule in rules:
            if self.evaluate(rule, context=context):
                matches |= rule
        return matches

    def first_match(self, rule_type, context=None, definition=None, version=None):
        matches = self.find_matching(
            rule_type, context=context, definition=definition, version=version,
        )
        return matches[:1]

    def _resolve_criterion(self, criterion, context):
        payload = context.get('payload') or {}
        if not isinstance(payload, dict):
            payload = {}
        mapping = {
            'department': context.get('department') or payload.get('department'),
            'role': context.get('role') or payload.get('role'),
            'value': context.get('value') if 'value' in context else payload.get('value'),
            'property': context.get('property') or payload.get('property') or payload.get('property_ref'),
            'site': context.get('site') or payload.get('site') or payload.get('site_ref'),
            'module': context.get('module') or payload.get('module') or context.get('source_module'),
        }
        return mapping.get(criterion)

    def _compare(self, left, operator, right):
        if operator == 'in':
            options = [part.strip() for part in str(right).split(',') if part.strip()]
            return str(left) in options if left is not None else False
        if left is None:
            return False
        if operator in ('<', '<=', '>', '>='):
            try:
                left_num = float(left)
                right_num = float(right)
            except (TypeError, ValueError):
                return False
            if operator == '<':
                return left_num < right_num
            if operator == '<=':
                return left_num <= right_num
            if operator == '>':
                return left_num > right_num
            return left_num >= right_num
        left_s = str(left)
        right_s = str(right)
        if operator == '=':
            return left_s == right_s
        if operator == '!=':
            return left_s != right_s
        raise ValidationError('Unsupported conditional operator: %s' % operator)

    def build_context(self, execution=None, payload=None, source_module=None):
        payload = payload if payload is not None else (
            execution.payload_json if execution else {}
        ) or {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            'payload': payload,
            'source_module': source_module or (execution.source_module if execution else False),
            'module': source_module or (execution.source_module if execution else False)
                      or payload.get('module'),
            'department': payload.get('department'),
            'role': payload.get('role'),
            'value': payload.get('value'),
            'property': payload.get('property') or payload.get('property_ref'),
            'site': payload.get('site') or payload.get('site_ref')
                    or (execution.site_ref if execution else False),
        }
