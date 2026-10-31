# -*- coding: utf-8 -*-
"""Phase 4 alert, incident, emergency, and escalation service tests."""
import unittest
from datetime import timedelta

try:
    from odoo import fields
    from odoo.exceptions import AccessError, UserError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    AccessError = UserError = Exception
    fields = None

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'cc_services')
class TestCcServices(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.group_user = self.env.ref('command_center.group_cc_user')
        self.group_manager = self.env.ref('command_center.group_cc_manager')
        self.group_admin = self.env.ref('command_center.group_cc_admin')
        self.user = self._make_user('cc_p4_user', self.group_user)
        self.other = self._make_user('cc_p4_other', self.group_user)
        self.manager = self._make_user('cc_p4_manager', self.group_manager)
        self.admin = self._make_user('cc_p4_admin', self.group_admin)
        self.site = self.env['cc.site'].create({'code': 'P4-SITE', 'name': 'Phase 4 Site'})
        self.alert = self.env['cc.alert'].create({
            'alert_type': 'intrusion',
            'severity': 'high',
            'source': 'manual',
            'site_id': self.site.id,
        })
        self.Api = self.env['cc.ui.api']

    def _make_user(self, login, group):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, [group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _api(self, user):
        return self.Api.with_user(user)

    def test_alert_acknowledge_investigate_resolve_close_reopen(self):
        self._api(self.user).run_alert_action(self.alert.id, 'acknowledge')
        self.assertEqual(self.alert.state, 'acknowledged')
        self.assertEqual(self.alert.acknowledged_uid, self.user)
        self.assertTrue(self.alert.acknowledged_at)
        self._api(self.user).run_alert_action(self.alert.id, 'investigate')
        self.assertEqual(self.alert.state, 'investigating')
        self._api(self.manager).run_alert_action(self.alert.id, 'resolve', {'resolution_note': 'Cleared'})
        self.assertEqual(self.alert.state, 'resolved')
        self.assertEqual(self.alert.resolved_uid, self.manager)
        self.assertEqual(self.alert.resolution_note, 'Cleared')
        resolved_at = self.alert.resolved_at
        self._api(self.manager).run_alert_action(self.alert.id, 'close')
        self.assertEqual(self.alert.state, 'closed')
        self.assertTrue(self.alert.closed_at)
        self.assertEqual(self.alert.resolved_at, resolved_at)
        self._api(self.admin).run_alert_action(self.alert.id, 'reopen')
        self.assertEqual(self.alert.state, 'open')
        self.assertFalse(self.alert.acknowledged_uid)
        self.assertFalse(self.alert.acknowledged_at)
        self.assertFalse(self.alert.resolved_uid)
        self.assertFalse(self.alert.resolved_at)
        self.assertFalse(self.alert.closed_at)

    def test_alert_invalid_transitions(self):
        with self.assertRaises(UserError):
            self._api(self.manager).run_alert_action(self.alert.id, 'resolve')
        with self.assertRaises(UserError):
            self._api(self.manager).run_alert_action(self.alert.id, 'close')
        self._api(self.user).run_alert_action(self.alert.id, 'acknowledge')
        with self.assertRaises(UserError):
            self._api(self.user).run_alert_action(self.alert.id, 'acknowledge')
        with self.assertRaises(UserError):
            self._api(self.admin).run_alert_action(self.alert.id, 'reopen')

    def test_alert_assign_self_and_other_permission(self):
        self._api(self.user).run_alert_action(self.alert.id, 'assign')
        self.assertEqual(self.alert.user_id, self.user)
        with self.assertRaises(AccessError):
            self._api(self.user).run_alert_action(self.alert.id, 'assign', {'user_id': self.other.id})
        self._api(self.manager).run_alert_action(self.alert.id, 'assign', {'user_id': self.other.id})
        self.assertEqual(self.alert.user_id, self.other)

    def test_alert_to_incident_follows_workflow(self):
        with self.assertRaises(AccessError):
            self._api(self.user).run_alert_action(self.alert.id, 'to_incident')
        result = self._api(self.manager).run_alert_action(
            self.alert.id,
            'to_incident',
            {'summary': 'Promoted from alert', 'severity': 'high'},
        )
        self.alert.invalidate_recordset()
        self.assertTrue(self.alert.incident_id)
        self.assertEqual(self.alert.incident_id.summary, 'Promoted from alert')
        self.assertEqual(self.alert.incident_id.severity, 'high')
        self.assertEqual(result['alert']['incident_id'], self.alert.incident_id.id)

    def test_alert_escalate_creates_history_without_state_change(self):
        rule = self.env['cc.escalation.rule'].create({
            'name': 'Site rule',
            'level': 2,
            'delay_minutes': 5,
            'site_id': self.site.id,
            'user_id': self.manager.id,
        })
        state = self.alert.state
        self._api(self.manager).run_alert_action(self.alert.id, 'escalate', {'note': 'Need backup'})
        self.assertEqual(self.alert.state, state)
        history = self.env['cc.escalation.history'].search([('alert_id', '=', self.alert.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.rule_id, rule)
        self.assertEqual(history.result, 'triggered')
        self.assertEqual(history.actor_id, self.manager)
        self.assertEqual(self.alert.user_id, self.manager)
        with self.assertRaises(AccessError):
            self._api(self.user).run_alert_action(self.alert.id, 'escalate')

    def test_alert_unauthorized_actions(self):
        self._api(self.user).run_alert_action(self.alert.id, 'acknowledge')
        self._api(self.user).run_alert_action(self.alert.id, 'investigate')
        with self.assertRaises(AccessError):
            self._api(self.user).run_alert_action(self.alert.id, 'resolve')
        with self.assertRaises(AccessError):
            self._api(self.user).run_alert_action(self.alert.id, 'close')
        self._api(self.manager).run_alert_action(self.alert.id, 'resolve')
        with self.assertRaises(AccessError):
            self._api(self.manager).run_alert_action(self.alert.id, 'reopen')
        with self.assertRaises(UserError):
            self._api(self.manager).run_alert_action(self.alert.id, 'unknown')
        with self.assertRaises(UserError):
            self._api(self.manager).run_alert_action(0, 'acknowledge')

    def test_incident_lifecycle_and_permissions(self):
        with self.assertRaises(AccessError):
            self._api(self.user).run_incident_action(False, 'create', {
                'summary': 'Smoke',
                'severity': 'high',
                'site_id': self.site.id,
            })
        result = self._api(self.manager).run_incident_action(False, 'create', {
            'summary': 'Smoke in north hall',
            'severity': 'medium',
            'site_id': self.site.id,
        })
        incident = self.env['cc.incident'].browse(result['incident']['id'])
        self.assertEqual(incident.state, 'open')
        self.assertTrue(incident.opened_at)
        self.assertTrue(incident.name.startswith('CC-INC'))
        self._api(self.user).run_incident_action(incident.id, 'acknowledge')
        self.assertEqual(incident.state, 'acknowledged')
        self._api(self.user).run_incident_action(incident.id, 'investigate')
        self.assertEqual(incident.state, 'investigating')
        self._api(self.user).run_incident_action(incident.id, 'assign')
        self.assertEqual(incident.user_id, self.user)
        with self.assertRaises(AccessError):
            self._api(self.user).run_incident_action(incident.id, 'assign', {'user_id': self.other.id})
        self._api(self.manager).run_incident_action(incident.id, 'assign', {'user_id': self.other.id})
        self._api(self.manager).run_incident_action(incident.id, 'resolve', {'resolution': 'Ventilated'})
        self.assertEqual(incident.state, 'resolved')
        self.assertEqual(incident.resolution, 'Ventilated')
        self._api(self.manager).run_incident_action(incident.id, 'close')
        self.assertEqual(incident.state, 'closed')
        with self.assertRaises(AccessError):
            self._api(self.manager).run_incident_action(incident.id, 'reopen')
        self._api(self.admin).run_incident_action(incident.id, 'reopen')
        self.assertEqual(incident.state, 'open')
        self.assertFalse(incident.acknowledged_at)
        self.assertFalse(incident.resolved_at)
        self.assertFalse(incident.closed_at)
        with self.assertRaises(UserError):
            self._api(self.manager).run_incident_action(incident.id, 'resolve')

    def test_emergency_filter_actions_and_overdue(self):
        past = fields.Datetime.now() - timedelta(hours=1)
        emergency = self.env['cc.alert'].with_context(cc_lifecycle=True).create({
            'alert_type': 'fire',
            'severity': 'critical',
            'site_id': self.site.id,
            'is_emergency': True,
            'response_deadline': past,
        })
        self.env['cc.escalation.rule'].create({
            'name': 'Emergency rule',
            'level': 3,
            'delay_minutes': 0,
            'site_id': self.site.id,
            'user_id': self.admin.id,
        })
        data = self._api(self.user).get_emergency_data({})
        self.assertEqual(data['kpis']['total'], 1)
        self.assertTrue(all(item['is_emergency'] for item in data['alerts']))
        overdue = self._api(self.user).get_emergency_data({'overdue': True})
        self.assertEqual(overdue['kpis']['total'], 1)
        self._api(self.user).run_emergency_action(emergency.id, 'acknowledge')
        self.assertEqual(emergency.state, 'acknowledged')
        self._api(self.manager).run_emergency_action(emergency.id, 'escalate')
        self.assertEqual(emergency.state, 'acknowledged')
        self.assertTrue(emergency.history_ids)
        self._api(self.manager).run_emergency_action(emergency.id, 'handle_overdue')
        self.assertEqual(emergency.user_id, self.admin)
        self._api(self.manager).run_emergency_action(emergency.id, 'resolve')
        self.assertEqual(emergency.state, 'resolved')
        self._api(self.admin).run_emergency_action(emergency.id, 'reopen')
        self.assertEqual(emergency.state, 'open')
        with self.assertRaises(UserError):
            self._api(self.manager).run_emergency_action(self.alert.id, 'acknowledge')

    def test_escalation_rule_selection_and_company_isolation(self):
        other_company = self.env['res.company'].create({'name': 'P4 Other'})
        other_site = self.env['cc.site'].create({
            'code': 'P4-B',
            'company_id': other_company.id,
        })
        low = self.env['cc.escalation.rule'].create({
            'name': 'Global low',
            'level': 1,
            'delay_minutes': 10,
        })
        high = self.env['cc.escalation.rule'].create({
            'name': 'Global high',
            'level': 5,
            'delay_minutes': 1,
        })
        same_level_a = self.env['cc.escalation.rule'].create({
            'name': 'Tie A',
            'level': 4,
            'delay_minutes': 1,
        })
        self.env['cc.escalation.rule'].create({
            'name': 'Tie B',
            'level': 4,
            'delay_minutes': 1,
        })
        site_rule = self.env['cc.escalation.rule'].create({
            'name': 'Site first',
            'level': 1,
            'delay_minutes': 1,
            'site_id': self.site.id,
        })
        self.env['cc.escalation.rule'].create({
            'name': 'Other company',
            'level': 9,
            'delay_minutes': 1,
            'company_id': other_company.id,
            'site_id': other_site.id,
        })
        from odoo.addons.command_center.services.escalation_service import EscalationService
        service = EscalationService(self.env)
        selected = service.select_rule(self.alert)
        self.assertEqual(selected, site_rule)
        self.alert.site_id = False
        selected = service.select_rule(self.alert)
        self.assertEqual(selected, high)
        high.active = False
        selected = service.select_rule(self.alert)
        self.assertEqual(selected, same_level_a)
        other_alert = self.env['cc.alert'].create({
            'alert_type': 'ops',
            'company_id': other_company.id,
            'site_id': other_site.id,
        })
        selected = service.select_rule(other_alert)
        self.assertEqual(selected.company_id, other_company)
        self.assertNotEqual(selected.id, low.id)

    def test_notes_author_and_append_only(self):
        self._api(self.user).run_alert_action(self.alert.id, 'add_note', {'body': 'Camera 3 reviewed'})
        note = self.alert.note_ids
        self.assertEqual(len(note), 1)
        self.assertEqual(note.user_id, self.user)
        with self.assertRaises(UserError):
            note.with_user(self.admin).write({'body': 'changed'})
        with self.assertRaises(UserError):
            self._api(self.user).run_alert_action(self.alert.id, 'add_note', {'body': '   '})

    def test_manager_cannot_unlink_site(self):
        spare = self.env['cc.site'].create({'code': 'P4-UNLINK'})
        with self.assertRaises(AccessError):
            spare.with_user(self.manager).unlink()
        spare.with_user(self.admin).unlink()
        self.assertFalse(spare.exists())
