# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError

from .common import (
    ESCALATABLE_STATES,
    assert_manager_action,
    assert_state,
    extra_values,
    now,
    require_record,
)


class EscalationService:
    def __init__(self, env):
        self.env = env

    def create_rule(self, values):
        self.env['cc.escalation.rule']._cc_require_manager()
        vals = self._prepare_rule_vals(values or {})
        return self.env['cc.escalation.rule'].create(vals)

    def write_rule(self, rule_id, values):
        rule = require_record(self.env, 'cc.escalation.rule', rule_id, 'Escalation rule')
        rule._cc_require_manager()
        vals = self._prepare_rule_vals(values or {}, partial=True)
        rule.write(vals)
        return rule

    def unlink_rule(self, rule_id):
        rule = require_record(self.env, 'cc.escalation.rule', rule_id, 'Escalation rule')
        rule._cc_require_manager()
        rule.unlink()
        return True

    def _prepare_rule_vals(self, values, partial=False):
        vals = {}
        mapping = (
            'name', 'active', 'level', 'delay_minutes', 'mode',
            'user_id', 'group_id', 'company_id', 'site_id',
        )
        for key in mapping:
            if key in values:
                vals[key] = values[key]
        if not partial or 'level' in vals:
            level = vals.get('level', 1 if not partial else None)
            if level is not None and int(level) < 0:
                raise ValidationError('Escalation level must be greater than or equal to 0.')
            if level is not None:
                vals['level'] = int(level)
        if not partial or 'delay_minutes' in vals:
            delay = vals.get('delay_minutes', 0 if not partial else None)
            if delay is not None and int(delay) < 0:
                raise ValidationError('Escalation delay must be greater than or equal to 0.')
            if delay is not None:
                vals['delay_minutes'] = int(delay)
        if vals.get('site_id'):
            site = require_record(self.env, 'cc.site', vals['site_id'], 'Site')
            company_id = vals.get('company_id') or self.env.company.id
            if site.company_id.id != company_id:
                raise UserError('Escalation rule company must match the selected site company.')
        return vals

    def select_rule(self, alert, rule_id=None):
        if rule_id:
            rule = require_record(self.env, 'cc.escalation.rule', rule_id, 'Escalation rule')
            if not rule.active:
                raise UserError('Escalation rule is not active.')
            if rule.company_id != alert.company_id:
                raise UserError('Escalation rule company must match the alert company.')
            if rule.site_id and rule.site_id != alert.site_id:
                raise UserError('Escalation rule does not apply to this site.')
            return rule
        return self._match_rule(alert)

    def _match_rule(self, alert):
        base = [
            ('active', '=', True),
            ('company_id', '=', alert.company_id.id),
        ]
        site_rules = self.env['cc.escalation.rule'].browse()
        if alert.site_id:
            site_rules = self.env['cc.escalation.rule'].search(
                base + [('site_id', '=', alert.site_id.id)],
                order='level desc, id asc',
                limit=1,
            )
        if site_rules:
            return site_rules
        return self.env['cc.escalation.rule'].search(
            base + [('site_id', '=', False)],
            order='level desc, id asc',
            limit=1,
        )

    def create_history(self, alert, rule=None, extra=None, result='triggered'):
        values = extra_values(extra)
        rule = rule or self.env['cc.escalation.rule']
        level = values.get('level')
        if level in (None, False, ''):
            level = rule.level if rule else 0
        return self.env['cc.escalation.history'].sudo().create({
            'alert_id': alert.id,
            'rule_id': rule.id or False,
            'level': int(level or 0),
            'timestamp': now(),
            'user_id': rule.user_id.id if rule else False,
            'group_id': rule.group_id.id if rule else False,
            'result': result,
            'actor_id': self.env.uid,
            'note': values.get('note') or values.get('body') or '',
        })

    def escalate_alert(self, alert, extra=None):
        assert_manager_action(alert)
        assert_state(alert, ESCALATABLE_STATES, 'escalate')
        values = extra_values(extra)
        rule = self.select_rule(alert, values.get('rule_id'))
        if not rule:
            raise UserError('No applicable escalation rule.')
        history = self.create_history(alert, rule, values, result='triggered')
        if rule.user_id:
            alert.user_id = rule.user_id.id
        return history
