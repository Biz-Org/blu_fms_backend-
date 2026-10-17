# -*- coding: utf-8 -*-
"""Continuous maintenance request workflow — stay on the same record across steps."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MaintenanceRequestContinuousWorkflow(models.Model):
    _inherit = 'maintenance.request'

    equipment_image = fields.Image(
        related='equipment_id.image_1920',
        string='Equipment Image',
        readonly=True,
    )
    equipment_code_display = fields.Char(
        string='Equipment Code',
        compute='_compute_equipment_code_display',
    )
    manpower_notes = fields.Text(string='Manpower Notes')
    planning_notes = fields.Text(string='Planning Notes')
    manpower_ref_display = fields.Char(
        string='Request Ref',
        compute='_compute_manpower_ref_display',
    )
    manpower_technician_count = fields.Integer(
        string='Technicians Assigned',
        compute='_compute_manpower_assignment_kpis',
    )
    manpower_total_hours = fields.Float(
        string='Total Planned Hours',
        compute='_compute_manpower_assignment_kpis',
        digits=(16, 2),
    )

    @api.depends('equipment_id', 'equipment_id.equipment_code', 'equipment_id.serial_no')
    def _compute_equipment_code_display(self):
        for request in self:
            eq = request.equipment_id
            request.equipment_code_display = (
                (eq.equipment_code or eq.serial_no or '') if eq else ''
            )

    def _compute_manpower_ref_display(self):
        for request in self:
            request.manpower_ref_display = _('MR-%s') % (request.id or '')

    # Named distinctly — must not override maintenance.py `_compute_manpower_summary`
    @api.depends('manpower_line_ids', 'manpower_line_ids.planned_hours', 'manpower_line_ids.user_id')
    def _compute_manpower_assignment_kpis(self):
        for request in self:
            lines = request.manpower_line_ids
            request.manpower_technician_count = len(lines)
            request.manpower_total_hours = sum(lines.mapped('planned_hours'))

    def action_save_manpower(self):
        """Persist manpower assignment and stay on the same form."""
        self.ensure_one()
        self.flush_recordset()
        self.message_post(body=_('Manpower assignment details were saved.'))
        return self._action_open_request_step(
            'maintenance.maintenance_request_manpower_form_view',
            _('Manpower Assignment'),
        )

    def action_add_manpower_line(self):
        """Add a technician row on the same request and stay on the form."""
        self.ensure_one()
        next_seq = (max(self.manpower_line_ids.mapped('sequence') or [0]) + 1)
        self.env['maintenance.request.manpower.line'].create({
            'request_id': self.id,
            'user_id': self.env.user.id,
            'skill_type': 'mechanical',
            'status': 'available',
            'assigned_task': '',
            'planned_hours': 1.0,
            'sequence': next_seq,
        })
        return self._action_open_request_step(
            'maintenance.maintenance_request_manpower_form_view',
            _('Manpower Assignment'),
        )

    def action_add_spare_line(self):
        """Add a spare-part row on the same request and stay on planning."""
        self.ensure_one()
        self._create_empty_spare_line()
        return self._action_open_request_step(
            'maintenance.maintenance_request_planning_form_view',
            _('Maintenance Planning'),
        )

    def action_add_inventory_spare_line(self):
        """Add a spare-part row and stay on Inventory & Spares."""
        self.ensure_one()
        self._create_empty_spare_line()
        return self._action_open_request_step(
            'maintenance.maintenance_request_spares_form_view',
            _('Inventory & Spares'),
        )

    def _create_empty_spare_line(self):
        self.ensure_one()
        next_seq = (max(self.spare_line_ids.mapped('sequence') or [0]) + 10)
        return self.env['maintenance.request.spare.line'].create({
            'request_id': self.id,
            'spare_name': '',
            'quantity': 1.0,
            'sequence': next_seq,
            'stock_status': 'available',
        })

    def action_back_to_manpower(self):
        """Footer Back — return to Manpower Assignment for the same request."""
        self.ensure_one()
        return self.action_workflow_assign_technician()

    def action_back_to_inventory_spares(self):
        """Footer Back — return to Inventory & Spares for the same request."""
        self.ensure_one()
        return self.action_workflow_inventory_spares()

    def action_save_work_order(self):
        """Persist execution details and stay on the Work Order form."""
        self.ensure_one()
        self.flush_recordset()
        self.message_post(body=_('Work order execution details were saved.'))
        return self._action_open_request_step(
            'maintenance.maintenance_request_execution_form_view',
            _('Work Order'),
        )

    def action_print_planning(self):
        """Header Print — reopen planning (browser print via Ctrl+P)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_request_planning_form_view',
            _('Maintenance Planning'),
        )

    def action_print_timeline(self):
        """Header Print on Workflow / Timeline — stay on the same screen."""
        self.ensure_one()
        return self.action_workflow_open_timeline()

    def action_back_to_planning(self):
        """Footer Back — return to Maintenance Planning for the same request."""
        self.ensure_one()
        return self.action_workflow_plan_maintenance()

    def action_continue_to_inventory_spares(self):
        """Save context and open Inventory / Spares for the same request (not a list)."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before continuing to inventory.'))
        if not self.manpower_line_ids and not self.user_id:
            raise UserError(_('Assign at least one technician before continuing.'))
        self.flush_recordset()
        return self.action_workflow_inventory_spares()

    def action_save_inventory_spares(self):
        """Persist inventory / spares details and stay on the same form."""
        self.ensure_one()
        self.message_post(body=_('Inventory and spares details were saved.'))
        return self._action_open_request_step(
            'maintenance.maintenance_request_spares_form_view',
            _('Inventory / Spares'),
        )

    def action_continue_to_create_work_order(self):
        """Move from Inventory / Spares to Create Work Order for the same request."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before creating a work order.'))
        return self.action_workflow_create_work_order()

    def action_workflow_open_rca_mom(self):
        """Analysis: RCA & MOM for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_rca_case_form_view',
            _('Root Cause Analysis & MOM'),
        )

    def action_workflow_open_fishbone(self):
        """Analysis: Plant fishbone RCA for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_plant_rca_form_view',
            _('AI Fishbone Root Cause Analysis'),
        )

    def action_workflow_open_why_why(self):
        """Analysis: Why-Why RCA for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_why_rca_form_view',
            _('AI Why-Why Root Cause Analysis'),
        )

    def action_workflow_open_agile(self):
        """Analysis: Agile investigation for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_agile_rca_form_view',
            _('Agile Investigation Network (RCA)'),
        )

    def action_workflow_open_capa(self):
        """Analysis: CAPA dashboard for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_capa_rca_form_view',
            _('AI CAPA Management Dashboard'),
        )

    def action_workflow_open_nogo(self):
        """Analysis: No-Go screen for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_request_nogo_form_view',
            _('No-Go Decision'),
        )

    def _action_open_request_step(self, view_xmlid, title):
        """Open a specialized form for THIS request (never a list).

        Always set form_view_ref + views. Without form_view_ref, Odoo keeps the
        current form when switching steps on the same res_id (e.g. Request → Manpower).
        """
        self.ensure_one()
        view = self.env.ref(view_xmlid, raise_if_not_found=False)
        ctx = dict(
            self.env.context,
            active_id=self.id,
            active_ids=[self.id],
            default_equipment_id=self.equipment_id.id,
            default_maintenance_team_id=self.maintenance_team_id.id,
            # Bust same-record form cache so specialized views actually render
            pm_workflow_step=view_xmlid,
            form_view_ref=view_xmlid,
        )
        action = {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'maintenance.request',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')] if view else [(False, 'form')],
            'target': 'current',
            'context': ctx,
        }
        if view:
            action['view_id'] = view.id
        return self._pm_finalize_step_action(action, view_xmlid)

    def action_workflow_open_request(self):
        """Return to the main request detail form for the same record."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.hr_equipment_request_view_form',
            _('Maintenance Request'),
        )

    def action_workflow_plan_maintenance(self):
        """Step: Plan Maintenance — same request, planning form."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before planning maintenance.'))
        return self._action_open_request_step(
            'maintenance.maintenance_request_planning_form_view',
            _('Maintenance Planning'),
        )

    def action_workflow_assign_technician(self):
        """Step: Assign Technician — same request, manpower form."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before assigning a technician.'))
        if self.user_id and not self.manpower_line_ids:
            self.env['maintenance.request.manpower.line'].create({
                'request_id': self.id,
                'user_id': self.user_id.id,
                'skill_type': 'other',
                'status': 'busy',
                'assigned_task': _('Primary technician'),
            })
        return self._action_open_request_step(
            'maintenance.maintenance_request_manpower_form_view',
            _('Manpower Assignment'),
        )

    def action_workflow_inventory_spares(self):
        """Optional step: Inventory & Spares for the same request."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_request_spares_form_view',
            _('Inventory & Spares'),
        )

    def action_workflow_open_execution(self):
        """Open Work Order / execution screen for the same request (no status change)."""
        self.ensure_one()
        return self._action_open_execution_form()

    def action_workflow_open_timeline(self):
        """Open Workflow / Timeline for the same request (never the list)."""
        self.ensure_one()
        return self._action_open_request_step(
            'maintenance.maintenance_request_workflow_timeline_form_view',
            _('Workflow / Timeline'),
        )

    def action_workflow_create_work_order(self):
        """Step: Create Work Order — reuse existing backend, stay on this request."""
        return self.action_create_maintenance_order()

    def action_workflow_start_work(self):
        """Step: Start Work — mark in progress and open execution for this request."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before starting work.'))
        if self.stage_id and self.stage_id.done:
            raise UserError(_('This request is already closed.'))
        if self.execution_status == 'completed':
            raise UserError(_('This work order is already completed.'))

        stage_new = self.env.ref('maintenance.stage_0', raise_if_not_found=False)
        stage_progress = self.env.ref('maintenance.stage_1', raise_if_not_found=False)
        vals = {'execution_status': 'in_progress'}
        if stage_progress and (
            not self.stage_id
            or (stage_new and self.stage_id == stage_new)
        ):
            vals['stage_id'] = stage_progress.id
        if not (self.work_order_sequence or '').strip():
            vals['work_order_sequence'] = _('WO-%s') % self.id
        if not self.user_id:
            technician = self.manpower_line_ids[:1].user_id
            if technician:
                vals['user_id'] = technician.id
        self.write(vals)
        self.message_post(body=_('Work started on this maintenance request.'))
        return self._action_open_execution_form()

    def action_workflow_complete_maintenance(self):
        """Step 6: Complete Maintenance — same request, stay on Work Order form."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Reopen the request before completing maintenance.'))
        # Already finished — just reopen the right screen (no error popup)
        if (self.stage_id and self.stage_id.done) or self.done:
            return self.action_workflow_open_request()
        if self.execution_status == 'completed':
            return self._action_open_execution_form()
        if self.execution_status == 'paused':
            raise UserError(_(
                'Work is paused.\n\nClick Start Work first, then Complete Maintenance.'
            ))
        if self.execution_status not in ('in_progress', False, None):
            raise UserError(_(
                'Start Work before completing maintenance.\n\n'
                'Use the Start Work button, then click Complete Maintenance again.'
            ))
        try:
            return self.action_complete_work_order()
        except ValidationError as err:
            raise UserError(err.args[0]) from err

    def action_workflow_verify_close(self):
        """Step 7: Verify/Close — close the same request and open its detail form."""
        self.ensure_one()
        if self.archive:
            raise UserError(_('Cancelled requests cannot be verified/closed.'))
        # Already closed — open request form quietly (stepper click must not error)
        if (self.stage_id and self.stage_id.done) or self.done:
            return self.action_workflow_open_request()
        if self.execution_status != 'completed':
            raise UserError(_(
                'Complete Maintenance first (step 6), then Verify / Close.\n\n'
                'Click Complete Maintenance on the Work Order screen, then try again.'
            ))
        try:
            self._raise_if_rca_missing_for_closure()
        except ValidationError as err:
            raise UserError(err.args[0]) from err
        stage_done = self.env.ref('maintenance.stage_3', raise_if_not_found=False)
        vals = {
            'execution_status': 'completed',
            'go_no_go_decision': self.go_no_go_decision or 'go',
            'close_date': fields.Date.context_today(self),
        }
        if stage_done:
            vals['stage_id'] = stage_done.id
        self.write(vals)
        self.message_post(body=_('Maintenance verified and closed.'))
        return self.action_workflow_open_request()

    def action_pause_work(self):
        for request in self:
            request.execution_status = 'paused'
            request.message_post(body=_('Work has been paused from execution tab.'))
        if len(self) == 1:
            return self._action_open_execution_form()
        return True

    def action_complete_work_order(self):
        self._raise_if_rca_missing_for_closure()
        for request in self:
            request.execution_status = 'completed'
            request.go_no_go_decision = 'go'
            request.message_post(body=_('Work order marked as completed.'))
        if len(self) == 1:
            return self._action_open_execution_form()
        return True
