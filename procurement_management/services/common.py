# -*- coding: utf-8 -*-
"""Shared server-side helpers. Not an Odoo model."""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.modules import module as odoo_module

STATE_CTX = 'pm_state_write'
AUDIT_CTX = 'pm_audit_system'
DECISION_CTX = 'pm_decision_system'
REQUEST_CTX = 'pm_request_system'
SELF_APPROVAL_PARAM = 'procurement_management.self_approval'


def normalize(value):
    return (value or '').strip().casefold()


def has_group(env, xml_id):
    return env.user.has_group('procurement_management.%s' % xml_id)


def ensure_group(env, xml_id, message):
    if not has_group(env, xml_id):
        audit_denied(env, env.company, 'modified', message)
        raise AccessError(message)


def set_state(record, state):
    record.with_context(**{STATE_CTX: True}).write({'state': state})


def guard_state(record, vals):
    if 'state' in vals and not record.env.context.get(STATE_CTX):
        raise UserError('Status changes must use a procurement action.')


def audit(env, company, action, status='success', model='', reference='',
          before='', after='', detail='', user=None):
    return env['procurement.management.audit.event'].sudo().with_context(
        **{AUDIT_CTX: True}
    ).create({
        'user_id': (user or env.user).id,
        'company_id': company.id if company else env.company.id,
        'action': action,
        'status': status,
        'res_model': model or '',
        'reference': reference or '',
        'before_value': before or '',
        'after_value': after or '',
        'detail': detail or '',
    })


def audit_record(record, action, status='success', before='', after='', detail=''):
    company = record.company_id if 'company_id' in record._fields else record.env.company
    reference = record.display_name if 'display_name' in record else str(record.id)
    return audit(
        record.env,
        company,
        action,
        status=status,
        model=record._name,
        reference=reference,
        before=before,
        after=after,
        detail=detail,
    )


def audit_denied(env, company, action, detail, model='', reference=''):
    """Record a denied attempt.

    During tests the row stays in the current transaction so it rolls back
    with the test. Outside tests it is committed on a separate cursor so a
    raised error does not erase it.
    """
    values = {
        'user_id': env.user.id,
        'company_id': company.id if company else env.company.id,
        'action': action,
        'status': 'denied',
        'res_model': model or '',
        'reference': reference or '',
        'detail': detail or '',
    }
    if odoo_module.current_test or env.registry.in_test_mode():
        return env['procurement.management.audit.event'].sudo().with_context(
            **{AUDIT_CTX: True}
        ).create(values)
    with env.registry.cursor() as cr:
        denied_env = env(cr=cr)
        row = denied_env['procurement.management.audit.event'].sudo().with_context(
            **{AUDIT_CTX: True}
        ).create(values)
        cr.commit()
        return row


def self_approval_policy(env):
    """OPEN until the owner sets procurement_management.self_approval to A or B."""
    return (env['ir.config_parameter'].sudo().get_param(SELF_APPROVAL_PARAM) or '').strip()


def assert_self_approval(env, requester, actor, company, reference):
    policy = self_approval_policy(env)
    if policy == 'A' and requester and requester == actor:
        audit_denied(
            env, company, 'approved',
            'Self-approval is blocked by policy A.',
            model='procurement.management.approval.request',
            reference=reference,
        )
        raise AccessError('You cannot approve a request you submitted.')
    if policy not in ('', 'A', 'B'):
        raise UserError('Unknown self-approval policy. Expected A, B, or unset.')


def today(env):
    return fields.Date.context_today(env.user)
