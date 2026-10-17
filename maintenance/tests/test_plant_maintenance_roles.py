# -*- coding: utf-8 -*-

import base64
import io
import unittest

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


@tagged('post_install', '-at_install')
class TestPlantMaintenanceRoles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group_operator = cls.env.ref('maintenance.group_plant_maintenance_operator')
        cls.group_supervisor = cls.env.ref('maintenance.group_plant_maintenance_supervisor')
        cls.group_manager = cls.env.ref('maintenance.group_equipment_manager')

        cls.operator = cls.env['res.users'].create({
            'name': 'Role Test Operator',
            'login': 'role_operator_test',
            'email': 'role_operator_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_operator.id])],
        })
        cls.supervisor = cls.env['res.users'].create({
            'name': 'Role Test Supervisor',
            'login': 'role_supervisor_test',
            'email': 'role_supervisor_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_supervisor.id])],
        })
        cls.manager = cls.env['res.users'].create({
            'name': 'Role Test Manager',
            'login': 'role_manager_test',
            'email': 'role_manager_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_manager.id])],
        })

        cls.team = cls.env.ref('maintenance.equipment_team_maintenance')
        cls.equipment = cls.env['maintenance.equipment'].with_user(cls.manager).create({
            'name': 'Role Test Pump',
            'equipment_code': 'EQ-ROLE-001',
            'company_id': cls.company.id,
            'maintenance_team_id': cls.team.id,
        })

    def test_role_hierarchy(self):
        self.assertTrue(self.operator.has_group('maintenance.group_plant_maintenance_operator'))
        self.assertFalse(self.operator.has_group('maintenance.group_plant_maintenance_supervisor'))

        self.assertTrue(self.supervisor.has_group('maintenance.group_plant_maintenance_operator'))
        self.assertTrue(self.supervisor.has_group('maintenance.group_plant_maintenance_supervisor'))

        self.assertTrue(self.manager.has_group('maintenance.group_plant_maintenance_supervisor'))
        self.assertTrue(self.manager.has_group('maintenance.group_equipment_manager'))

    def test_operator_can_read_company_equipment(self):
        count = self.env['maintenance.equipment'].with_user(self.operator).search_count([
            ('company_id', '=', self.company.id),
        ])
        self.assertGreaterEqual(count, 1)

    def test_operator_cannot_create_equipment(self):
        with self.assertRaises(AccessError):
            self.env['maintenance.equipment'].with_user(self.operator).create({
                'name': 'Blocked by operator',
                'company_id': self.company.id,
            })

    def test_supervisor_can_create_equipment(self):
        equipment = self.env['maintenance.equipment'].with_user(self.supervisor).create({
            'name': 'Supervisor Created Asset',
            'equipment_code': 'EQ-SUP-001',
            'company_id': self.company.id,
        })
        self.assertTrue(equipment)

    def test_manager_can_delete_equipment(self):
        equipment = self.env['maintenance.equipment'].with_user(self.manager).create({
            'name': 'Temp Delete Asset',
            'equipment_code': 'EQ-DEL-001',
            'company_id': self.company.id,
        })
        equipment.with_user(self.manager).unlink()
        self.assertFalse(equipment.exists())

    def test_operator_cannot_delete_equipment(self):
        with self.assertRaises(AccessError):
            self.equipment.with_user(self.operator).unlink()

    @unittest.skipUnless(Workbook, 'openpyxl required')
    def test_supervisor_can_use_excel_import_wizard(self):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Equipment Master'
        ws.append(['Equipment Name', 'Equipment Code', 'Serial Number', 'Equipment Category',
                   'Maintenance Team', 'Owner', 'Responsible Person', 'Vendor', 'Model',
                   'Purchase Date', 'Warranty Expiry Date', 'Cost', 'Location', 'MTBF', 'MTTR', 'Status'])
        ws.append(['Role Excel Asset', 'EQ-ROLE-XLS', 'SN-ROLE-XLS', 'Test Cat', '', '', '', '', '', '', '', '', '', '', '', 'Active'])
        buffer = io.BytesIO()
        wb.save(buffer)
        wizard = self.env['maintenance.equipment.import.wizard'].with_user(self.supervisor).create({
            'file': base64.b64encode(buffer.getvalue()),
            'filename': 'roles.xlsx',
        })
        wizard.action_import_excel()
        self.assertTrue(self.env['maintenance.equipment'].search([('equipment_code', '=', 'EQ-ROLE-XLS')]))

    def test_operator_creates_own_work_order(self):
        request = self.env['maintenance.request'].with_user(self.operator).create({
            'name': 'Operator reported leak',
            'equipment_id': self.equipment.id,
            'maintenance_team_id': self.team.id,
            'owner_user_id': self.operator.id,
        })
        self.assertTrue(request)
        visible = self.env['maintenance.request'].with_user(self.operator).search([
            ('id', '=', request.id),
        ])
        self.assertEqual(len(visible), 1)
