# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.alert_service import AlertService
from odoo.addons.utility_management.services.consumption_service import ConsumptionService
from odoo.addons.utility_management.services.electricity_service import ElectricityService
from odoo.addons.utility_management.services.gas_service import GasService
from odoo.addons.utility_management.services.leak_service import LeakService
from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.power_source_service import PowerSourceService
from odoo.addons.utility_management.services.reading_service import ReadingService
from odoo.addons.utility_management.services.report_service import ReportService
from odoo.addons.utility_management.services.water_service import WaterService


@tagged('post_install', '-at_install', 'utility_domain')
class TestUtilityDomain(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.staff = self.env['res.users'].create({
            'name': 'Utility Staff Domain',
            'login': 'utility_staff_domain',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.other_staff = self.env['res.users'].create({
            'name': 'Utility Staff Two',
            'login': 'utility_staff_domain_two',
            'groups_id': [(6, 0, [staff_group.id])],
        })
        self.other_company = self.env['res.company'].create({'name': 'Other Utility Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'Other Utility Manager',
            'login': 'utility_other_manager',
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
            'groups_id': [(6, 0, [manager_group.id])],
        })
        self.env['utility.management.access.scope'].create({
            'user_id': self.staff.id,
            'company_id': self.env.company.id,
            'dimension': 'property',
            'ref_code': 'P1',
            'label': 'Property 1',
        })
        self.env['utility.management.access.scope'].create({
            'user_id': self.staff.id,
            'company_id': self.env.company.id,
            'dimension': 'site',
            'ref_code': 'S1',
            'label': 'Site 1',
        })
        self.env['utility.management.access.scope'].create({
            'user_id': self.staff.id,
            'company_id': self.env.company.id,
            'dimension': 'department',
            'ref_code': 'D1',
            'label': 'Department 1',
        })

    def _meter(self, code, utility_type='electricity', **extra):
        values = {
            'name': code,
            'meter_code': code,
            'utility_type': utility_type,
            'meter_role': 'consumption',
            'reading_mode': 'cumulative',
            'protocol': 'manual',
            'property_ref': 'P1',
            'property_label': 'Property 1',
            'site_ref': 'S1',
            'department_ref': 'D1',
            'connection_config': {'host': 'meter.local', 'password': 'hidden'},
        }
        values.update(extra)
        return MeterService(self.env).create(values)

    def _reading(self, meter_id, register_value, hours_ago, **extra):
        values = {
            'meter_id': meter_id,
            'observed_at': fields.Datetime.now() - timedelta(hours=hours_ago),
            'register_value': register_value,
            'source': 'manual',
        }
        values.update(extra)
        return ReadingService(self.env).create_manual(values)

    def test_security_scope_and_company(self):
        visible = self._meter('M-P1')
        hidden = self._meter('M-P2', property_ref='P2', site_ref='S2', department_ref='D2')
        staff_meters = self.env['utility.management.meter'].with_user(self.staff).search([])
        self.assertIn(visible['id'], staff_meters.ids)
        self.assertNotIn(hidden['id'], staff_meters.ids)
        site_only = self._meter('M-S1', property_ref='P9', site_ref='S1', department_ref='D9')
        dept_only = self._meter('M-D1', property_ref='P9', site_ref='S9', department_ref='D1')
        staff_meters = self.env['utility.management.meter'].with_user(self.staff).search([])
        self.assertIn(site_only['id'], staff_meters.ids)
        self.assertIn(dept_only['id'], staff_meters.ids)
        self.assertFalse(self.env['utility.management.meter'].with_user(self.other_manager).search([]))
        with self.assertRaises(AccessError):
            MeterService(self.env(user=self.other_manager)).create({
                'name': 'Foreign',
                'meter_code': 'M-FOREIGN',
                'utility_type': 'water',
                'company_id': self.env.company.id,
            })
        with self.assertRaises(UserError):
            self.env['utility.management.reading'].sudo().with_context(utility_reading_service=True).create({
                'meter_id': visible['id'],
                'company_id': self.other_company.id,
                'observed_at': fields.Datetime.now() - timedelta(hours=1),
                'source': 'manual',
                'status': 'recorded',
                'register_value': 1,
            })
        try:
            MeterService(self.env(user=self.staff)).create({
                'name': 'Denied',
                'meter_code': 'M-DENIED',
                'utility_type': 'gas',
            })
            self.fail('Utility Staff created a meter.')
        except AccessError:
            pass
        denied = self.env['utility.management.audit.event'].sudo().search([
            ('event_type', '=', 'access_denied'),
            ('user_id', '=', self.staff.id),
        ])
        self.assertTrue(denied)
        self.assertEqual(denied[:1].outcome, 'denied')

    def test_meter_lifecycle_and_connection(self):
        meter = self._meter('M-LIFE')
        self.assertEqual(meter['status'], 'connecting')
        self.assertNotIn('password', meter['connection'])
        self.assertEqual(meter['connection'].get('host'), 'meter.local')
        result = MeterService(self.env).test_connection(meter['id'])
        self.assertEqual(result, {
            'ok': False,
            'error': 'no_provider_connected',
            'status': 'connecting',
        })
        stored = self.env['utility.management.meter'].browse(meter['id'])
        self.assertEqual(stored.status, 'connecting')
        self.assertTrue(stored.connectivity_ids)
        with self.assertRaises(UserError):
            MeterService(self.env).set_status(meter['id'], 'deactivated')
        MeterService(self.env).set_status(meter['id'], 'online', health='healthy')
        MeterService(self.env).set_status(meter['id'], 'offline', health='failed')
        MeterService(self.env).set_status(meter['id'], 'deactivated')
        stored.invalidate_recordset()
        self.assertFalse(stored.active)
        with self.assertRaises(UserError):
            self._reading(meter['id'], 10, 1)
        MeterService(self.env).set_status(meter['id'], 'connecting')
        stored.invalidate_recordset()
        self.assertTrue(stored.active)
        with self.assertRaises(UserError):
            stored.unlink()
        with self.assertRaises(ValidationError):
            self._meter('M-TANK', utility_type='water', meter_role='tank', tank_capacity=0)

    def test_readings_calculations_and_correction(self):
        meter = self._meter('M-READ', anomaly_enabled=True, anomaly_percent=10)
        first = self._reading(meter['id'], 100, 5)
        self.assertEqual(first['status'], 'accepted')
        self.assertEqual(first['reading']['status'], 'pending_verification')
        self.assertEqual(first['reading']['consumption_qty'], 0)
        self.assertTrue(first['reading']['name'].startswith('RDG/'))
        reading = self.env['utility.management.reading'].browse(first['reading_id'])
        self.assertEqual(reading.property_ref, 'P1')
        ReadingService(self.env).verify(first['reading_id'])
        second = self._reading(meter['id'], 150, 4)
        ReadingService(self.env).verify(second['reading_id'])
        self.assertEqual(second['reading']['consumption_qty'], 50)
        stamp = fields.Datetime.now() - timedelta(hours=3)
        third = self._reading(meter['id'], 250, 3, observed_at=stamp)
        self.assertTrue(third['reading']['is_abnormal'])
        with self.assertRaises(UserError):
            self._reading(meter['id'], 260, 3, observed_at=stamp)
        duplicate = self._reading(meter['id'], 260, 2, idempotency_key='same-key')
        again = self._reading(meter['id'], 999, 1, idempotency_key='same-key')
        self.assertEqual(again['status'], 'duplicate')
        self.assertEqual(again['reading_id'], duplicate['reading_id'])
        with self.assertRaises(UserError):
            self._reading(meter['id'], 10, -1)
        with self.assertRaises(AccessError):
            ReadingService(self.env(user=self.staff)).correct(second['reading_id'], {
                'register_value': 140,
                'notes': 'staff cannot correct',
                'is_rollover': True,
            })
        with self.assertRaises(UserError):
            self._reading(meter['id'], 90, 2)
        rolled = ReadingService(self.env).correct(second['reading_id'], {
            'register_value': 140,
            'notes': 'Register replaced',
            'observed_at': fields.Datetime.now() - timedelta(hours=4, minutes=1),
        })
        original = self.env['utility.management.reading'].browse(second['reading_id'])
        self.assertEqual(original.status, 'corrected')
        replacement = self.env['utility.management.reading'].browse(rolled['reading_id'])
        self.assertEqual(replacement.corrects_reading_id, original)
        with self.assertRaises(UserError):
            original.with_context(utility_reading_service=True).write({'notes': 'changed'})
        interval = self._meter('M-INT', reading_mode='interval')
        interval_reading = self._reading(interval['id'], 0, 2, interval_quantity=7)
        self.assertEqual(interval_reading['reading']['consumption_qty'], 7)
        water = self._meter('M-WATER', utility_type='water', meter_role='tank', tank_capacity=100)
        with self.assertRaises(ValidationError):
            self._reading(water['id'], 1, 2, voltage=230)
        self._reading(water['id'], 1, 2, tank_level=40, flow_rate=2, inflow=1, outflow=1)
        gas = self._meter('M-GAS', utility_type='gas')
        self._reading(gas['id'], 5, 2, flow_rate=1.5, pressure=3, safety_observation='warning')
        ReadingService(self.env).invalidate(third['reading_id'], 'Out of range')
        invalid = self.env['utility.management.reading'].browse(third['reading_id'])
        self.assertEqual(invalid.status, 'invalid')
        photo = ReadingService(self.env).attach_photo(
            first['reading_id'],
            base64.b64encode(b'png-bytes'),
            'meter.png',
            'image/png',
        )
        attachment = self.env['ir.attachment'].browse(photo['attachment_id'])
        self.assertFalse(attachment.public)
        self.assertEqual(attachment.res_model, 'utility.management.reading')
        with self.assertRaises(UserError):
            ReadingService(self.env).attach_photo(
                first['reading_id'],
                base64.b64encode(b'gif'),
                'meter.gif',
                'image/gif',
            )

    def test_analytics_power_leak_and_alert(self):
        meter = self._meter('M-ELEC')
        first = self._reading(meter['id'], 10, 6, voltage=230, current=4, frequency=50, power_factor=0.9, demand_kw=12, load_kw=8)
        ReadingService(self.env).verify(first['reading_id'])
        second = self._reading(meter['id'], 25, 5, voltage=231, demand_kw=20, load_kw=9)
        ReadingService(self.env).verify(second['reading_id'])
        overview = ElectricityService(self.env).overview()
        self.assertEqual(overview['consumption'], 15)
        self.assertEqual(overview['peak_demand'], 20)
        trends = ElectricityService(self.env).trends({'grouping': 'day', 'comparison': 'previous_period', 'date_from': fields.Date.today(), 'date_to': fields.Date.today()})
        self.assertTrue(trends['buckets'])
        water = self._meter('M-TANK2', utility_type='water', meter_role='tank', tank_capacity=80)
        level = self._reading(water['id'], 1, 3, tank_level=30, flow_rate=1, inflow=2, outflow=1)
        ReadingService(self.env).verify(level['reading_id'])
        more_water = self._reading(water['id'], 5, 2, tank_level=30, flow_rate=1)
        ReadingService(self.env).verify(more_water['reading_id'])
        tanks = WaterService(self.env).tanks()
        row = [item for item in tanks if item['meter_id'] == water['id']][0]
        self.assertEqual(row['availability'], 50)
        gas = self._meter('M-GAS2', utility_type='gas')
        gas_reading = self._reading(gas['id'], 8, 3, flow_rate=2, pressure=4, safety_observation='critical')
        ReadingService(self.env).verify(gas_reading['reading_id'])
        safety = GasService(self.env).safety()
        self.assertTrue(any(item['safety_observation'] == 'critical' for item in safety))
        more_gas = self._reading(gas['id'], 12, 2, flow_rate=2, pressure=4, safety_observation='warning')
        ReadingService(self.env).verify(more_gas['reading_id'])
        consumption = ConsumptionService(self.env).overview()
        self.assertEqual(consumption['electricity'], 15)
        self.assertGreater(consumption['water'], 0)
        self.assertGreater(consumption['gas'], 0)
        analysis = ConsumptionService(self.env).analysis()
        self.assertTrue(analysis['properties'])
        source = PowerSourceService(self.env).create({
            'name': 'Generator A',
            'source_kind': 'generator',
            'property_ref': 'P1',
            'meter_id': meter['id'],
        })
        self.assertFalse(source['fuel_level_percent'])
        PowerSourceService(self.env).transition(source['id'], 'generator_active', {
            'load': 12,
            'fuel_level_percent': 40,
            'fuel_consumed': 1,
        })
        restored = PowerSourceService(self.env).transition(source['id'], 'power_restored')
        self.assertEqual(restored['status'], 'grid_active')
        event = self.env['utility.management.power.event'].search([('source_id', '=', source['id'])], limit=1)
        event.with_context(utility_power_service=True).write({
            'started_at': fields.Datetime.now() - timedelta(hours=2),
        })
        self.assertAlmostEqual(event.runtime_hours, 2, places=1)
        grid = PowerSourceService(self.env).create({
            'name': 'Grid A',
            'source_kind': 'grid',
            'property_ref': 'P1',
            'meter_id': meter['id'],
        })
        PowerSourceService(self.env).transition(grid['id'], 'grid_outage')
        outage = self.env['utility.management.alert'].search([
            ('alert_type', '=', 'grid_outage'),
            ('meter_id', '=', meter['id']),
        ])
        self.assertTrue(outage)
        leak = LeakService(self.env(user=self.staff)).create({
            'leak_type': 'water',
            'severity': 'high',
            'meter_id': water['id'],
            'property_ref': 'P1',
        })
        self.assertTrue(leak['name'].startswith('LK/'))
        assigned = LeakService(self.env).assign(leak['id'], self.other_staff.id)
        self.assertEqual(assigned['assignee_id'], self.other_staff.id)
        visible = self.env['utility.management.leak'].with_user(self.other_staff).search([
            ('id', '=', leak['id']),
        ])
        self.assertTrue(visible)
        with self.assertRaises(UserError):
            LeakService(self.env).transition(leak['id'], 'closed')
        LeakService(self.env(user=self.staff)).transition(leak['id'], 'investigating')
        LeakService(self.env(user=self.staff)).add_action(leak['id'], {
            'entry_kind': 'investigation',
            'note': 'Checked the valve.',
        })
        with self.assertRaises(AccessError):
            LeakService(self.env(user=self.staff)).transition(leak['id'], 'resolved')
        LeakService(self.env).transition(leak['id'], 'resolved')
        closed = LeakService(self.env).transition(leak['id'], 'closed')
        self.assertGreaterEqual(closed['response_minutes'], 0)
        self.assertTrue(closed['actions'])
        rule = AlertService(self.env).save_rule({
            'name': 'High use',
            'rule_type': 'threshold',
            'utility_type': 'electricity',
            'meter_id': meter['id'],
            'threshold_value': 1,
            'severity': 'high',
            'escalation_minutes': 30,
            'escalate_to_id': self.other_staff.id,
        })
        alert_reading = self._reading(meter['id'], 40, 1)
        alert = self.env['utility.management.alert'].search([
            ('rule_id', '=', rule['id']),
            ('reading_id', '=', alert_reading['reading_id']),
        ])
        self.assertTrue(alert)
        self.assertTrue(alert.name.startswith('ALT/'))
        AlertService(self.env(user=self.staff)).transition(alert.id, 'acknowledged')
        with self.assertRaises(AccessError):
            AlertService(self.env(user=self.staff)).transition(alert.id, 'resolved')
        alert.sudo().with_context(utility_alert_service=True).write({
            'triggered_at': fields.Datetime.now() - timedelta(hours=2),
        })
        AlertService(self.env).escalate_due()
        alert.invalidate_recordset()
        self.assertEqual(alert.escalation_count, 1)
        self.assertEqual(alert.state, 'acknowledged')
        self.assertEqual(alert.assignee_id, self.other_staff)
        AlertService(self.env).transition(alert.id, 'in_progress')
        AlertService(self.env).transition(alert.id, 'resolved', {'resolution_note': 'Checked'})
        AlertService(self.env).transition(alert.id, 'closed')
        with self.assertRaises(UserError):
            alert.unlink()

    def test_reports_are_real_and_audit_is_append_only(self):
        meter = self._meter('M-RPT')
        created = self._reading(meter['id'], 10, 2, demand_kw=5)
        ReadingService(self.env).verify(created['reading_id'])
        report_types = [
            'electricity_consumption',
            'water_consumption',
            'gas_consumption',
            'combined_usage',
            'grid_vs_generator',
            'meter_reading',
            'leak_detection',
            'consumption_alert',
            'utility_trend',
            'utility_performance',
        ]
        service = ReportService(self.env)
        for report_type in report_types:
            definition = service.save_definition({
                'name': report_type,
                'report_type': report_type,
                'property_ref': 'P1',
                'grouping': 'day',
                'comparison': 'previous_period',
            })
            csv_run = service.run(definition['id'], 'csv')
            self.assertEqual(csv_run['execution_state'], 'completed', report_type)
            self.assertTrue(csv_run['name'].startswith('RPT/'))
            xlsx_run = service.run(definition['id'], 'xlsx')
            self.assertEqual(xlsx_run['execution_state'], 'completed', report_type)
            attachment = self.env['ir.attachment'].browse(xlsx_run['attachment_id'])
            self.assertFalse(attachment.public)
            self.assertTrue(base64.b64decode(attachment.datas).startswith(b'PK'))
            pdf_run = service.run(definition['id'], 'pdf')
            if pdf_run['execution_state'] == 'completed':
                pdf = self.env['ir.attachment'].browse(pdf_run['attachment_id'])
                self.assertTrue(base64.b64decode(pdf.datas).startswith(b'%PDF'))
            else:
                self.assertEqual(pdf_run['execution_state'], 'failed', report_type)
                self.assertTrue(pdf_run['error_message'])
                self.assertFalse(pdf_run['attachment_id'])
        audit = self.env['utility.management.audit.event'].search([
            ('event_type', '=', 'report_execution'),
        ], limit=1)
        self.assertTrue(audit)
        with self.assertRaises(UserError):
            audit.write({'summary': 'changed'})
        with self.assertRaises(UserError):
            audit.unlink()
        self.assertFalse(self.env['utility.management.audit.event'].search([
            ('summary', 'ilike', 'password'),
        ]))
