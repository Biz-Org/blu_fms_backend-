# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError

CLOSED_STATES = ('resolved', 'closed')
ACTIVE_STATES = ('open', 'acknowledged', 'investigating')
ESCALATABLE_STATES = ACTIVE_STATES
ALERT_ACTIONS = {
    'acknowledge', 'investigate', 'assign', 'escalate',
    'resolve', 'close', 'add_note', 'reopen', 'to_incident',
}
EMERGENCY_ACTIONS = {
    'acknowledge', 'escalate', 'resolve', 'handle_overdue', 'reopen',
}
INCIDENT_ACTIONS = {
    'create', 'acknowledge', 'investigate', 'assign', 'escalate',
    'resolve', 'close', 'add_note', 'reopen',
}


def extra_values(extra):
    return extra if isinstance(extra, dict) else {}


def dt_string(value):
    if not value:
        return False
    return fields.Datetime.to_string(value)


def require_record(env, model, rec_id, label):
    if rec_id in (None, False, '', 0, '0'):
        raise UserError('%s not found.' % label)
    try:
        rec_id = int(rec_id)
    except (TypeError, ValueError) as err:
        raise UserError('%s not found.' % label) from err
    rec = env[model].browse(rec_id)
    if not rec.exists():
        raise UserError('%s not found.' % label)
    return rec


def require_user(env, user_id):
    user = require_record(env, 'res.users', user_id, 'Assignee')
    if not user.active:
        raise UserError('Assignee not found.')
    return user


def assert_company_access(user, company):
    if company and company not in user.company_ids:
        raise UserError('Assignee does not have access to this company.')


def is_manager(env):
    return env.su or env.user.has_group('command_center.group_cc_manager')


def is_admin(env):
    return env.su or env.user.has_group('command_center.group_cc_admin')


def assert_user_action(record):
    record._cc_require_user()


def assert_manager_action(record):
    record._cc_require_manager()


def assert_admin_action(record):
    record._cc_require_admin()


def assert_state(record, allowed, action):
    if record.state not in allowed:
        raise UserError('Action "%s" is not allowed from state "%s".' % (action, record.state or ''))


def lifecycle(record):
    return record.with_context(cc_lifecycle=True)


def now():
    return fields.Datetime.now()


def overdue_domain():
    return [
        ('response_deadline', '!=', False),
        ('response_deadline', '<', now()),
        ('state', 'not in', list(CLOSED_STATES)),
    ]


def is_overdue(alert):
    return bool(
        alert.response_deadline
        and alert.response_deadline < now()
        and alert.state not in CLOSED_STATES
    )


def assignable_users(env):
    group = env.ref('command_center.group_cc_user')
    users = env['res.users'].search([
        ('groups_id', 'in', [group.id]),
        ('company_ids', 'in', env.companies.ids),
        ('active', '=', True),
        ('id', '!=', env.ref('base.user_root').id),
    ], order='name, id')
    return [{'id': user.id, 'name': user.name} for user in users]


def site_rows(env, domain=None):
    sites = env['cc.site'].search(domain or [], order='name, id')
    return [{
        'id': site.id,
        'name': site.name,
        'code': site.code,
        'operational_status': site.operational_status,
        'company_id': site.company_id.id,
    } for site in sites]


def note_rows(notes):
    return [{
        'id': note.id,
        'body': note.body,
        'user_id': note.user_id.id,
        'user_name': note.user_id.name,
        'create_date': dt_string(note.create_date),
        'alert_id': note.alert_id.id or False,
        'incident_id': note.incident_id.id or False,
    } for note in notes]


def history_rows(history):
    return [{
        'id': rec.id,
        'alert_id': rec.alert_id.id,
        'rule_id': rec.rule_id.id or False,
        'level': rec.level or 0,
        'timestamp': dt_string(rec.timestamp),
        'user_id': rec.user_id.id or False,
        'group_id': rec.group_id.id or False,
        'result': rec.result or False,
        'actor_id': rec.actor_id.id or False,
        'note': rec.note or '',
    } for rec in history]
