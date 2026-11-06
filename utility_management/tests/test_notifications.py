# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.addons.mail.models.mail_template import MailTemplate
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.alert_service import AlertService
from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.notification_service import NotificationService
from odoo.addons.utility_management.services.report_service import ReportService


@tagged('post_install', '-at_install', 'utility_domain')
class TestAlertNotificationAudit(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.other_company = self.env['res.company'].create({'name': 'Notification Other Company'})
        self.recipient = self.env['res.users'].create({
            'name': 'Alert Mail Recipient',
            'login': 'utility_alert_mail_recipient',
            'email': 'alert.recipient@example.com',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.silent = self.env['res.users'].create({
            'name': 'Alert Mail Silent',
            'login': 'utility_alert_mail_silent',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.foreign = self.env['res.users'].create({
            'name': 'Alert Mail Foreign',
            'login': 'utility_alert_mail_foreign',
            'email': 'foreign.recipient@example.com',
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [manager_group.id])],
        })

    def _settings(self, company, enabled):
        model = self.env['utility.management.config'].sudo().with_context(
            utility_config_service=True,
        )
        config = model.search([('company_id', '=', company.id)], limit=1)
        if config:
            config.write({'mail_notifications': enabled})
            return config
        return model.create({
            'company_id': company.id,
            'mail_notifications': enabled,
        })

    def _meter(self, code):
        return MeterService(self.env).create({
            'name': code,
            'meter_code': code,
            'utility_type': 'electricity',
            'meter_role': 'consumption',
            'reading_mode': 'cumulative',
            'protocol': 'manual',
            'property_ref': 'P1',
            'site_ref': 'S1',
            'department_ref': 'D1',
        })

    def _offline_alert(self, code, user):
        meter = self._meter(code)
        AlertService(self.env).save_rule({
            'name': 'Offline %s' % code,
            'rule_type': 'meter_offline',
            'severity': 'critical',
            'meter_id': meter['id'],
            'escalate_to_id': user.id,
            'escalation_minutes': 30,
            'utility_type': 'electricity',
            'property_ref': 'P1',
        })
        MeterService(self.env).set_status(meter['id'], 'offline', health='failed')
        alert = self.env['utility.management.alert'].search([
            ('meter_id', '=', meter['id']),
            ('alert_type', '=', 'meter_offline'),
        ])
        self.assertEqual(len(alert), 1)
        return alert

    def _notes(self, record):
        return self.env['utility.management.audit.event'].sudo().search([
            ('model_name', '=', record._name),
            ('res_id', '=', record.id),
            ('summary', 'ilike', 'Notification'),
        ])

    def _status(self, notes, status):
        return notes.filtered(lambda note: (note.data_after or {}).get('notification_status') == status)

    def _blob(self, notes):
        return json.dumps([{
            'summary': note.summary,
            'before': note.data_before,
            'after': note.data_after,
            'outcome': note.outcome,
        } for note in notes], default=str)

    def test_alert_email_uses_template_and_audits_success(self):
        self._settings(self.env.company, True)
        template = self.env.ref('utility_management.mail_template_utility_alert')
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            alert = self._offline_alert('M-MAIL', self.recipient)
        self.assertEqual(alert.state, 'new')
        self.assertEqual(alert.severity, 'critical')
        mocked.assert_called_once()
        called = mocked.call_args.args[0]
        self.assertEqual(called.id, template.id)
        self.assertEqual(
            mocked.call_args.kwargs['email_values']['email_to'],
            'alert.recipient@example.com',
        )
        self.assertFalse(mocked.call_args.kwargs['force_send'])
        notes = self._notes(alert)
        sent = self._status(notes, 'sent')
        attempted = self._status(notes, 'attempted')
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent.outcome, 'success')
        self.assertTrue(sent.data_after.get('attempted'))
        self.assertEqual(sent.data_after.get('template'), 'utility_management.mail_template_utility_alert')
        self.assertEqual(sent.data_after.get('recipient_count'), 1)
        self.assertEqual(len(attempted), 1)
        self.assertTrue(attempted.data_after.get('attempted'))
        blob = self._blob(notes)
        self.assertNotIn('alert.recipient@example.com', blob)
        self.assertNotIn('body_html', blob)
        self.assertNotIn('<p>', blob)
        self.assertNotIn('Utility alert', blob)

    def test_disabled_notifications_skip_email_and_audit(self):
        self._settings(self.env.company, False)
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            alert = self._offline_alert('M-OFFMAIL', self.recipient)
        mocked.assert_not_called()
        notes = self._notes(alert)
        skipped = self._status(notes, 'skipped')
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped.data_after.get('reason'), 'notifications_disabled')
        self.assertFalse(skipped.data_after.get('attempted'))
        self.assertNotEqual(skipped.outcome, 'success')
        self.assertFalse(self._status(notes, 'sent'))

    def test_missing_recipient_skips_email_and_audits(self):
        self._settings(self.env.company, True)
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            alert = self._offline_alert('M-NOMAIL', self.silent)
        mocked.assert_not_called()
        notes = self._notes(alert)
        skipped = self._status(notes, 'skipped')
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped.data_after.get('reason'), 'recipient_unavailable')
        self.assertFalse(skipped.data_after.get('attempted'))
        self.assertNotEqual(skipped.outcome, 'success')

    def test_email_failure_is_audited_and_alert_remains(self):
        self._settings(self.env.company, True)
        with patch.object(
            MailTemplate, 'send_mail', autospec=True, side_effect=Exception('delivery failed'),
        ):
            alert = self._offline_alert('M-FAILMAIL', self.recipient)
        self.assertTrue(alert.exists())
        self.assertEqual(alert.state, 'new')
        self.assertTrue(alert.rule_id)
        self.assertEqual(alert.severity, 'critical')
        notes = self._notes(alert)
        failed = self._status(notes, 'failed')
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed.outcome, 'denied')
        self.assertNotEqual(failed.outcome, 'success')
        self.assertTrue(failed.data_after.get('attempted'))
        self.assertEqual(failed.data_after.get('reason'), 'delivery failed')
        self.assertFalse(self._status(notes, 'sent'))
        blob = self._blob(notes)
        self.assertNotIn('alert.recipient@example.com', blob)
        self.assertNotIn('<p>', blob)
        self.assertNotIn('body_html', blob)

    def test_scheduled_report_email_still_uses_report_template(self):
        self._settings(self.env.company, True)
        definition = ReportService(self.env).save_definition({
            'name': 'Scheduled electricity',
            'report_type': 'electricity_consumption',
            'schedule': 'daily',
            'recipient_user_ids': [(6, 0, [self.recipient.id])],
        })
        report_template = self.env.ref('utility_management.mail_template_utility_report')
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            ReportService(self.env).send_due()
        self.assertTrue(mocked.called)
        templates = {call.args[0].id for call in mocked.call_args_list}
        self.assertIn(report_template.id, templates)
        self.assertNotIn(self.env.ref('utility_management.mail_template_utility_alert').id, templates)
        run = self.env['utility.management.report.run'].search([
            ('definition_id', '=', definition['id']),
        ], limit=1)
        self.assertEqual(run.execution_state, 'completed')
        sent = self._status(self._notes(run), 'sent')
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent.outcome, 'success')
        self.assertEqual(sent.data_after.get('template'), 'utility_management.mail_template_utility_report')

    def test_notification_respects_company(self):
        self._settings(self.other_company, True)
        self._settings(self.env.company, False)
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            untouched = self._offline_alert('M-COOFF', self.recipient)
        mocked.assert_not_called()
        self.assertEqual(
            self._status(self._notes(untouched), 'skipped').data_after.get('reason'),
            'notifications_disabled',
        )
        self._settings(self.env.company, True)
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            foreign_alert = self._offline_alert('M-COFOR', self.foreign)
        mocked.assert_not_called()
        skipped = self._status(self._notes(foreign_alert), 'skipped')
        self.assertEqual(skipped.data_after.get('reason'), 'recipient_unavailable')
        blob = self._blob(self._notes(foreign_alert))
        self.assertNotIn('foreign.recipient@example.com', blob)
