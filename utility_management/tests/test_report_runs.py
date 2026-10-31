# -*- coding: utf-8 -*-
import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.mail.models.mail_template import MailTemplate
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.reading_service import ReadingService
from odoo.addons.utility_management.services.report_service import ReportService


@tagged('post_install', '-at_install', 'utility_domain')
class TestReportRunSnapshot(TransactionCase):

    def setUp(self):
        super().setUp()
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.other_company = self.env['res.company'].create({'name': 'Report Snapshot Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'Report Snapshot Manager',
            'login': 'utility_report_snapshot_manager',
            'email': 'report.snapshot@example.com',
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [manager_group.id])],
        })
        self.recipient = self.env['res.users'].create({
            'name': 'Report Snapshot Recipient',
            'login': 'utility_report_snapshot_recipient',
            'email': 'report.recipient@example.com',
            'groups_id': [(6, 0, [self.env.ref('utility_management.group_utility_staff').id])],
        })

    def _settings(self, company, enabled):
        model = self.env['utility.management.config'].sudo().with_context(
            utility_config_service=True,
        )
        config = model.search([('company_id', '=', company.id)], limit=1)
        if config:
            config.write({'mail_notifications': enabled})
            return config
        return model.create({'company_id': company.id, 'mail_notifications': enabled})

    def _meter(self):
        return MeterService(self.env).create({
            'name': 'Snapshot Meter',
            'meter_code': 'M-SNAP',
            'utility_type': 'electricity',
            'meter_role': 'consumption',
            'reading_mode': 'interval',
            'protocol': 'manual',
            'property_ref': 'P1',
        })

    def _reading(self, meter_id, quantity, hours_ago):
        created = ReadingService(self.env).create_manual({
            'meter_id': meter_id,
            'observed_at': fields.Datetime.now() - timedelta(hours=hours_ago),
            'source': 'manual',
            'interval_quantity': quantity,
        })
        ReadingService(self.env).verify(created['reading_id'])
        return created

    def _definition(self, name, schedule='none', company_env=None, recipients=None):
        service = ReportService(company_env or self.env)
        values = {
            'name': name,
            'report_type': 'electricity_consumption',
            'schedule': schedule,
            'grouping': 'day',
        }
        if recipients:
            values['recipient_user_ids'] = [(6, 0, recipients)]
        return service.save_definition(values)

    def _runs(self, definition_id, state=None):
        domain = [('definition_id', '=', definition_id)]
        if state:
            domain.append(('execution_state', '=', state))
        return self.env['utility.management.report.run'].sudo().search(domain)

    def _fail(self, definition):
        return self.env['utility.management.report.run'].with_context(
            utility_report_service=True,
        ).create({
            'definition_id': definition['id'],
            'company_id': definition['company_id'],
            'execution_state': 'failed',
            'export_format': 'csv',
            'error_message': 'Scheduled export failed.',
            'started_at': fields.Datetime.now(),
            'finished_at': fields.Datetime.now(),
        })

    def _backdate(self, run, days):
        run.with_context(utility_report_service=True).write({
            'started_at': fields.Datetime.now() - timedelta(days=days),
            'finished_at': fields.Datetime.now() - timedelta(days=days),
        })

    def test_completed_run_keeps_its_snapshot(self):
        meter = self._meter()
        self._reading(meter['id'], 80, 3)
        definition = self._definition('Snapshot electricity')
        service = ReportService(self.env)
        csv_run = service.run(definition['id'], 'csv')
        stored = self.env['utility.management.report.run'].browse(csv_run['id'])
        self.assertEqual(csv_run['execution_state'], 'completed')
        self.assertEqual(csv_run['chart_state'], 'ready')
        self.assertEqual(stored.result_rows, [{
            'reading': stored.result_rows[0]['reading'],
            'meter': 'M-SNAP',
            'utility': 'electricity',
            'property_ref': 'P1',
            'site_ref': '',
            'consumption': 80.0,
            'demand_kw': 0.0,
            'flow_rate': 0.0,
            'pressure': 0.0,
            'status': 'verified',
        }])
        self.assertEqual(csv_run['chart'], [{'label': 'M-SNAP', 'value': 80.0}])
        attachment = self.env['ir.attachment'].browse(csv_run['attachment_id'])
        csv_text = base64.b64decode(attachment.datas).decode()
        self.assertIn('80.0', csv_text)
        self._reading(meter['id'], 40, 1)
        opened = service.run_dto(stored)
        self.assertEqual(opened['chart'], [{'label': 'M-SNAP', 'value': 80.0}])
        self.assertEqual(opened['chart_state'], 'ready')
        self.assertIn('80.0', base64.b64decode(attachment.datas).decode())
        self.assertNotIn('40.0', base64.b64decode(attachment.datas).decode())
        xlsx_run = service.run(definition['id'], 'xlsx')
        self.assertEqual(xlsx_run['execution_state'], 'completed')
        workbook = base64.b64decode(
            self.env['ir.attachment'].browse(xlsx_run['attachment_id']).datas
        )
        self.assertTrue(workbook.startswith(b'PK'))
        self.assertEqual(
            sorted(point['value'] for point in xlsx_run['chart']),
            [40.0, 80.0],
        )
        pdf_run = service.run(definition['id'], 'pdf')
        if pdf_run['execution_state'] == 'completed':
            pdf = base64.b64decode(
                self.env['ir.attachment'].browse(pdf_run['attachment_id']).datas
            )
            self.assertTrue(pdf.startswith(b'%PDF'))
            self.assertTrue(pdf_run['chart'])
        else:
            self.assertEqual(pdf_run['execution_state'], 'failed')
            self.assertTrue(pdf_run['error_message'])
            self.assertFalse(pdf_run['attachment_id'])
            self.assertEqual(pdf_run['chart'], [])
            self.assertFalse(pdf_run['chart_state'])
            failed = self.env['utility.management.report.run'].browse(pdf_run['id'])
            self.assertFalse(failed.result_rows)
        stored.with_context(utility_report_service=True).write({'result_rows': False})
        missing = service.run_dto(stored)
        self.assertEqual(missing['chart'], [])
        self.assertEqual(missing['chart_state'], 'unavailable')
        self.assertEqual(missing['execution_state'], 'completed')

    def test_failed_daily_run_retries_without_a_second_success(self):
        definition = self._definition('Daily schedule', 'daily')
        failed = self._fail(definition)
        service = ReportService(self.env)
        today = fields.Date.context_today(self.env.user)
        self.assertTrue(service._is_due(
            self.env['utility.management.report.definition'].browse(definition['id']),
            today,
        ))
        service.send_due()
        self.assertEqual(len(self._runs(definition['id'], 'failed')), 1)
        self.assertEqual(len(self._runs(definition['id'], 'completed')), 1)
        self.assertEqual(failed.execution_state, 'failed')
        self.assertTrue(failed.error_message)
        visible = service.list_runs()
        states = {
            row['id']: row['execution_state']
            for row in visible
            if row['definition_id'] == definition['id']
        }
        self.assertEqual(states[failed.id], 'failed')
        self.assertIn('completed', states.values())
        service.send_due()
        self.assertEqual(len(self._runs(definition['id'], 'completed')), 1)
        self.assertEqual(len(self._runs(definition['id'], 'failed')), 1)

    def test_weekly_and_monthly_windows_follow_the_last_success(self):
        service = ReportService(self.env)
        today = fields.Date.context_today(self.env.user)
        weekly = self._definition('Weekly schedule', 'weekly')
        weekly_record = self.env['utility.management.report.definition'].browse(weekly['id'])
        weekly_run = service.run(weekly['id'], 'csv')
        self._backdate(self.env['utility.management.report.run'].browse(weekly_run['id']), 8)
        self.assertTrue(service._is_due(weekly_record, today))
        service.send_due()
        self.assertEqual(len(self._runs(weekly['id'], 'completed')), 2)
        self.assertFalse(service._is_due(weekly_record, today))
        service.send_due()
        self.assertEqual(len(self._runs(weekly['id'], 'completed')), 2)
        recent_weekly = self._definition('Recent weekly', 'weekly')
        recent_run = service.run(recent_weekly['id'], 'csv')
        self._backdate(self.env['utility.management.report.run'].browse(recent_run['id']), 2)
        before = len(self._runs(recent_weekly['id'], 'completed'))
        self.assertFalse(service._is_due(
            self.env['utility.management.report.definition'].browse(recent_weekly['id']),
            today,
        ))
        service.send_due()
        self.assertEqual(len(self._runs(recent_weekly['id'], 'completed')), before)
        monthly = self._definition('Monthly schedule', 'monthly')
        monthly_record = self.env['utility.management.report.definition'].browse(monthly['id'])
        monthly_run = service.run(monthly['id'], 'csv')
        self._backdate(self.env['utility.management.report.run'].browse(monthly_run['id']), 30)
        self.assertTrue(service._is_due(monthly_record, today))
        service.send_due()
        self.assertEqual(len(self._runs(monthly['id'], 'completed')), 2)
        self.assertFalse(service._is_due(monthly_record, today))
        recent_monthly = self._definition('Recent monthly', 'monthly')
        recent_monthly_run = service.run(recent_monthly['id'], 'csv')
        self._backdate(
            self.env['utility.management.report.run'].browse(recent_monthly_run['id']),
            10,
        )
        before_monthly = len(self._runs(recent_monthly['id'], 'completed'))
        service.send_due()
        self.assertEqual(len(self._runs(recent_monthly['id'], 'completed')), before_monthly)

    def test_scheduled_report_email_still_sends_once_per_success(self):
        self._settings(self.env.company, True)
        definition = self._definition(
            'Mailed daily',
            'daily',
            recipients=[self.recipient.id],
        )
        template = self.env.ref('utility_management.mail_template_utility_report')
        with patch.object(MailTemplate, 'send_mail', autospec=True, return_value=1) as mocked:
            ReportService(self.env).send_due()
            ReportService(self.env).send_due()
        completed = self._runs(definition['id'], 'completed')
        self.assertEqual(len(completed), 1)
        calls = [
            call for call in mocked.call_args_list
            if call.args[0].id == template.id and call.args[1] == completed.id
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0].kwargs['email_values']['email_to'],
            'report.recipient@example.com',
        )

    def test_schedule_and_snapshot_stay_in_their_company(self):
        meter = self._meter()
        self._reading(meter['id'], 80, 2)
        main = self._definition('Main daily', 'daily')
        other = self._definition(
            'Other daily',
            'daily',
            company_env=self.env(user=self.other_manager),
        )
        self.assertEqual(other['company_id'], self.other_company.id)
        other_run = ReportService(self.env(user=self.other_manager)).run(other['id'], 'csv')
        self.assertEqual(other_run['company_id'], self.other_company.id)
        self.assertEqual(other_run['chart'], [])
        ReportService(self.env).send_due()
        self.assertEqual(len(self._runs(other['id'], 'completed')), 1)
        main_runs = self._runs(main['id'], 'completed')
        self.assertEqual(len(main_runs), 1)
        self.assertEqual(main_runs.company_id, self.env.company)
        self.assertEqual(main_runs.result_rows[0]['consumption'], 80.0)
        self.assertEqual(main_runs.result_rows[0]['meter'], 'M-SNAP')
        ReportService(self.env).send_due()
        self.assertEqual(len(self._runs(main['id'], 'completed')), 1)
        self.assertEqual(len(self._runs(other['id'], 'completed')), 1)
