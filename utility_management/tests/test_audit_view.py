# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.audit_service import AuditService
from odoo.addons.utility_management.services.notification_service import NotificationService
from odoo.addons.utility_management.services.report_service import ReportService


@tagged('post_install', '-at_install', 'utility_domain')
class TestAuditView(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.manager = self.env['res.users'].create({
            'name': 'Audit Facility Manager',
            'login': 'utility_audit_manager',
            'groups_id': [(6, 0, [manager_group.id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        self.staff = self.env['res.users'].create({
            'name': 'Audit Utility Staff',
            'login': 'utility_audit_staff',
            'groups_id': [(6, 0, [staff_group.id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        self.other_company = self.env['res.company'].create({'name': 'Audit Other Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'Audit Other Manager',
            'login': 'utility_audit_other_manager',
            'groups_id': [(6, 0, [manager_group.id])],
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
        })

    def _config(self, company):
        model = self.env['utility.management.config'].sudo().with_context(utility_config_service=True)
        found = model.search([('company_id', '=', company.id)], limit=1)
        if found:
            return found
        return model.create({'company_id': company.id})

    def _log(self, user, event_type, outcome, summary, company=None, before=None, after=None):
        company = company or user.company_id
        return AuditService(self.env(user=user)).log(
            event_type,
            self._config(self.env.company),
            outcome,
            summary,
            before=before,
            after=after,
            company=company,
        )

    def _api(self, user):
        return self.env['utility.management.ui.api'].with_user(user)

    def test_manager_lists_audit_events(self):
        event = self._log(self.manager, 'config_change', 'success', 'AUDV-LIST')
        listed = self._api(self.manager).list_audit_events({
            'limit': 20,
            'offset': 0,
            'search': 'AUDV-LIST',
        })
        self.assertEqual(listed['total_count'], 1)
        self.assertEqual(listed['limit'], 20)
        self.assertEqual(listed['offset'], 0)
        row = listed['rows'][0]
        self.assertEqual(row['id'], event.id)
        self.assertEqual(row['event_type'], 'config_change')
        self.assertEqual(row['model_name'], 'utility.management.config')
        self.assertEqual(row['user_id'], self.manager.id)
        self.assertEqual(row['user_name'], 'Audit Facility Manager')
        self.assertEqual(row['company_id'], self.env.company.id)
        self.assertEqual(row['outcome'], 'success')
        self.assertEqual(row['summary'], 'AUDV-LIST')
        self.assertTrue(row['occurred_at'])
        self.assertNotIn('data_before', row)
        self.assertNotIn('data_after', row)
        self.assertNotIn('@', json.dumps(row))

    def test_manager_paginates_audit_events(self):
        created = []
        for index in range(5):
            created.append(self._log(self.manager, 'config_change', 'success', 'AUDVPAGE-%s' % index))
        api = self._api(self.manager)
        first = api.list_audit_events({'limit': 2, 'offset': 0, 'search': 'AUDVPAGE-'})
        second = api.list_audit_events({'limit': 2, 'offset': 2, 'search': 'AUDVPAGE-'})
        self.assertEqual(first['total_count'], 5)
        self.assertEqual(second['total_count'], 5)
        self.assertEqual(len(first['rows']), 2)
        self.assertEqual(len(second['rows']), 2)
        self.assertEqual(first['limit'], 2)
        self.assertEqual(first['offset'], 0)
        self.assertEqual(second['offset'], 2)
        self.assertEqual(first['rows'][0]['id'], created[-1].id)
        self.assertEqual(second['rows'][0]['id'], created[-3].id)
        self.assertEqual(len({row['id'] for row in first['rows'] + second['rows']}), 4)

    def test_manager_filters_audit_events(self):
        kept = self._log(self.manager, 'leak_change', 'denied', 'AUDVFILT-KEEP')
        self._log(self.manager, 'meter_change', 'success', 'AUDVFILT-OTHER')
        admin_event = AuditService(self.env).log(
            'leak_change', self._config(self.env.company), 'denied', 'AUDVFILT-ADMIN',
        )
        api = self._api(self.manager)
        today = fields.Date.to_string(fields.Date.context_today(self.manager))
        tomorrow = fields.Date.to_string(fields.Date.context_today(self.manager) + timedelta(days=1))
        typed = api.list_audit_events({
            'limit': 20, 'offset': 0, 'event_type': 'leak_change', 'search': 'AUDVFILT-',
        })
        self.assertGreaterEqual(typed['total_count'], 2)
        self.assertTrue(all(row['event_type'] == 'leak_change' for row in typed['rows']))
        outcome = api.list_audit_events({
            'limit': 20, 'offset': 0, 'outcome': 'denied', 'search': 'AUDVFILT-KEEP',
        })
        self.assertEqual(outcome['total_count'], 1)
        self.assertEqual(outcome['rows'][0]['id'], kept.id)
        user_rows = api.list_audit_events({
            'limit': 20, 'offset': 0, 'user_id': self.manager.id, 'search': 'AUDVFILT-',
        })
        self.assertTrue(user_rows['rows'])
        self.assertTrue(all(row['user_id'] == self.manager.id for row in user_rows['rows']))
        self.assertFalse(any(row['id'] == admin_event.id for row in user_rows['rows']))
        model_rows = api.list_audit_events({
            'limit': 20,
            'offset': 0,
            'model_name': 'utility.management.config',
            'search': 'AUDVFILT-KEEP',
        })
        self.assertEqual(model_rows['total_count'], 1)
        dated = api.list_audit_events({
            'limit': 20,
            'offset': 0,
            'date_from': today,
            'date_to': today,
            'search': 'AUDVFILT-KEEP',
        })
        self.assertEqual(dated['total_count'], 1)
        future = api.list_audit_events({
            'limit': 20, 'offset': 0, 'date_from': tomorrow, 'search': 'AUDVFILT-KEEP',
        })
        self.assertEqual(future['total_count'], 0)
        by_ref = api.list_audit_events({
            'limit': 50,
            'offset': 0,
            'search': str(kept.res_id),
            'event_type': 'leak_change',
        })
        self.assertTrue(any(row['id'] == kept.id for row in by_ref['rows']))

    def test_manager_opens_audit_details(self):
        event = self._log(
            self.manager, 'reading_correction', 'success', 'AUDV-DETAIL',
            before={'reason': 'closed'},
            after={'reason': 'opened', 'threshold': 3},
        )
        detail = self._api(self.manager).get_audit_event(event.id)
        self.assertEqual(detail['id'], event.id)
        self.assertEqual(detail['summary'], 'AUDV-DETAIL')
        self.assertEqual(detail['res_id'], event.res_id)
        self.assertEqual(detail['data_before']['reason'], 'closed')
        self.assertEqual(detail['data_after']['reason'], 'opened')
        self.assertEqual(detail['data_after']['threshold'], 3)
        self.assertNotIn('email', json.dumps(detail))

    def test_staff_cannot_list_audit_events(self):
        self._log(self.staff, 'config_change', 'success', 'AUDV-STAFF-LIST')
        self.assertFalse(self.env['utility.management.audit.event'].with_user(self.staff).search([
            ('summary', '=', 'AUDV-STAFF-LIST'),
        ]))
        with self.assertRaises(AccessError):
            self._api(self.staff).list_audit_events({'limit': 5, 'offset': 0})

    def test_staff_cannot_open_audit_details(self):
        event = self._log(self.manager, 'config_change', 'success', 'AUDV-STAFF-DETAIL')
        with self.assertRaises(AccessError):
            self._api(self.staff).get_audit_event(event.id)

    def test_audit_list_is_company_isolated(self):
        main = self._log(self.manager, 'config_change', 'success', 'AUDV-MAIN')
        foreign = self._log(
            self.other_manager, 'config_change', 'success', 'AUDV-FOREIGN',
            company=self.other_company,
        )
        main_rows = self._api(self.manager).list_audit_events({
            'limit': 20, 'offset': 0, 'search': 'AUDV-',
        })
        foreign_rows = self._api(self.other_manager).list_audit_events({
            'limit': 20, 'offset': 0, 'search': 'AUDV-',
        })
        self.assertTrue(any(row['id'] == main.id for row in main_rows['rows']))
        self.assertFalse(any(row['id'] == foreign.id for row in main_rows['rows']))
        self.assertTrue(any(row['id'] == foreign.id for row in foreign_rows['rows']))
        self.assertFalse(any(row['id'] == main.id for row in foreign_rows['rows']))
        with self.assertRaises(UserError):
            self._api(self.other_manager).get_audit_event(main.id)

    def test_audit_events_stay_append_only(self):
        event = self._log(self.manager, 'meter_change', 'success', 'AUDV-APPEND')
        with self.assertRaises(UserError):
            event.with_user(self.manager).write({'summary': 'changed'})
        with self.assertRaises(UserError):
            event.with_user(self.manager).unlink()
        self.assertEqual(event.summary, 'AUDV-APPEND')
        self.assertTrue(event.exists())

    def test_audit_records_cannot_be_deleted_through_ui_api(self):
        event = self._log(self.manager, 'config_change', 'success', 'AUDV-NODELETE')
        api = self._api(self.manager)
        self.assertFalse(hasattr(api, 'unlink_audit_event'))
        self.assertFalse(hasattr(api, 'delete_audit_event'))
        self.assertFalse(hasattr(api, 'write_audit_event'))
        before = api.list_audit_events({'limit': 20, 'offset': 0, 'search': 'AUDV-NODELETE'})
        detail = api.get_audit_event(event.id)
        after = api.list_audit_events({'limit': 20, 'offset': 0, 'search': 'AUDV-NODELETE'})
        self.assertEqual(detail['id'], event.id)
        self.assertEqual(before['total_count'], after['total_count'])
        self.assertEqual(after['total_count'], 1)
        with self.assertRaises(UserError):
            self.env['utility.management.audit.event'].with_user(self.manager).browse(event.id).unlink()

    def test_audit_view_hides_notification_secrets(self):
        event = self._log(
            self.manager, 'alert_change', 'denied', 'Notification sent.',
            after={
                'notification_status': 'sent',
                'recipient_count': 1,
                'template': 'utility_management.mail_template_utility_alert',
                'reason': 'checked',
                'email': 'secret.person@example.com',
                'email_to': 'secret.person@example.com',
                'body_html': '<p>secret body</p>',
                'subject': 'Hidden subject line',
                'password': 'hidden-secret',
                'note': 'reach secret.person@example.com now',
            },
        )
        self.assertIn('email', event.data_after)
        detail = self._api(self.manager).get_audit_event(event.id)
        blob = json.dumps(detail)
        self.assertNotIn('secret.person@example.com', blob)
        self.assertNotIn('secret body', blob)
        self.assertNotIn('Hidden subject', blob)
        self.assertNotIn('hidden-secret', blob)
        self.assertNotIn('<p>', blob)
        self.assertEqual(detail['data_after']['notification_status'], 'sent')
        self.assertEqual(detail['data_after']['recipient_count'], 1)
        self.assertEqual(detail['data_after']['template'], 'utility_management.mail_template_utility_alert')
        self.assertEqual(detail['data_after']['reason'], 'checked')
        self.assertEqual(detail['data_after']['note'], '[redacted]')
        self.assertNotIn('email', detail['data_after'])
        self.assertNotIn('body_html', detail['data_after'])
        self.assertNotIn('subject', detail['data_after'])
        self.assertNotIn('password', detail['data_after'])
        listed = self._api(self.manager).list_audit_events({
            'limit': 5, 'offset': 0, 'search': 'Notification sent.',
        })
        self.assertNotIn('secret.person@example.com', json.dumps(listed))

    def test_notification_audit_events_stay_visible(self):
        alert = self.env['utility.management.alert'].with_context(utility_alert_service=True).create({
            'name': 'Audit view alert',
            'alert_type': 'threshold',
            'severity': 'medium',
            'state': 'new',
            'triggered_at': fields.Datetime.now(),
            'company_id': self.env.company.id,
            'property_ref': 'P1',
            'site_ref': 'S1',
            'department_ref': 'D1',
            'observed_value': 1,
        })
        NotificationService(self.env(user=self.manager)).notify_record(
            alert, self.env['res.users'], 'Audit notice',
        )
        listed = self._api(self.manager).list_audit_events({
            'limit': 20,
            'offset': 0,
            'event_type': 'alert_change',
            'search': 'Notification skipped.',
        })
        self.assertEqual(listed['total_count'], 1)
        detail = self._api(self.manager).get_audit_event(listed['rows'][0]['id'])
        self.assertEqual(detail['outcome'], 'denied')
        self.assertEqual(detail['data_after']['notification_status'], 'skipped')
        self.assertEqual(detail['data_after']['reason'], 'notifications_disabled')
        self.assertNotIn('@', json.dumps(detail))

    def test_report_audit_events_stay_visible(self):
        service = ReportService(self.env(user=self.manager))
        definition = service.save_definition({
            'name': 'Audit View Report',
            'report_type': 'utility_performance',
            'grouping': 'day',
            'comparison': 'none',
            'schedule': 'none',
        })
        service.run(definition['id'], 'csv')
        listed = self._api(self.manager).list_audit_events({
            'limit': 20, 'offset': 0, 'event_type': 'report_execution',
        })
        self.assertGreaterEqual(listed['total_count'], 1)
        detail = self._api(self.manager).get_audit_event(listed['rows'][0]['id'])
        self.assertEqual(detail['event_type'], 'report_execution')
        self.assertIn(detail['data_after'].get('execution_state'), ('completed', 'failed'))
        self.assertNotIn('@', json.dumps(detail))
        self.assertNotIn('body_html', detail['data_after'])

    def test_denied_access_audit_events_stay_visible(self):
        try:
            self._api(self.staff).list_audit_events({'limit': 5, 'offset': 0})
        except AccessError:
            pass
        else:
            self.fail('Utility Staff should not list audit events.')
        listed = self._api(self.manager).list_audit_events({
            'limit': 20, 'offset': 0, 'event_type': 'access_denied', 'outcome': 'denied',
        })
        match = [
            row for row in listed['rows']
            if row['summary'] == 'Only a Facility Manager can review the audit log.'
        ]
        self.assertTrue(match)
        detail = self._api(self.manager).get_audit_event(match[0]['id'])
        self.assertEqual(detail['event_type'], 'access_denied')
        self.assertEqual(detail['outcome'], 'denied')
        self.assertNotIn('@', json.dumps(detail))

    def test_phase5_list_contracts_remain(self):
        api = self.env['utility.management.ui.api']
        self.assertIsInstance(api.list_alerts({}), list)
        self.assertIsInstance(api.list_leaks({}), list)
        self.assertIsInstance(api.list_readings({}), list)
        paged = api.list_alerts({'limit': 1, 'offset': 0})
        self.assertEqual(sorted(paged), ['limit', 'offset', 'rows', 'total_count'])
        self.assertIsInstance(paged['rows'], list)
        runs = ReportService(self.env).list_runs({})
        self.assertIsInstance(runs, list)
        paged_runs = ReportService(self.env).list_runs({'limit': 1, 'offset': 0})
        self.assertEqual(sorted(paged_runs), ['limit', 'offset', 'rows', 'total_count'])
