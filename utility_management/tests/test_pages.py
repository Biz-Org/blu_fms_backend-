# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.mail.models.mail_template import MailTemplate
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.alert_service import AlertService
from odoo.addons.utility_management.services.common import observed_end, observed_start
from odoo.addons.utility_management.services.leak_service import LeakService
from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.notification_service import NotificationService
from odoo.addons.utility_management.services.reading_service import ReadingService
from odoo.addons.utility_management.services.report_service import ReportService


@tagged('post_install', '-at_install', 'utility_domain')
class TestOperationalPages(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.staff = self.env['res.users'].create({
            'name': 'Page Staff',
            'login': 'utility_page_staff',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.other_company = self.env['res.company'].create({'name': 'Page Other Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'Page Other Manager',
            'login': 'utility_page_other_manager',
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [manager_group.id])],
        })
        for dimension, code in (('property', 'P1'), ('site', 'S1'), ('department', 'D1')):
            self.env['utility.management.access.scope'].create({
                'user_id': self.staff.id,
                'company_id': self.env.company.id,
                'dimension': dimension,
                'ref_code': code,
                'label': code,
            })

    def _alert(self, name, severity='high', property_ref='P1', company=None, alert_type='threshold'):
        company = company or self.env.company
        return self.env['utility.management.alert'].with_context(utility_alert_service=True).create({
            'name': name,
            'alert_type': alert_type,
            'severity': severity,
            'state': 'new',
            'triggered_at': fields.Datetime.now(),
            'company_id': company.id,
            'property_ref': property_ref,
            'site_ref': 'S9' if property_ref != 'P1' else 'S1',
            'department_ref': 'D9' if property_ref != 'P1' else 'D1',
            'observed_value': 1,
        })

    def _leak(self, severity='high', property_ref='P1', company=None):
        return LeakService(self.env).create({
            'leak_type': 'water',
            'severity': severity,
            'property_ref': property_ref,
            'site_ref': 'S9' if property_ref != 'P1' else 'S1',
            'department_ref': 'D9' if property_ref != 'P1' else 'D1',
            'company_id': (company or self.env.company).id,
        })

    def test_alert_pages_keep_filters_and_company_scope(self):
        created = []
        for index in range(4):
            created.append(self._alert('ALT-HIGH-%s' % index, 'high'))
        created.append(self._alert('ALT-LOW-1', 'low'))
        created.append(self._alert('ALT-LOW-2', 'low'))
        self._alert('ALT-HIDDEN', 'high', property_ref='P2')
        self._alert('ALT-FOREIGN', 'high', company=self.other_company)
        service = AlertService(self.env(user=self.staff))
        first = service.list({'limit': 2, 'offset': 0})
        second = service.list({'limit': 2, 'offset': 2})
        self.assertEqual(len(first['rows']), 2)
        self.assertEqual(len(second['rows']), 2)
        self.assertEqual(first['total_count'], 6)
        self.assertGreater(first['total_count'], 2)
        self.assertEqual(first['offset'], 0)
        self.assertEqual(second['offset'], 2)
        visible_ids = [row['id'] for row in first['rows'] + second['rows']]
        self.assertEqual(len(set(visible_ids)), 4)
        newest = list(reversed(created))
        self.assertEqual(first['rows'][0]['id'], newest[0].id)
        self.assertEqual(second['rows'][0]['id'], newest[2].id)
        high = service.list({'limit': 2, 'offset': 0, 'severity': 'high'})
        self.assertEqual(high['total_count'], 4)
        self.assertTrue(all(row['severity'] == 'high' for row in high['rows']))
        named = service.list({'limit': 5, 'offset': 0, 'search': 'ALT-LOW-2'})
        self.assertEqual(named['total_count'], 1)
        self.assertEqual(named['rows'][0]['name'], 'ALT-LOW-2')
        self.assertFalse(service.list({'limit': 20, 'offset': 0, 'search': 'ALT-FOREIGN'})['rows'])
        self.assertFalse(service.list({'limit': 20, 'offset': 0, 'search': 'ALT-HIDDEN'})['rows'])

    def test_leak_pages_keep_filters_and_company_scope(self):
        created = []
        for index in range(4):
            created.append(self._leak('high'))
        created.append(self._leak('low'))
        created.append(self._leak('low'))
        self._leak('high', property_ref='P2')
        hidden_company = LeakService(self.env(user=self.other_manager)).create({
            'leak_type': 'water',
            'severity': 'high',
            'property_ref': 'P1',
            'company_id': self.other_company.id,
        })
        service = LeakService(self.env(user=self.staff))
        first = service.list({'limit': 2, 'offset': 0})
        second = service.list({'limit': 2, 'offset': 2})
        self.assertEqual(len(first['rows']), 2)
        self.assertEqual(len(second['rows']), 2)
        self.assertEqual(first['total_count'], 6)
        self.assertEqual([row['id'] for row in first['rows']], [created[-1]['id'], created[-2]['id']])
        self.assertEqual(second['rows'][0]['id'], created[-3]['id'])
        low = service.list({'limit': 5, 'offset': 0, 'severity': 'low'})
        self.assertEqual(low['total_count'], 2)
        self.assertTrue(all(row['severity'] == 'low' for row in low['rows']))
        self.assertNotIn(hidden_company['id'], [row['id'] for row in service.list({'limit': 20, 'offset': 0})['rows']])
        self.assertEqual(service.list({'limit': 20, 'offset': 0, 'property_ref': 'P2'})['total_count'], 0)

    def test_report_run_pages_keep_snapshot_and_failures(self):
        meter = MeterService(self.env).create({
            'name': 'Page Meter',
            'meter_code': 'M-PAGE',
            'utility_type': 'electricity',
            'meter_role': 'consumption',
            'reading_mode': 'interval',
            'protocol': 'manual',
            'property_ref': 'P1',
        })
        created = ReadingService(self.env).create_manual({
            'meter_id': meter['id'],
            'observed_at': fields.Datetime.now() - timedelta(hours=3),
            'source': 'manual',
            'interval_quantity': 80,
        })
        ReadingService(self.env).verify(created['reading_id'])
        service = ReportService(self.env)
        definition = service.save_definition({
            'name': 'Paged electricity',
            'report_type': 'electricity_consumption',
            'schedule': 'daily',
            'meter_id': meter['id'],
        })
        completed = service.run(definition['id'], 'csv')
        self.assertEqual(completed['chart'], [{'label': 'M-PAGE', 'value': 80.0}])
        stored = self.env['utility.management.report.run'].browse(completed['id'])
        later = ReadingService(self.env).create_manual({
            'meter_id': meter['id'],
            'observed_at': fields.Datetime.now() - timedelta(hours=1),
            'source': 'manual',
            'interval_quantity': 25,
        })
        ReadingService(self.env).verify(later['reading_id'])
        for index in range(4):
            service.run(definition['id'], 'csv')
        failed = self.env['utility.management.report.run'].with_context(
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
        first = service.list_runs({'limit': 2, 'offset': 0, 'definition_id': definition['id']})
        second = service.list_runs({'limit': 2, 'offset': 2, 'definition_id': definition['id']})
        self.assertEqual(len(first['rows']), 2)
        self.assertEqual(len(second['rows']), 2)
        self.assertEqual(first['total_count'], 6)
        self.assertGreater(first['total_count'], 2)
        seen = {row['id']: row for row in first['rows'] + second['rows']}
        self.assertIn(failed.id, seen)
        self.assertEqual(seen[failed.id]['execution_state'], 'failed')
        self.assertTrue(seen[failed.id]['error_message'])
        reopened = service.run_dto(stored)
        self.assertEqual(reopened['chart'], [{'label': 'M-PAGE', 'value': 80.0}])
        self.assertEqual(reopened['chart_state'], 'ready')
        self.assertEqual(stored.result_rows[0]['consumption'], 80.0)
        today = fields.Date.context_today(self.env.user)
        definition_record = self.env['utility.management.report.definition'].browse(definition['id'])
        self.assertFalse(service._is_due(definition_record, today))
        service.send_due()
        self.assertEqual(self.env['utility.management.report.run'].search_count([
            ('definition_id', '=', definition['id']),
            ('execution_state', '=', 'completed'),
        ]), 5)

    def test_reading_end_date_includes_the_whole_day(self):
        meter = MeterService(self.env).create({
            'name': 'Date Meter',
            'meter_code': 'M-DATE',
            'utility_type': 'electricity',
            'meter_role': 'consumption',
            'reading_mode': 'interval',
            'protocol': 'manual',
            'property_ref': 'P1',
        })
        day = fields.Date.context_today(self.env.user) - timedelta(days=1)
        stamps = {
            'start': datetime.combine(day, time(0, 0)),
            'later': datetime.combine(day, time(18, 30)),
            'after': datetime.combine(day + timedelta(days=1), time(0, 0)),
        }
        for observed in stamps.values():
            ReadingService(self.env).create_manual({
                'meter_id': meter['id'],
                'observed_at': observed,
                'source': 'manual',
                'interval_quantity': 1,
            })
        self.assertEqual(observed_start(day), datetime.combine(day, datetime.min.time()))
        self.assertEqual(observed_end(day), datetime.combine(day, datetime.max.time()))
        self.assertLess(stamps['later'], observed_end(day))
        self.assertGreater(stamps['after'], observed_end(day))
        listed = ReadingService(self.env).list({
            'meter_id': meter['id'],
            'date_from': fields.Date.to_string(day),
            'date_to': fields.Date.to_string(day),
            'limit': 10,
            'offset': 0,
        })
        observed = {row['observed_at'] for row in listed['rows']}
        self.assertIn(fields.Datetime.to_string(stamps['start']), observed)
        self.assertIn(fields.Datetime.to_string(stamps['later']), observed)
        self.assertNotIn(fields.Datetime.to_string(stamps['after']), observed)
        self.assertEqual(listed['total_count'], 2)

    def test_meter_pages_rules_and_notification_skip_still_hold(self):
        for index in range(3):
            MeterService(self.env).create({
                'name': 'Meter %s' % index,
                'meter_code': 'M-PG-%s' % index,
                'utility_type': 'electricity',
                'meter_role': 'consumption',
                'reading_mode': 'cumulative',
                'protocol': 'manual',
                'property_ref': 'P1',
            })
        meters = MeterService(self.env(user=self.staff)).list({'limit': 2, 'offset': 0, 'property_ref': 'P1'})
        self.assertEqual(len(meters['rows']), 2)
        self.assertEqual(meters['total_count'], 3)
        meter = meters['rows'][0]
        rule = AlertService(self.env).save_rule({
            'name': 'Offline page rule',
            'rule_type': 'meter_offline',
            'severity': 'critical',
            'meter_id': meter['id'],
            'escalation_minutes': 15,
            'property_ref': 'P1',
        })
        MeterService(self.env).set_status(meter['id'], 'offline', health='failed')
        alert = self.env['utility.management.alert'].search([
            ('meter_id', '=', meter['id']),
            ('alert_type', '=', 'meter_offline'),
        ])
        self.assertEqual(alert.rule_id.id, rule['id'])
        self.assertEqual(alert.severity, 'critical')
        with patch.object(MailTemplate, 'send_mail', autospec=True) as mocked:
            result = NotificationService(self.env).notify_record(alert, self.staff, alert.name)
        mocked.assert_not_called()
        self.assertTrue(result['skipped'])
        note = self.env['utility.management.audit.event'].search([
            ('res_id', '=', alert.id),
            ('summary', '=', 'Notification skipped.'),
        ], limit=1)
        self.assertTrue(note)
        self.assertEqual(note.data_after.get('reason'), 'notifications_disabled')
        self.assertNotEqual(note.outcome, 'success')
