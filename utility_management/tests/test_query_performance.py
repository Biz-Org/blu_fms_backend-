# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.utility_management.services.common import bucket_key, company_tz, reading_domain
from odoo.addons.utility_management.services.consumption_service import ConsumptionService
from odoo.addons.utility_management.services.electricity_service import ElectricityService
from odoo.addons.utility_management.services.gas_service import GasService
from odoo.addons.utility_management.services.meter_service import MeterService
from odoo.addons.utility_management.services.reading_service import ReadingService
from odoo.addons.utility_management.services.water_service import WaterService


@tagged('post_install', '-at_install', 'utility_domain')
class TestQueryPerformance(TransactionCase):

    def setUp(self):
        super().setUp()
        staff_group = self.env.ref('utility_management.group_utility_staff')
        manager_group = self.env.ref('utility_management.group_facility_manager')
        self.staff = self.env['res.users'].create({
            'name': 'Query Staff',
            'login': 'utility_query_staff',
            'groups_id': [(6, 0, [staff_group.id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        self.manager = self.env['res.users'].create({
            'name': 'Query Manager',
            'login': 'utility_query_manager',
            'groups_id': [(6, 0, [manager_group.id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        self.other_company = self.env['res.company'].create({'name': 'Query Other Company'})
        self.other_manager = self.env['res.users'].create({
            'name': 'Query Other Manager',
            'login': 'utility_query_other_manager',
            'groups_id': [(6, 0, [manager_group.id])],
            'company_id': self.other_company.id,
            'company_ids': [(6, 0, [self.other_company.id])],
        })
        for dimension, code in (('property', 'P1'), ('site', 'S1'), ('department', 'D1')):
            self.env['utility.management.access.scope'].create({
                'user_id': self.staff.id,
                'company_id': self.env.company.id,
                'dimension': dimension,
                'ref_code': code,
                'label': code,
            })

    def _meter(self, code, utility='electricity', user=None, **extra):
        values = {
            'name': code,
            'meter_code': code,
            'utility_type': utility,
            'meter_role': extra.pop('meter_role', 'consumption'),
            'reading_mode': 'interval',
            'protocol': 'manual',
            'property_ref': 'P1',
            'site_ref': 'S1',
            'department_ref': 'D1',
        }
        values.update(extra)
        return MeterService(self.env(user=user) if user else self.env).create(values)

    def _verified(self, meter_id, quantity, when, user=None, **extra):
        values = {
            'meter_id': meter_id,
            'observed_at': when,
            'source': 'manual',
            'interval_quantity': quantity,
        }
        values.update(extra)
        service = ReadingService(self.env(user=user) if user else self.env)
        created = service.create_manual(values)
        service.verify(created['reading_id'])
        return self.env['utility.management.reading'].browse(created['reading_id'])

    def _python_overview(self, filters, utility, measures):
        readings = self.env['utility.management.reading'].search(reading_domain(filters, utility))
        payload = {
            'reading_count': len(readings),
            'consumption': sum(readings.mapped('consumption_qty')),
            'abnormal': len(readings.filtered('is_abnormal')),
        }
        for measure in measures:
            values = [reading[measure] for reading in readings if reading[measure]]
            payload[measure] = {
                'average': (sum(values) / len(values)) if values else 0.0,
                'maximum': max(values) if values else 0.0,
            }
        if utility == 'electricity':
            payload['peak_demand'] = max(readings.mapped('demand_kw') or [0.0])
        return payload

    def test_empty_results_stay_empty(self):
        overview = ElectricityService(self.env).overview()
        self.assertEqual(overview['reading_count'], 0)
        self.assertEqual(overview['consumption'], 0.0)
        self.assertEqual(overview['abnormal'], 0)
        self.assertEqual(overview['peak_demand'], 0.0)
        self.assertEqual(ElectricityService(self.env).trends()['buckets'], [])
        self.assertEqual(WaterService(self.env).tanks(), [])
        self.assertEqual(GasService(self.env).safety(), [])
        self.assertEqual(ConsumptionService(self.env).overview()['electricity'], 0.0)
        listed = MeterService(self.env).list({'limit': 5, 'offset': 0})
        self.assertEqual(listed['total_count'], 0)
        self.assertEqual(listed['rows'], [])
        self.assertEqual(listed['summary'], {
            'electricity': 0, 'water': 0, 'gas': 0, 'online': 0, 'offline': 0, 'error': 0,
        })
        self.assertEqual(listed['properties'], [])

    def test_analytics_match_direct_reading_totals(self):
        self.env.company.partner_id.sudo().write({'tz': 'Asia/Kolkata'})
        first_meter = self._meter('Q-E1')
        second_meter = self._meter('Q-E2', property_ref='P2', site_ref='S2', department_ref='D2')
        morning = datetime(2020, 6, 15, 4, 30, 0)
        evening = datetime(2020, 6, 15, 20, 30, 0)
        later = datetime(2020, 6, 16, 3, 0, 0)
        first = self._verified(
            first_meter['id'], 10, morning, voltage=230, demand_kw=5, load_kw=4, power_factor=0,
        )
        second = self._verified(
            first_meter['id'], 6, evening, voltage=0, demand_kw=9, load_kw=8, power_factor=0.5,
        )
        self._verified(second_meter['id'], 4, later, voltage=240, demand_kw=3, load_kw=2, power_factor=1)
        first.with_context(utility_reading_service=True).write({'is_abnormal': True})
        filters = {'date_from': '2020-06-15', 'date_to': '2020-06-15'}
        measures = ('voltage', 'current', 'frequency', 'power_factor', 'load_kw')
        overview = ElectricityService(self.env).overview(filters)
        expected = self._python_overview(filters, 'electricity', measures)
        self.assertEqual(overview['reading_count'], expected['reading_count'])
        self.assertEqual(overview['reading_count'], 2)
        self.assertEqual(overview['consumption'], expected['consumption'])
        self.assertEqual(overview['abnormal'], expected['abnormal'])
        self.assertEqual(overview['abnormal'], 1)
        self.assertEqual(overview['peak_demand'], expected['peak_demand'])
        self.assertEqual(overview['voltage']['average'], expected['voltage']['average'])
        self.assertEqual(overview['voltage']['average'], 230.0)
        self.assertEqual(overview['power_factor']['average'], expected['power_factor']['average'])
        self.assertEqual(overview['power_factor']['average'], 0.5)
        self.assertEqual(overview['load_kw']['maximum'], expected['load_kw']['maximum'])
        trends = ElectricityService(self.env).trends({
            'grouping': 'day',
            'comparison': 'previous_period',
            'date_from': '2020-06-16',
            'date_to': '2020-06-16',
        })
        self.assertEqual(trends['previous_period']['consumption'], 16.0)
        self.assertEqual([row['bucket'] for row in trends['buckets']], ['2020-06-16'])
        self.assertEqual(trends['buckets'][0]['consumption'], 4.0)
        for grouping in ('day', 'week', 'month', 'year'):
            service_rows = ElectricityService(self.env).trends({'grouping': grouping})['buckets']
            readings = self.env['utility.management.reading'].search(reading_domain({}, 'electricity'))
            timezone = company_tz(self.env, readings[:1].company_id or self.env.company)
            expected_rows = {}
            for reading in readings:
                key = bucket_key(reading.observed_at, grouping, timezone)
                slot = expected_rows.setdefault(key, {'bucket': key, 'consumption': 0.0, 'peak_demand': 0.0, 'count': 0})
                slot['consumption'] += reading.consumption_qty
                slot['count'] += 1
                if reading.demand_kw > slot['peak_demand']:
                    slot['peak_demand'] = reading.demand_kw
            self.assertEqual(service_rows, [expected_rows[key] for key in sorted(expected_rows)])

    def test_consumption_matches_utility_and_property_split(self):
        electric = self._meter('Q-C-E')
        water = self._meter('Q-C-W', utility='water', property_ref='P2', site_ref='S2', department_ref='D2')
        gas = self._meter('Q-C-G', utility='gas')
        when = datetime(2020, 7, 1, 8, 0, 0)
        self._verified(electric['id'], 8, when, demand_kw=4)
        self._verified(water['id'], 3, when, flow_rate=1)
        abnormal = self._verified(gas['id'], 5, when + timedelta(hours=2), flow_rate=2, pressure=1, safety_observation='normal')
        abnormal.with_context(utility_reading_service=True).write({'is_abnormal': True})
        overview = ConsumptionService(self.env).overview()
        self.assertEqual(overview['electricity'], 8.0)
        self.assertEqual(overview['water'], 3.0)
        self.assertEqual(overview['gas'], 5.0)
        self.assertEqual(sum(row['consumption'] for row in overview['meters']), 16.0)
        properties = ConsumptionService(self.env).by_property()
        by_property = {row['property_ref']: row for row in properties}
        self.assertEqual(by_property['P1']['electricity'], 8.0)
        self.assertEqual(by_property['P1']['gas'], 5.0)
        self.assertEqual(by_property['P2']['water'], 3.0)
        analysis = ConsumptionService(self.env).analysis()
        self.assertEqual(analysis['meters'], overview['meters'])
        self.assertEqual([row['meter_id'] for row in analysis['abnormal_meters']], [gas['id']])

    def test_gas_safety_uses_latest_verified_reading(self):
        meter = self._meter('Q-GAS', utility='gas')
        other = self._meter('Q-GAS-2', utility='gas', property_ref='P2', site_ref='S2', department_ref='D2')
        self._verified(
            meter['id'], 1, datetime(2020, 8, 1, 8, 0, 0),
            flow_rate=1, pressure=2, safety_observation='warning',
        )
        self._verified(
            meter['id'], 2, datetime(2020, 8, 2, 8, 0, 0),
            flow_rate=4, pressure=6, safety_observation='critical',
        )
        pending = ReadingService(self.env).create_manual({
            'meter_id': meter['id'],
            'observed_at': datetime(2020, 8, 3, 8, 0, 0),
            'source': 'manual',
            'interval_quantity': 9,
            'flow_rate': 9,
            'pressure': 9,
            'safety_observation': 'normal',
        })
        self.assertNotEqual(pending['reading']['status'], 'verified')
        self._verified(
            other['id'], 1, datetime(2020, 8, 2, 9, 0, 0),
            flow_rate=3, pressure=3, safety_observation='warning',
        )
        rows = GasService(self.env).safety()
        current = [row for row in rows if row['meter_id'] == meter['id']][0]
        self.assertEqual(current['pressure'], 6)
        self.assertEqual(current['flow_rate'], 4)
        self.assertEqual(current['safety_observation'], 'critical')
        self.assertEqual(current['status'], 'connecting')

    def test_tanks_use_latest_level(self):
        meter = self._meter(
            'Q-TANK', utility='water', meter_role='tank', tank_capacity=100,
            property_ref='P1', site_ref='S1',
        )
        self._verified(
            meter['id'], 1, datetime(2020, 9, 1, 8, 0, 0),
            tank_level=20, flow_rate=1, inflow=2, outflow=1,
        )
        self._verified(
            meter['id'], 1, datetime(2020, 9, 2, 8, 0, 0),
            tank_level=35, flow_rate=3, inflow=4, outflow=2,
        )
        rows = WaterService(self.env).tanks({'property_ref': 'P1'})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tank_level'], 35)
        self.assertEqual(rows[0]['tank_capacity'], 100)
        self.assertEqual(rows[0]['availability'], 65)
        self.assertEqual(rows[0]['inflow'], 4)
        self.assertEqual(rows[0]['outflow'], 2)
        self.assertEqual(WaterService(self.env).tanks({'property_ref': 'P9'}), [])

    def test_inventory_summary_counts_and_properties(self):
        self._meter('Q-M1')
        self._meter('Q-M2', utility='water')
        self._meter('Q-M3', utility='gas', property_ref='P2', site_ref='S2', department_ref='D2')
        service = MeterService(self.env)
        listed = service.list({'limit': 1, 'offset': 0})
        self.assertEqual(listed['total_count'], 3)
        self.assertEqual(len(listed['rows']), 1)
        self.assertEqual(listed['summary'], {
            'electricity': 1, 'water': 1, 'gas': 1, 'online': 0, 'offline': 0, 'error': 0,
        })
        self.assertEqual(listed['properties'], ['P1', 'P2'])
        dashboard = service.dashboard({})
        self.assertEqual(dashboard['total'], 3)
        self.assertEqual(dashboard['counts']['connecting'], 3)
        self.assertEqual(dashboard['properties'], ['P1', 'P2'])
        self.assertEqual(len(dashboard['meters']), 3)

    def test_staff_scope_stays_on_assigned_locations(self):
        visible = self._meter('Q-S-VISIBLE')
        hidden = self._meter('Q-S-HIDDEN', property_ref='P2', site_ref='S2', department_ref='D2')
        self._verified(visible['id'], 7, datetime(2020, 5, 1, 9, 0, 0))
        self._verified(hidden['id'], 9, datetime(2020, 5, 1, 10, 0, 0))
        staff = self.env(user=self.staff)
        overview = ElectricityService(staff).overview()
        self.assertEqual(overview['consumption'], 7.0)
        self.assertEqual(overview['reading_count'], 1)
        meters = ConsumptionService(staff).by_meter()
        self.assertEqual([row['meter_code'] for row in meters], ['Q-S-VISIBLE'])
        listed = MeterService(staff).list({'limit': 5, 'offset': 0})
        self.assertEqual(listed['total_count'], 1)
        self.assertEqual(listed['summary']['electricity'], 1)
        self.assertEqual(listed['properties'], ['P1'])

    def test_manager_company_isolation_stays_in_place(self):
        self._meter('Q-MAIN')
        self._verified(self._meter('Q-MAIN-READ')['id'], 2, datetime(2020, 5, 2, 9, 0, 0))
        foreign = self._meter(
            'Q-FOREIGN', user=self.other_manager, company_id=self.other_company.id,
        )
        self._verified(foreign['id'], 9, datetime(2020, 5, 2, 10, 0, 0), user=self.other_manager)
        main = ElectricityService(self.env(user=self.manager)).overview()
        other = ElectricityService(self.env(user=self.other_manager)).overview()
        self.assertEqual(main['consumption'], 2.0)
        self.assertEqual(other['consumption'], 9.0)
        self.assertEqual(MeterService(self.env(user=self.manager)).list({'limit': 10, 'offset': 0})['total_count'], 2)
        self.assertEqual(
            MeterService(self.env(user=self.other_manager)).list({'limit': 10, 'offset': 0})['total_count'],
            1,
        )

    def test_pagination_and_date_window_stay_identical(self):
        self._meter('Q-P1')
        self._meter('Q-P2', utility='water')
        self._meter('Q-P3', utility='gas')
        service = MeterService(self.env)
        first = service.list({'limit': 1, 'offset': 0})
        second = service.list({'limit': 1, 'offset': 1})
        self.assertEqual(first['total_count'], 3)
        self.assertEqual(second['total_count'], 3)
        self.assertNotEqual(first['rows'][0]['id'], second['rows'][0]['id'])
        gas_one = self._meter('Q-PAGE-G1', utility='gas')
        gas_two = self._meter('Q-PAGE-G2', utility='gas')
        self._verified(gas_one['id'], 1, datetime(2020, 4, 1, 8, 0, 0), pressure=1, safety_observation='normal')
        self._verified(gas_two['id'], 1, datetime(2020, 4, 1, 9, 0, 0), pressure=2, safety_observation='warning')
        gas = GasService(self.env)
        page = gas.safety({'limit': 1, 'offset': 0})
        following = gas.safety({'limit': 1, 'offset': 1})
        self.assertEqual(page['limit'], 1)
        self.assertEqual(page['offset'], 0)
        self.assertGreaterEqual(page['total_count'], 2)
        self.assertEqual(len(page['rows']), 1)
        self.assertNotEqual(page['rows'][0]['meter_id'], following['rows'][0]['meter_id'])
        bounded = self._meter('Q-DATE')
        self._verified(bounded['id'], 5, datetime(2020, 6, 15, 23, 30, 0))
        self._verified(bounded['id'], 8, datetime(2020, 6, 16, 0, 30, 0))
        included = ElectricityService(self.env).overview({
            'date_from': '2020-06-15',
            'date_to': '2020-06-15',
            'meter_id': bounded['id'],
        })
        self.assertEqual(included['reading_count'], 1)
        self.assertEqual(included['consumption'], 5.0)

    def test_phase5_entry_points_remain(self):
        api = self.env['utility.management.ui.api']
        self.assertIsInstance(api.list_alerts({}), list)
        self.assertIsInstance(api.list_leaks({}), list)
        self.assertIsInstance(api.list_readings({}), list)
        self.assertTrue(hasattr(api, 'list_audit_events'))
        self.assertTrue(hasattr(api, 'get_audit_event'))
        paged = api.list_alerts({'limit': 1, 'offset': 0})
        self.assertEqual(sorted(paged), ['limit', 'offset', 'rows', 'total_count'])
