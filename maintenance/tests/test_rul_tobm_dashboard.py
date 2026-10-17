# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRulTobmDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env['maintenance.rul.tobm.dashboard']
        cls.Equipment = cls.env['maintenance.equipment']
        cls.Category = cls.env['maintenance.equipment.category']
        cls.company = cls.env.company

        cls.cat_fleet = cls.Category.create({'name': 'Test Fleet RUL'})
        cls.cat_plant = cls.Category.create({'name': 'Test Plant RUL'})

        cls.eq_fleet_a = cls.Equipment.create({
            'name': 'RUL Fleet A',
            'company_id': cls.company.id,
            'category_id': cls.cat_fleet.id,
            'life_consumed_percent': 80.0,
            'expected_mtbf': 90,
        })
        cls.eq_fleet_b = cls.Equipment.create({
            'name': 'RUL Fleet B',
            'company_id': cls.company.id,
            'category_id': cls.cat_fleet.id,
            'life_consumed_percent': 68.0,
            'expected_mtbf': 90,
        })
        cls.eq_plant = cls.Equipment.create({
            'name': 'RUL Plant Compressor',
            'company_id': cls.company.id,
            'category_id': cls.cat_plant.id,
            'life_consumed_percent': 40.0,
            'expected_mtbf': 120,
        })

        cls.dashboard = cls.Dashboard.create({
            'name': 'Test RUL Dashboard',
            'company_id': cls.company.id,
            'analysis_period_days': 365,
        })

    def test_rul_from_life_consumed(self):
        self.assertEqual(self.dashboard._rul_for_life(75.0), 25.0)
        self.assertEqual(self.dashboard._rul_for_life(0.0), 100.0)

    def test_tobm_window_detection(self):
        self.assertTrue(self.dashboard.TOBM_WINDOW_START <= 68.0 < self.dashboard.FAILURE_LIFE_PCT)
        self.assertFalse(self.dashboard.TOBM_WINDOW_START <= 80.0 < self.dashboard.FAILURE_LIFE_PCT)

    def test_category_filter_scopes_equipment_and_kpis(self):
        self.dashboard.write({'category_id': False})
        stats_all = self.dashboard._rul_stats()
        self.assertGreaterEqual(len(stats_all['rows']), 3)

        self.dashboard.apply_dashboard_filters({'category_id': self.cat_fleet.id})
        payload_fleet = self.dashboard._build_dashboard_payload()
        fleet_rows = self.dashboard._rul_stats()['rows']
        self.assertEqual(len(fleet_rows), 2)
        self.assertEqual(payload_fleet['kpis']['tobm_count'], 1)
        self.assertIn('Test Fleet RUL', payload_fleet['meta'])
        avg_expected = int(round(sum(r['rul'] for r in fleet_rows) / len(fleet_rows), 0))
        self.assertEqual(payload_fleet['kpis']['avg_rul_display'], f'{avg_expected}%')

    def test_equipment_selector_updates_chart_not_kpi_average(self):
        self.dashboard.write({'category_id': self.cat_fleet.id})
        payload_before = self.dashboard.apply_dashboard_filters({
            'equipment_id': self.eq_fleet_a.id,
        })
        avg_before = payload_before['kpis']['avg_rul_display']

        payload_after = self.dashboard.apply_dashboard_filters({
            'equipment_id': self.eq_fleet_b.id,
        })
        self.assertEqual(payload_after['kpis']['avg_rul_display'], avg_before)
        self.assertEqual(payload_after['detail']['equipment_id'], self.eq_fleet_b.id)
        self.assertNotEqual(
            payload_after['detail']['title'],
            payload_before['detail']['title'],
        )

    def test_invalid_equipment_outside_category_is_corrected(self):
        self.dashboard.write({
            'category_id': self.cat_fleet.id,
            'equipment_id': self.eq_plant.id,
        })
        payload = self.dashboard._build_dashboard_payload()
        self.assertIn(
            payload['detail']['equipment_id'],
            {self.eq_fleet_a.id, self.eq_fleet_b.id},
        )
