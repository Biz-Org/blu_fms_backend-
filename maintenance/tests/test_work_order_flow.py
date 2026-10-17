# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkOrderFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env['maintenance.request']
        cls.Equipment = cls.env['maintenance.equipment']
        cls.SpareLine = cls.env['maintenance.request.spare.line']
        cls.ManpowerLine = cls.env['maintenance.request.manpower.line']
        cls.company = cls.env.company
        cls.team = cls.env.ref('maintenance.equipment_team_maintenance')
        cls.stage_new = cls.env.ref('maintenance.stage_0')
        cls.stage_progress = cls.env.ref('maintenance.stage_1')

        cls.group_supervisor = cls.env.ref('maintenance.group_plant_maintenance_supervisor')
        cls.supervisor = cls.env['res.users'].create({
            'name': 'WO Flow Supervisor',
            'login': 'wo_flow_supervisor_test',
            'email': 'wo_flow_supervisor_test@test.example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.group_supervisor.id])],
        })

        cls.equipment = cls.Equipment.create({
            'name': 'Flow Test Compressor',
            'equipment_code': 'EQ-FLOW-001',
            'serial_no': 'SN-FLOW-001',
            'company_id': cls.company.id,
            'maintenance_team_id': cls.team.id,
        })

    def _create_request(self):
        return self.Request.with_user(self.supervisor).create({
            'name': 'High temperature alarm',
            'equipment_id': self.equipment.id,
            'maintenance_team_id': self.team.id,
            'maintenance_type': 'corrective',
            'owner_user_id': self.supervisor.id,
            'stage_id': self.stage_new.id,
        })

    def test_workflow_steps_progress_through_lifecycle(self):
        request = self._create_request()

        self.assertTrue(request.wf_step_issue_done)
        self.assertTrue(request.wf_step_plan_done)
        self.assertFalse(request.wf_step_spare_done)

        self.SpareLine.create({
            'request_id': request.id,
            'spare_name': 'Oil filter kit',
            'quantity': 1,
            'cost': 250,
        })
        self.assertTrue(request.wf_step_spare_done)

        self.ManpowerLine.create({
            'request_id': request.id,
            'user_id': self.supervisor.id,
            'skill_type': 'mechanical',
        })
        self.assertTrue(request.wf_step_assigned_done)

        request.action_create_maintenance_order()
        self.assertEqual(request.execution_status, 'in_progress')
        self.assertEqual(request.stage_id, self.stage_progress)
        self.assertTrue(request.work_order_sequence)

        request.write({
            'actual_hours': 3.0,
            'execution_notes': 'Replaced filter and cleaned cooler.',
        })
        self.assertTrue(request.wf_step_execution_done)

        request.action_mark_go()
        self.assertEqual(request.go_no_go_decision, 'go')
        self.assertTrue(request.wf_step_gonogo_done)

        request.write({'final_root_cause': 'Blocked cooler / poor airflow'})
        self.assertTrue(request.wf_step_rca_done)

        request.action_complete_work_order()
        self.assertEqual(request.execution_status, 'completed')
        self.assertTrue(request.wf_step_completed_done)

    def test_create_maintenance_order_requires_equipment(self):
        request = self.Request.create({
            'name': 'Missing equipment',
            'maintenance_team_id': self.team.id,
            'planned_date': fields.Date.today(),
            'planning_maintenance_type': 'breakdown',
        })
        with self.assertRaises(UserError):
            request.action_create_maintenance_order()

    def test_create_maintenance_order_requires_planning(self):
        request = self._create_request()
        request.write({'planning_maintenance_type': False, 'planned_date': False})
        with self.assertRaises(UserError):
            request.action_create_maintenance_order()

    def test_workflow_timeline_action_opens_form(self):
        request = self._create_request()
        action = request.action_open_workflow_timeline()
        self.assertEqual(action['res_model'], 'maintenance.request')
        self.assertEqual(action['res_id'], request.id)
        self.assertEqual(action['view_mode'], 'form')

    def test_go_no_go_decisions(self):
        request = self._create_request()
        request.write({
            'planned_date': fields.Date.today(),
            'planning_maintenance_type': 'breakdown',
            'actual_hours': 1.0,
        })
        request.action_mark_no_go()
        self.assertEqual(request.go_no_go_decision, 'no_go')

        request.action_mark_go()
        self.assertEqual(request.go_no_go_decision, 'go')
