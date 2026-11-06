# -*- coding: utf-8 -*-
"""Phase 4 RPC contract and empty-response tests."""
import json
import unittest
from datetime import timedelta

try:
    from odoo import fields
    from odoo.exceptions import UserError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    UserError = Exception
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


FORBIDDEN_PAYLOAD = ('fake', 'demo', 'sample', 'placeholder')


def _assert_clean_payload(testcase, payload):
    blob = json.dumps(payload, default=str).lower()
    for word in FORBIDDEN_PAYLOAD:
        testcase.assertNotIn(word, blob)


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'cc_ui')
class TestCcUiEmpty(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.api = self.env['cc.ui.api']

    def test_empty_dashboard_and_lists(self):
        dashboard = self.api.get_dashboard_data()
        self.assertEqual(dashboard['kpis']['sites_total'], 0)
        self.assertEqual(dashboard['kpis']['sites_operational'], 0)
        self.assertEqual(dashboard['kpis']['alerts_active'], 0)
        self.assertEqual(dashboard['kpis']['incidents_open'], 0)
        self.assertEqual(dashboard['kpis']['emergencies_active'], 0)
        self.assertEqual(dashboard['kpis']['unresolved_overdue'], 0)
        self.assertEqual(dashboard['recent_activity'], [])
        self.assertEqual(dashboard['sites_summary'], [])
        _assert_clean_payload(self, dashboard)

        alerts = self.api.get_alerts_data({})
        self.assertEqual(alerts['kpis']['total'], 0)
        self.assertEqual(alerts['alerts'], [])
        self.assertFalse(alerts['selected'])
        self.assertEqual(alerts['sites'], [])
        _assert_clean_payload(self, alerts)

        monitoring = self.api.get_monitoring_data({})
        self.assertEqual(monitoring['sites'], [])
        _assert_clean_payload(self, monitoring)

        incidents = self.api.get_incidents_data({})
        self.assertEqual(incidents['kpis']['total'], 0)
        self.assertEqual(incidents['incidents'], [])
        self.assertFalse(incidents['selected'])
        _assert_clean_payload(self, incidents)

        emergency = self.api.get_emergency_data({})
        self.assertEqual(emergency['kpis']['total'], 0)
        self.assertEqual(emergency['alerts'], [])
        self.assertFalse(emergency['selected'])
        self.assertEqual(emergency['history'], [])
        _assert_clean_payload(self, emergency)

        reports = self.api.get_reports_data({})
        self.assertEqual(reports['kpis']['alerts'], 0)
        self.assertEqual(reports['alerts'], [])
        self.assertEqual(reports['incidents'], [])
        self.assertEqual(reports['sites'], [])
        self.assertEqual(reports['emergency'], [])
        _assert_clean_payload(self, reports)

        definitions = self.api.get_report_definitions({})
        self.assertEqual(definitions['definitions'], [])
        self.assertEqual(definitions['exports'], [])

    def test_export_report_not_available(self):
        with self.assertRaises(UserError):
            self.api.export_report(export_format='csv')


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'cc_ui')
class TestCcUiWithData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.api = self.env['cc.ui.api']
        self.site = self.env['cc.site'].create({
            'code': 'P4-UI',
            'name': 'UI Site',
            'operational_status': 'normal',
        })
        self.alert = self.env['cc.alert'].create({
            'alert_type': 'intrusion',
            'severity': 'high',
            'site_id': self.site.id,
        })
        self.emergency = self.env['cc.alert'].with_context(cc_lifecycle=True).create({
            'alert_type': 'fire',
            'severity': 'critical',
            'site_id': self.site.id,
            'is_emergency': True,
            'response_deadline': fields.Datetime.now() - timedelta(minutes=5),
        })
        self.incident = self.env['cc.incident'].create({
            'summary': 'North alarm',
            'severity': 'medium',
            'site_id': self.site.id,
        })

    def test_dashboard_and_list_shapes(self):
        dashboard = self.api.get_dashboard_data()
        self.assertEqual(dashboard['kpis']['sites_total'], 1)
        self.assertEqual(dashboard['kpis']['sites_operational'], 1)
        self.assertEqual(dashboard['kpis']['alerts_active'], 2)
        self.assertEqual(dashboard['kpis']['incidents_open'], 1)
        self.assertEqual(dashboard['kpis']['emergencies_active'], 1)
        self.assertEqual(dashboard['kpis']['unresolved_overdue'], 1)
        self.assertTrue(dashboard['recent_activity'])
        self.assertEqual(len(dashboard['sites_summary']), 1)
        _assert_clean_payload(self, dashboard)

        alerts = self.api.get_alerts_data({'alert_id': self.alert.id})
        self.assertEqual(len(alerts['alerts']), 1)
        self.assertEqual(alerts['selected']['id'], self.alert.id)
        self.assertIn('assignable_users', alerts)
        self.assertEqual(alerts['sites'][0]['code'], 'P4-UI')
        _assert_clean_payload(self, alerts)

        monitoring = self.api.get_monitoring_data({'site_id': self.site.id})
        row = monitoring['sites'][0]
        self.assertEqual(row['alerts_active'], 2)
        self.assertEqual(row['incidents_open'], 1)
        self.assertTrue(row['has_emergency'])
        self.assertTrue(row['latest_activity_at'])
        _assert_clean_payload(self, monitoring)

        incidents = self.api.get_incidents_data({'incident_id': self.incident.id})
        self.assertEqual(incidents['selected']['id'], self.incident.id)
        self.assertEqual(incidents['kpis']['incidents_open'], 1)
        _assert_clean_payload(self, incidents)

        emergency = self.api.get_emergency_data({'alert_id': self.emergency.id})
        self.assertEqual(emergency['selected']['id'], self.emergency.id)
        self.assertTrue(emergency['selected']['is_emergency'])
        self.assertEqual(emergency['kpis']['unresolved_overdue'], 1)
        _assert_clean_payload(self, emergency)

        reports = self.api.get_reports_data({'source': 'emergency'})
        self.assertEqual(len(reports['emergency']), 1)
        self.assertEqual(reports['alerts'], [])
        result = self.api.run_report(spec={'source': 'sites'})
        self.assertEqual(result['source'], 'sites')
        self.assertEqual(len(result['rows']), 1)
        with self.assertRaises(UserError):
            self.api.run_report(spec={'source': 'res.partner'})
