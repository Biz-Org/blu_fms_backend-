# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.alert_service import AlertService
from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.power_source_service import PowerSourceService
from odoo.addons.utility_management.services.reading_service import ReadingService


@tagged('post_install', '-at_install', 'utility_domain')
class TestSystemAlertRules(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.other_staff = self.env['res.users'].create({
            'name': 'System Alert Staff',
            'login': 'utility_system_alert_staff',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.other_company = self.env['res.company'].create({'name': 'System Alert Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'System Alert Other Manager',
            'login': 'utility_system_alert_other_manager',
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [manager_group.id])],
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

    def _rule(self, name, rule_type, meter_id=None):
        values = {
            'name': name,
            'rule_type': rule_type,
            'severity': 'critical',
            'escalation_minutes': 30,
            'escalate_to_id': self.other_staff.id,
            'utility_type': 'electricity',
            'property_ref': 'P1',
        }
        if meter_id:
            values['meter_id'] = meter_id
        return AlertService(self.env).save_rule(values)

    def _alert(self, meter_id, alert_type):
        return self.env['utility.management.alert'].search([
            ('meter_id', '=', meter_id),
            ('alert_type', '=', alert_type),
        ])

    def _assert_bound(self, alert, rule):
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.rule_id.id, rule['id'])
        self.assertEqual(alert.company_id, alert.rule_id.company_id)
        self.assertEqual(alert.severity, 'critical')
        self.assertEqual(alert.rule_id.escalation_minutes, 30)
        self.assertEqual(alert.rule_id.escalate_to_id, self.other_staff)
        self.assertEqual(alert.assignee_id, self.other_staff)
        self.assertEqual(alert.threshold_value, 0.0)
        self.assertEqual(alert.escalation_count, 0)
        self.assertEqual(alert.state, 'new')

    def test_system_alerts_use_matching_rules(self):
        offline_meter = self._meter('M-OFF')
        missing_meter = self._meter('M-MISS')
        grid_meter = self._meter('M-GRID')
        fault_meter = self._meter('M-FAULT')
        offline_rule = self._rule('Offline rule', 'meter_offline', offline_meter['id'])
        missing_rule = self._rule('Missing rule', 'missing_reading', missing_meter['id'])
        grid_rule = self._rule('Outage rule', 'grid_outage', grid_meter['id'])
        fault_rule = self._rule('Fault rule', 'generator_fault', fault_meter['id'])

        MeterService(self.env).set_status(offline_meter['id'], 'offline', health='failed')
        self.env['utility.management.meter'].browse(missing_meter['id']).write({
            'last_sync': fields.Datetime.now() - timedelta(hours=3),
        })
        ReadingService(self.env).flag_missing()
        grid = PowerSourceService(self.env).create({
            'name': 'Grid Bound',
            'source_kind': 'grid',
            'property_ref': 'P1',
            'meter_id': grid_meter['id'],
        })
        PowerSourceService(self.env).transition(grid['id'], 'grid_outage', {'load': 4})
        generator = PowerSourceService(self.env).create({
            'name': 'Generator Bound',
            'source_kind': 'generator',
            'property_ref': 'P1',
            'meter_id': fault_meter['id'],
        })
        PowerSourceService(self.env).transition(generator['id'], 'generator_fault', {'load': 2})

        bound = {
            'meter_offline': (offline_meter, offline_rule),
            'missing_reading': (missing_meter, missing_rule),
            'grid_outage': (grid_meter, grid_rule),
            'generator_fault': (fault_meter, fault_rule),
        }
        alerts = []
        for alert_type, (meter, rule) in bound.items():
            with self.subTest(alert_type=alert_type):
                alert = self._alert(meter['id'], alert_type)
                self._assert_bound(alert, rule)
                alerts.append(alert)

        past = fields.Datetime.now() - timedelta(hours=2)
        for alert in alerts:
            alert.sudo().with_context(utility_alert_service=True).write({'triggered_at': past})
        AlertService(self.env).escalate_due()
        for alert in alerts:
            alert.invalidate_recordset()
            self.assertEqual(alert.escalation_count, 1)
            self.assertEqual(alert.assignee_id, self.other_staff)
            self.assertEqual(alert.state, 'new')
            self.assertTrue(alert.escalated_at)
        AlertService(self.env).escalate_due()
        for alert in alerts:
            alert.invalidate_recordset()
            self.assertEqual(alert.escalation_count, 1)

    def test_system_alert_without_rule_stays_unbound(self):
        meter = self._meter('M-NORULE')
        inactive = self._rule('Inactive offline', 'meter_offline', meter['id'])
        AlertService(self.env).save_rule({'id': inactive['id'], 'active': False})
        mismatched = self._meter('M-OTHER')
        self._rule('Other meter offline', 'meter_offline', mismatched['id'])
        AlertService(self.env).save_rule({
            'name': 'Water only offline',
            'rule_type': 'meter_offline',
            'severity': 'high',
            'utility_type': 'water',
        })
        AlertService(self.env).save_rule({
            'name': 'Other property offline',
            'rule_type': 'meter_offline',
            'severity': 'high',
            'property_ref': 'P-OTHER',
        })

        MeterService(self.env).set_status(meter['id'], 'offline', health='failed')
        alert = self._alert(meter['id'], 'meter_offline')
        self.assertEqual(len(alert), 1)
        self.assertFalse(alert.rule_id)
        self.assertEqual(alert.severity, 'medium')
        self.assertFalse(alert.assignee_id)
        self.assertEqual(alert.threshold_value, 0.0)
        alert.sudo().with_context(utility_alert_service=True).write({
            'triggered_at': fields.Datetime.now() - timedelta(hours=5),
        })
        AlertService(self.env).escalate_due()
        alert.invalidate_recordset()
        self.assertEqual(alert.escalation_count, 0)
        self.assertEqual(alert.state, 'new')

    def test_system_alert_rules_stay_in_their_company(self):
        AlertService(self.env(user=self.other_manager)).save_rule({
            'name': 'Foreign offline',
            'rule_type': 'meter_offline',
            'severity': 'critical',
            'escalation_minutes': 15,
            'escalate_to_id': self.other_manager.id,
        })
        meter = self._meter('M-CO')
        MeterService(self.env).set_status(meter['id'], 'offline', health='failed')
        alert = self._alert(meter['id'], 'meter_offline')
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.company_id, self.env.company)
        self.assertFalse(alert.rule_id)
        self.assertEqual(alert.severity, 'medium')
        foreign_rules = self.env['utility.management.alert.rule'].sudo().search([
            ('company_id', '=', self.other_company.id),
            ('rule_type', '=', 'meter_offline'),
        ])
        self.assertTrue(foreign_rules)
        self.assertNotEqual(alert.company_id, foreign_rules.company_id)
