# Part of Preventive Maintenance Management.

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .pm_access import pm_is_manager, pm_is_technician, pm_is_technician_only


class PmWorkOrder(models.Model):
    _name = "pm.work.order"
    _description = "PM Work Order"
    _inherit = ["mail.thread", "mail.activity.mixin", "pm.audit.mixin"]
    _order = "date_scheduled desc, id desc"

    name = fields.Char(string="Reference", required=True, copy=False, default="New", readonly=True)

    plan_id = fields.Many2one("pm.plan", required=True, ondelete="restrict", index=True)
    schedule_id = fields.Many2one("pm.schedule", ondelete="set null", index=True)

    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Asset", required=True, ondelete="restrict", index=True
    )
    property_location = fields.Char(string="Property / Location")

    maintenance_type = fields.Selection(related="plan_id.maintenance_type", store=True, readonly=True)

    team_id = fields.Many2one("maintenance.team", string="Maintenance Team")
    user_id = fields.Many2one(
        "res.users",
        string="Assigned Technician",
        tracking=True,
    )
    supervisor_id = fields.Many2one("res.users", string="Supervisor", tracking=True)

    reading_result_ids = fields.One2many(
        "pm.asset.reading.result", "work_order_id", string="Asset Readings"
    )

    priority = fields.Selection(
        [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Very High")],
        default="1",
        required=True,
    )

    date_scheduled = fields.Date(required=True, index=True)
    date_due = fields.Date(required=True, index=True)

    datetime_start = fields.Datetime(string="Actual Start")
    datetime_end = fields.Datetime(string="Actual End")
    duration_planned = fields.Float(string="Planned Duration (hours)")
    duration_actual = fields.Float(
        string="Actual Duration (hours)", compute="_compute_duration_actual", store=True
    )

    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("pending_inspection", "Pending Inspection"),
            ("rework", "Rework Required"),
            ("completed", "Completed"),
            ("skipped", "Skipped"),
            ("cancelled", "Cancelled"),
            ("overdue", "Overdue"),
        ],
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
    )

    mandatory_checklist = fields.Boolean(default=True)
    checklist_template_id = fields.Many2one("pm.checklist.template", ondelete="set null")
    checklist_line_ids = fields.One2many("pm.checklist.result", "work_order_id", string="Checklist Results")

    instruction_snapshot = fields.Html(string="Instructions (snapshot)")

    work_performed = fields.Text()
    technician_remarks = fields.Text()
    downtime_hours = fields.Float()

    meter_reading = fields.Float(string="Meter Reading")
    inspection_findings = fields.Text()

    material_line_ids = fields.One2many("pm.material.line", "work_order_id", string="Materials")
    cost_line_ids = fields.One2many("pm.cost.line", "work_order_id", string="Costs")

    labour_cost = fields.Monetary(currency_field="currency_id", compute="_compute_costs", store=True)
    service_cost = fields.Monetary(currency_field="currency_id", compute="_compute_costs", store=True)
    material_cost = fields.Monetary(currency_field="currency_id", compute="_compute_costs", store=True)
    total_cost = fields.Monetary(currency_field="currency_id", compute="_compute_costs", store=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    attachment_before_ids = fields.Many2many(
        "ir.attachment",
        "pm_wo_attachment_before_rel",
        "wo_id",
        "attachment_id",
        string="Before Photos",
    )
    attachment_after_ids = fields.Many2many(
        "ir.attachment",
        "pm_wo_attachment_after_rel",
        "wo_id",
        "attachment_id",
        string="After Photos",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment", "pm_wo_attachment_rel", "wo_id", "attachment_id", string="Documents"
    )

    skip_reason = fields.Text()
    cancel_reason = fields.Text()

    corrective_request_id = fields.Many2one(
        "maintenance.request",
        string="Corrective Maintenance Request",
        readonly=True,
        copy=False,
    )

    inspection_ids = fields.One2many("pm.inspection", "work_order_id", string="Inspections")
    inspection_count = fields.Integer(compute="_compute_inspection_count")

    is_overdue_flag = fields.Boolean(compute="_compute_overdue", store=True)

    _sql_constraints = [
        ("pm_wo_name_company_uniq", "unique(name, company_id)", "Work order reference must be unique per company."),
    ]

    @api.depends("datetime_start", "datetime_end")
    def _compute_duration_actual(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end:
                delta = rec.datetime_end - rec.datetime_start
                rec.duration_actual = max(delta.total_seconds() / 3600.0, 0.0)
            else:
                rec.duration_actual = 0.0

    @api.depends("cost_line_ids.amount", "material_line_ids.subtotal")
    def _compute_costs(self):
        for rec in self:
            labour = sum(rec.cost_line_ids.filtered(lambda c: c.cost_type == "labour").mapped("amount"))
            service = sum(rec.cost_line_ids.filtered(lambda c: c.cost_type == "service").mapped("amount"))
            mat = sum(rec.material_line_ids.mapped("subtotal"))
            rec.labour_cost = labour
            rec.service_cost = service
            rec.material_cost = mat
            rec.total_cost = labour + service + mat

    def _compute_inspection_count(self):
        for rec in self:
            rec.inspection_count = len(rec.inspection_ids)

    @api.depends("state", "date_due")
    def _compute_overdue(self):
        today = fields.Date.today()
        for rec in self:
            open_states = (
                "scheduled",
                "assigned",
                "in_progress",
                "on_hold",
                "pending_inspection",
                "rework",
            )
            rec.is_overdue_flag = rec.state in open_states and rec.date_due and rec.date_due < today

    @api.model_create_multi
    def create(self, vals_list):
        if pm_is_technician_only(self.env):
            raise AccessError("Technicians cannot create work orders.")
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("pm.work.order") or "New"
        return super().create(vals_list)

    TECHNICIAN_WRITABLE_FIELDS = {
        "datetime_start",
        "datetime_end",
        "work_performed",
        "technician_remarks",
        "downtime_hours",
        "meter_reading",
        "inspection_findings",
        "checklist_line_ids",
        "material_line_ids",
        "cost_line_ids",
        "attachment_before_ids",
        "attachment_after_ids",
        "attachment_ids",
        "message_follower_ids",
    }

    def write(self, vals):
        if pm_is_technician_only(self.env):
            forbidden = set(vals) - self.TECHNICIAN_WRITABLE_FIELDS
            if forbidden:
                raise AccessError(
                    "Technicians cannot modify: %s" % (", ".join(sorted(forbidden)))
                )
        if vals.get("user_id"):
            if not pm_is_manager(self.env):
                raise AccessError("Only managers can assign technicians.")
        if vals.get("user_id"):
            for rec in self:
                old = rec.user_id.id if rec.user_id else False
                new = vals["user_id"]
                if old != new:
                    rec._pm_audit_log(
                        "wo_assign",
                        f"Technician reassigned to {rec.env['res.users'].browse(new).name}",
                        old_vals={"user_id": old},
                        new_vals={"user_id": new},
                    )
                    if rec.state == "scheduled" and new:
                        vals.setdefault("state", "assigned")
        res = super().write(vals)
        return res

    def _ensure_checklist_lines(self):
        for wo in self:
            if not wo.checklist_template_id:
                continue
            existing = wo.checklist_line_ids.mapped("item_id")
            for item in wo.checklist_template_id.item_ids:
                if item not in existing:
                    self.env["pm.checklist.result"].create(
                        {
                            "work_order_id": wo.id,
                            "item_id": item.id,
                            "result": False,
                        }
                    )

    def _validate_mandatory_checklist(self):
        """Return False if any mandatory item is failed (corrective path)."""
        self.ensure_one()
        if not self.mandatory_checklist:
            return True
        for line in self.checklist_line_ids:
            if line.item_id.mandatory and not line.result:
                raise ValidationError(
                    f"Mandatory checklist item '{line.item_id.name}' requires a result."
                )
            if line.item_id.mandatory and line.result == "fail":
                return False
        return True

    def _create_corrective_request(self):
        self.ensure_one()
        Mr = self.env["maintenance.request"]
        team = self.team_id or self.equipment_id.maintenance_team_id
        if not team:
            team = self.env.ref("maintenance.equipment_team_maintenance", raise_if_not_found=False)
        vals = {
            "name": f"PM Finding: {self.name}",
            "equipment_id": self.equipment_id.id,
            "technician_user_id": self.user_id.id if self.user_id else False,
            "maintenance_type": "corrective",
            "priority": {"0": "1", "1": "2", "2": "3", "3": "3"}.get(self.priority, "2"),
            "description": (
                f"Raised from PM Work Order {self.name} (Plan: {self.plan_id.reference}).\n"
                f"Findings:\n{self.inspection_findings or self.technician_remarks or ''}"
            ),
        }
        if team:
            vals["maintenance_team_id"] = team.id
        req = Mr.create(vals)
        self.corrective_request_id = req.id
        return req

    def action_start(self):
        self._check_technician_or_manager()
        for wo in self:
            if wo.state not in ("scheduled", "assigned", "rework"):
                raise UserError("Work order cannot be started in the current state.")
            wo._ensure_checklist_lines()
            wo.write({"state": "in_progress", "datetime_start": fields.Datetime.now()})
            wo._pm_audit_log("wo_state", "Work started", new_vals={"state": "in_progress"})
            if wo.schedule_id:
                wo.schedule_id.state = "in_progress"

    def action_hold(self):
        self._check_technician_or_manager()
        for wo in self:
            if wo.state != "in_progress":
                raise UserError("Only in-progress work can be put on hold.")
            wo.write({"state": "on_hold"})
            wo._pm_audit_log("wo_state", "Work on hold")

    def action_resume(self):
        self._check_technician_or_manager()
        for wo in self:
            if wo.state != "on_hold":
                raise UserError("Only on-hold work can be resumed.")
            wo.write({"state": "in_progress"})
            wo._pm_audit_log("wo_state", "Work resumed")

    def action_submit_inspection(self):
        """Technician submits for manager inspection."""
        self._check_technician_or_manager()
        for wo in self:
            if wo.state not in ("in_progress", "rework"):
                raise UserError("Submit for inspection only from In Progress or Rework.")
            wo._ensure_checklist_lines()
            fails = wo.checklist_line_ids.filtered(lambda l: l.result == "fail")
            if fails:
                wo._create_corrective_request()
            valid = wo._validate_mandatory_checklist()
            if not valid:
                # Failed mandatory items: corrective request created; still proceed to inspection
                pass
            wo.write(
                {
                    "state": "pending_inspection",
                    "datetime_end": fields.Datetime.now(),
                }
            )
            self.env["pm.inspection"].create(
                {
                    "work_order_id": wo.id,
                    "state": "pending",
                }
            )
            wo._pm_audit_log("wo_state", "Submitted for inspection", new_vals={"state": "pending_inspection"})
            if wo.schedule_id:
                wo.schedule_id.state = "in_progress"

    def action_inspection_approve(self):
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can approve inspection.")
        for wo in self:
            if wo.state != "pending_inspection":
                raise UserError("Work order is not pending inspection.")
            if pm_is_technician_only(self.env) and wo.user_id == self.env.user:
                raise AccessError("You cannot approve your own work.")
            insp = wo.inspection_ids.filtered(lambda i: i.state == "pending")[:1]
            if insp:
                insp.write(
                    {
                        "state": "approved",
                        "reviewer_id": self.env.user.id,
                        "review_date": fields.Datetime.now(),
                    }
                )
            wo.write({"state": "completed"})
            wo._pm_audit_log("inspection", "Inspection approved — work order completed")
            wo._pm_audit_log("wo_state", "Completed", new_vals={"state": "completed"})
            if wo.schedule_id:
                wo.schedule_id.state = "completed"
            wo._create_next_occurrence()

    def action_inspection_reject(self, remarks):
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can reject inspection.")
        for wo in self:
            if wo.state != "pending_inspection":
                raise UserError("Work order is not pending inspection.")
            insp = wo.inspection_ids.filtered(lambda i: i.state == "pending")[:1]
            if insp:
                insp.write(
                    {
                        "state": "rejected",
                        "inspection_remarks": remarks,
                        "reviewer_id": self.env.user.id,
                        "review_date": fields.Datetime.now(),
                    }
                )
            wo.write({"state": "rework"})
            wo._pm_audit_log("inspection", "Inspection rejected — sent for rework", new_vals={"remarks": remarks})

    def action_skip(self, reason):
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can skip work orders.")
        for wo in self:
            wo.write({"state": "skipped", "skip_reason": reason})
            wo._pm_audit_log("wo_skip", reason or "Skipped", new_vals={"state": "skipped"})
            if wo.schedule_id:
                wo.schedule_id.state = "skipped"

    def action_cancel(self, reason):
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can cancel work orders.")
        for wo in self:
            wo.write({"state": "cancelled", "cancel_reason": reason})
            wo._pm_audit_log("wo_cancel", reason or "Cancelled", new_vals={"state": "cancelled"})
            if wo.schedule_id:
                wo.schedule_id.state = "cancelled"

    def action_close_completed(self):
        """Manager-only close after inspection approval."""
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can close work orders.")
        for wo in self:
            if wo.state != "pending_inspection":
                raise UserError("Use inspection approval to close.")
        return True

    def _create_next_occurrence(self):
        """After successful completion, create next schedule/WO from active plan."""
        for wo in self:
            plan = wo.plan_id
            if plan.state != "active" or not plan.auto_next_schedule:
                continue
            if plan.frequency_basis != "time":
                continue
            last_date = wo.date_scheduled or fields.Date.today()
            next_date = plan._next_time_date(last_date)
            due = plan._due_date_from_planned(next_date)
            if plan.end_date and next_date > plan.end_date:
                continue
            equip = wo.equipment_id
            if plan.auto_generate_work_orders:
                sched = self.env["pm.schedule"].create(
                    plan._prepare_schedule_vals(next_date, due, work_order=False, equipment=equip)
                )
                new_wo = self.create(
                    plan._prepare_work_order_vals(next_date, due, schedule=sched, equipment=equip)
                )
                sched.write({"work_order_id": new_wo.id})
            else:
                self.env["pm.schedule"].create(
                    plan._prepare_schedule_vals(next_date, due, work_order=False, equipment=equip)
                )
            plan._pm_audit_log("schedule_generate", "Next PM occurrence created after completion")

    def _check_technician_or_manager(self):
        if pm_is_manager(self.env):
            return
        if not pm_is_technician(self.env):
            raise AccessError("You are not allowed to execute PM work orders.")
        for wo in self:
            if wo.user_id and wo.user_id != self.env.user:
                raise AccessError("You can only work on work orders assigned to you.")

    @api.model
    def cron_update_overdue(self):
        today = fields.Date.today()
        wos = self.search(
            [
                (
                    "state",
                    "in",
                    ("scheduled", "assigned", "in_progress", "on_hold", "pending_inspection", "rework"),
                ),
                ("date_due", "<", today),
            ]
        )
        wos.write({"state": "overdue"})
        self.env["pm.schedule"].cron_update_schedule_states()


class PmChecklistResult(models.Model):
    _name = "pm.checklist.result"
    _description = "PM Checklist Result"

    work_order_id = fields.Many2one(
        "pm.work.order", required=True, ondelete="cascade", index=True
    )
    item_id = fields.Many2one("pm.checklist.item", required=True, ondelete="cascade")
    result = fields.Selection(
        [
            ("pass", "Pass"),
            ("fail", "Fail"),
            ("na", "Not Applicable"),
            ("obs", "Observation"),
        ]
    )
    observation = fields.Text()


class PmMaterialLine(models.Model):
    _name = "pm.material.line"
    _description = "PM Material Consumption Line"

    work_order_id = fields.Many2one("pm.work.order", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", string="Part / Material", required=True)
    quantity = fields.Float(default=1.0, required=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", related="product_id.uom_id", store=True)
    unit_cost = fields.Monetary(currency_field="currency_id")
    subtotal = fields.Monetary(
        currency_field="currency_id", compute="_compute_subtotal", store=True
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )

    @api.depends("quantity", "unit_cost")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = (rec.quantity or 0.0) * (rec.unit_cost or 0.0)


class PmCostLine(models.Model):
    _name = "pm.cost.line"
    _description = "PM Cost Line"

    work_order_id = fields.Many2one("pm.work.order", required=True, ondelete="cascade", index=True)
    cost_type = fields.Selection(
        [("labour", "Labour"), ("service", "Service"), ("other", "Other")],
        default="labour",
        required=True,
    )
    description = fields.Char()
    amount = fields.Monetary(currency_field="currency_id", required=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )
