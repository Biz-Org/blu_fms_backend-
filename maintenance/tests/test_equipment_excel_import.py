# -*- coding: utf-8 -*-

import base64
import io
import unittest

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


def _build_equipment_xlsx(rows):
    """Build a minimal Equipment Master workbook for tests."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Equipment Master'
    headers = [
        'Equipment Name', 'Equipment Code', 'Serial Number', 'Equipment Category',
        'Maintenance Team', 'Owner', 'Responsible Person', 'Vendor', 'Model',
        'Purchase Date', 'Warranty Expiry Date', 'Cost', 'Location', 'MTBF', 'MTTR', 'Status',
    ]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return base64.b64encode(buffer.getvalue())


@tagged('post_install', '-at_install')
class TestEquipmentExcelImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if Workbook is None:
            raise unittest.SkipTest('openpyxl is required for equipment Excel import tests')
        cls.Wizard = cls.env['maintenance.equipment.import.wizard']
        cls.ImportLog = cls.env['maintenance.equipment.import.log']
        cls.Equipment = cls.env['maintenance.equipment']
        cls.company = cls.env.company

        cls.group_supervisor = cls.env.ref('maintenance.group_plant_maintenance_supervisor')
        cls.group_operator = cls.env.ref('maintenance.group_plant_maintenance_operator')
        cls.group_manager = cls.env.ref('maintenance.group_equipment_manager')

        cls.supervisor = cls.env['res.users'].create({
            'name': 'Test Plant Supervisor',
            'login': 'plant_supervisor_test',
            'email': 'plant_supervisor_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_supervisor.id])],
        })
        cls.operator = cls.env['res.users'].create({
            'name': 'Test Plant Operator',
            'login': 'plant_operator_test',
            'email': 'plant_operator_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_operator.id])],
        })

    def _import_rows(self, rows, user=None):
        wizard = self.Wizard.with_user(user or self.supervisor).create({
            'file': _build_equipment_xlsx(rows),
            'filename': 'test_equipment.xlsx',
        })
        return wizard.action_import_excel()

    def test_import_creates_equipment_and_upload_log(self):
        rows = [
            ['Test Pump A', 'EQ-TEST-001', 'SN-TEST-001', 'Test Machines', '', '', '', '', 'Model-A', '', '', 1000, 'Plant A', 120, 2, 'Active'],
            ['Test Pump B', 'EQ-TEST-002', 'SN-TEST-002', 'Test Machines', '', '', '', '', 'Model-B', '', '', 1200, 'Plant B', 100, 3, 'Active'],
        ]
        self._import_rows(rows)

        equipment = self.Equipment.search([('equipment_code', 'in', ['EQ-TEST-001', 'EQ-TEST-002'])])
        self.assertEqual(len(equipment), 2)
        self.assertTrue(all(eq.is_excel_import for eq in equipment))
        self.assertTrue(all(eq.excel_import_id for eq in equipment))

        import_log = equipment[0].excel_import_id
        self.assertEqual(import_log.imported_count, 2)
        self.assertEqual(import_log.state, 'success')
        self.assertEqual(import_log.equipment_count, 2)

    def test_delete_upload_removes_linked_equipment(self):
        rows = [
            ['Temp Compressor', 'EQ-TMP-001', 'SN-TMP-001', 'Compressors', '', '', '', '', '', '', '', '', 'Utility', '', '', 'Active'],
        ]
        self._import_rows(rows)
        equipment = self.Equipment.search([('equipment_code', '=', 'EQ-TMP-001')])
        import_log = equipment.excel_import_id
        self.assertTrue(equipment)

        import_log.with_user(self.supervisor).action_remove_upload()
        self.assertFalse(self.Equipment.search([('equipment_code', '=', 'EQ-TMP-001')]))
        self.assertFalse(self.ImportLog.search([('id', '=', import_log.id)]))

    def test_existing_equipment_is_linked_not_duplicated(self):
        existing = self.Equipment.create({
            'name': 'Existing Asset',
            'equipment_code': 'EQ-DUP-001',
            'serial_no': 'SN-OLD-001',
            'company_id': self.company.id,
        })
        rows = [
            ['Existing Asset Updated', 'EQ-DUP-001', 'SN-OLD-001', 'Test Machines', '', '', '', '', '', '', '', '', '', '', '', 'Active'],
        ]
        self._import_rows(rows)
        self.assertEqual(self.Equipment.search_count([('equipment_code', '=', 'EQ-DUP-001')]), 1)
        existing.invalidate_recordset()
        self.assertTrue(existing.is_excel_import)
        self.assertTrue(existing.excel_import_id)

    def test_operator_cannot_import_excel(self):
        rows = [
            ['Operator Should Fail', 'EQ-OP-001', 'SN-OP-001', 'Test Machines', '', '', '', '', '', '', '', '', '', '', '', 'Active'],
        ]
        with self.assertRaises(AccessError):
            self._import_rows(rows, user=self.operator)

    def test_import_requires_file(self):
        wizard = self.Wizard.with_user(self.supervisor).create({})
        with self.assertRaises(UserError):
            wizard.action_import_excel()

    def test_template_download_action(self):
        wizard = self.Wizard.with_user(self.supervisor).create({})
        action = wizard.action_download_template()
        self.assertEqual(action.get('type'), 'ir.actions.act_url')
        self.assertIn('download', action.get('url', ''))
