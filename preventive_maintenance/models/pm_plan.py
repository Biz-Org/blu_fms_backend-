# Part of Preventive Maintenance Management.

import json
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PmPlan(models.Model):
    _name = "pm.plan"
    _description = "Preventive Maintenance Plan"
    _inherit = ["mail.thread", "mail.activity.mixin", "pm.audit.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(string="Plan Reference", copy=False, readonly=True, default="New")

    description = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    # Asset scope — standard Odoo Maintenance equipment as FMS asset surrogate
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Asset",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    asset_category_id = fields.Many2one(
        "maintenance.equipment.category",
        string="Plan by category",
        help="When set without a specific asset, schedules apply to equipment in this category.",
    )
    category_id = fields.Many2one(
        "maintenance.equipment.category",
        string="Asset Category",
        compute="_compute_category_id",
        store=True,
        readonly=True,
    )

    @api.depends("equipment_id", "equipment_id.category_id", "asset_category_id")
    def _compute_category_id(self):
        for rec in self:
            rec.category_id = rec.equipment_id.category_id if rec.equipment_id else rec.asset_category_id

    property_location = fields.Char(
        string="Property / Location",
        tracking=True,
        help="Site, building or area. If empty, the asset equipment location is used when generating work orders.",
    )

    maintenance_type = fields.Selection(
        [
            ("inspection", "Inspection"),
            ("servicing", "Servicing"),
            ("calibration", "Calibration"),
            ("cleaning", "Cleaning"),
            ("lubrication", "Lubrication"),
            ("other", "Other"),
        ],
        default="inspection",
        required=True,
        tracking=True,
    )

    team_id = fields.Many2one("maintenance.team", string="Maintenance Team", tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="Assigned Technician",
        tracking=True,
    )
    supervisor_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        tracking=True,
    )

    frequency_basis = fields.Selection(
        [("time", "Time-based"), ("meter", "Meter-based")],
        default="time",
        required=True,
        tracking=True,
    )
    frequency_time = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("half_yearly", "Half-yearly"),
            ("yearly", "Yearly"),
            ("custom", "Custom"),
        ],
        default="monthly",
        tracking=True,
    )
    custom_interval_days = fields.Integer(default=30, tracking=True)

    meter_type = fields.Selection(
        [
            ("hours", "Running Hours"),
            ("km", "Kilometres"),
            ("cycles", "Cycles"),
        ],
        tracking=True,
    )
    meter_interval = fields.Float(tracking=True)
    last_meter_reading = fields.Float(string="Last Recorded Meter Reading", tracking=True)

    start_date = fields.Date(required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date(tracking=True)

    priority = fields.Selection(
        [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Very High")],
        default="1",
        required=True,
        tracking=True,
    )
    criticality = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        tracking=True,
    )

    duration_hours = fields.Float(string="Estimated Duration (hours)", default=2.0, tracking=True)
    reminder_before_days = fields.Integer(default=1, tracking=True)

    instruction = fields.Html(string="Maintenance Instructions")
    checklist_template_id = fields.Many2one(
        "pm.checklist.template", string="Checklist Template", ondelete="restrict", tracking=True
    )

    spare_part_ids = fields.Many2many("product.product", string="Expected Spare Parts / Materials")

    estimated_labour_cost = fields.Monetary(currency_field="currency_id", tracking=True)
    estimated_service_cost = fields.Monetary(currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "pm_plan_ir_attachment_rel",
        "plan_id",
        "attachment_id",
        string="Attachments",
    )

    auto_generate_work_orders = fields.Boolean(default=True, tracking=True)
    auto_next_schedule = fields.Boolean(default=True, tracking=True)
    mandatory_checklist = fields.Boolean(default=True, tracking=True)
    reminder_escalation_note = fields.Text(string="Reminder / Escalation Rules Notes")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("expired", "Expired"),
            ("review", "Under Review"),
        ],
        default="draft",
        tracking=True,
    )

    schedule_ids = fields.One2many("pm.schedule", "plan_id", string="Schedules")
    work_order_ids = fields.One2many("pm.work.order", "plan_id", string="Work Orders")

    next_schedule_date = fields.Date(
        string="Next Scheduled Date", compute="_compute_next_schedule_date", store=False
    )

    _sql_constraints = [
        (
            "pm_plan_meter_interval_positive",
            "CHECK(meter_interval IS NULL OR meter_interval > 0)",
            "Meter interval must be positive.",
        ),
    ]

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.end_date and rec.start_date and rec.end_date < rec.start_date:
                raise ValidationError("End date cannot be before start date.")

    @api.constrains("equipment_id", "asset_category_id")
    def _check_asset_scope(self):
        for rec in self:
            if not rec.equipment_id and not rec.asset_category_id:
                raise ValidationError("Define either an asset or an asset category for the PM plan.")

    @api.constrains("custom_interval_days", "frequency_time")
    def _check_custom_interval(self):
        for rec in self:
            if rec.frequency_time == "custom" and (not rec.custom_interval_days or rec.custom_interval_days < 1):
                raise ValidationError("Custom interval requires at least 1 day.")

    @api.constrains("frequency_basis", "meter_type", "meter_interval")
    def _check_meter(self):
        for rec in self:
            if rec.frequency_basis == "meter":
                if not rec.meter_type or not rec.meter_interval:
                    raise ValidationError("Meter-based plans require meter type and interval.")

    def _compute_next_schedule_date(self):
        Schedule = self.env["pm.schedule"]
        for plan in self:
            next_line = Schedule.search(
                [("plan_id", "=", plan.id), ("state", "in", ("scheduled", "due", "overdue", "rescheduled"))],
                order="date_planned asc",
                limit=1,
            )
            plan.next_schedule_date = next_line.date_planned if next_line else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", "New") == "New":
                seq = self.env["ir.sequence"].next_by_code("pm.plan") or "New"
                vals["reference"] = seq
        plans = super().create(vals_list)
        for plan in plans:
            plan._pm_audit_log("plan_create", f"PM Plan created: {plan.display_name}")
        return plans

    def write(self, vals):
        snapshots = {rec.id: rec.read()[0] for rec in self}
        res = super().write(vals)
        for rec in self:
            old = {k: snapshots[rec.id].get(k) for k in vals if k in snapshots[rec.id]}
            new = {k: rec[k] if k in rec._fields else None for k in vals}
            rec._pm_audit_log("plan_write", "PM Plan updated", old_vals=old, new_vals=new)
        return res

    def _add_months(self, d: date, months: int) -> date:
        return d + relativedelta(months=months)

    def _next_time_date(self, from_date: date) -> date:
        self.ensure_one()
        ft = self.frequency_time
        if ft == "daily":
            return from_date + timedelta(days=1)
        if ft == "weekly":
            return from_date + timedelta(weeks=1)
        if ft == "monthly":
            return self._add_months(from_date, 1)
        if ft == "quarterly":
            return self._add_months(from_date, 3)
        if ft == "half_yearly":
            return self._add_months(from_date, 6)
        if ft == "yearly":
            return self._add_months(from_date, 12)
        if ft == "custom":
            return from_date + timedelta(days=self.custom_interval_days or 30)
        return from_date + timedelta(days=30)

    def _get_lead_days(self):
        self.ensure_one()
        cfg = self.env["pm.configuration"].get_config()
        return self.reminder_before_days if self.reminder_before_days is not None else cfg.reminder_days

    def _due_date_from_planned(self, planned_date):
        self.ensure_one()
        lead = self._get_lead_days()
        return planned_date + timedelta(days=lead)

    def action_activate(self):
        for plan in self:
            if plan.state == "expired":
                raise UserError("Cannot activate an expired plan.")
            plan.state = "active"
            plan._pm_audit_log("plan_activate", "PM Plan activated")
            plan._generate_future_schedules()

    def action_deactivate(self):
        for plan in self:
            plan.state = "inactive"
            plan._pm_audit_log("plan_deactivate", "PM Plan deactivated")

    def action_set_review(self):
        self.write({"state": "review"})

    def action_set_draft(self):
        self.write({"state": "draft"})

    def action_duplicate_plan(self):
        self.ensure_one()
        new_plan = self.copy(
            {
                "name": f"{self.name} (Copy)",
                "reference": self.env["ir.sequence"].next_by_code("pm.plan"),
                "state": "draft",
            }
        )
        new_plan._pm_audit_log("plan_create", f"Duplicated from plan {self.reference}")
        return new_plan.id

    def _property_location_text(self, equipment=None):
        """Resolved property/site text for schedules and work orders."""
        self.ensure_one()
        if self.property_location and self.property_location.strip():
            return self.property_location.strip()
        eq = equipment or self.equipment_id
        if eq and getattr(eq, "location", None):
            loc = (eq.location or "").strip()
            return loc or False
        return False

    def _generate_future_schedules(self, horizon_months=12):
        """Generate scheduled lines from start_date up to horizon when active."""
        Schedule = self.env["pm.schedule"]
        Wo = self.env["pm.work.order"]
        Equipment = self.env["maintenance.equipment"]
        today = fields.Date.today()
        for plan in self:
            if plan.state != "active" or plan.frequency_basis != "time":
                continue
            start = max(plan.start_date, today)
            if plan.end_date and start > plan.end_date:
                continue
            equipments = (
                plan.equipment_id
                if plan.equipment_id
                else Equipment.search([("category_id", "=", plan.asset_category_id.id)])
            )
            if not equipments:
                continue
            existing_keys = set()
            for s in Schedule.search([("plan_id", "=", plan.id)]):
                existing_keys.add((s.date_planned, s.equipment_id.id))
            current = start
            end_horizon = today + relativedelta(months=horizon_months)
            if plan.end_date:
                end_horizon = min(end_horizon, plan.end_date)
            max_lines = 200
            count = 0
            while current <= end_horizon and count < max_lines:
                for eq in equipments:
                    if (current, eq.id) in existing_keys:
                        continue
                    if plan.auto_generate_work_orders:
                        sched = Schedule.create(
                            plan._prepare_schedule_vals(current, plan._due_date_from_planned(current), work_order=False, equipment=eq)
                        )
                        wo = Wo.create(
                            plan._prepare_work_order_vals(
                                current, plan._due_date_from_planned(current), schedule=sched, equipment=eq
                            )
                        )
                        sched.write({"work_order_id": wo.id})
                    else:
                        Schedule.create(
                            plan._prepare_schedule_vals(
                                current, plan._due_date_from_planned(current), work_order=False, equipment=eq
                            )
                        )
                    existing_keys.add((current, eq.id))
                    count += 1
                    if count >= max_lines:
                        break
                if count >= max_lines:
                    break
                current = plan._next_time_date(current)
                if plan.end_date and current > plan.end_date:
                    break
            plan._pm_audit_log("schedule_generate", "Schedules/work orders generated from plan")

    def _prepare_schedule_vals(self, date_planned, date_due, work_order=None, equipment=None):
        self.ensure_one()
        equip = equipment or self.equipment_id
        vals = {
            "plan_id": self.id,
            "equipment_id": equip.id,
            "property_location": self._property_location_text(equipment=equip),
            "date_planned": date_planned,
            "date_due": date_due,
            "original_date_planned": date_planned,
            "duration_expected": self.duration_hours,
            "state": "scheduled",
            "company_id": self.company_id.id,
        }
        if work_order:
            vals["work_order_id"] = work_order.id
        return vals

    def _prepare_work_order_vals(self, date_scheduled, date_due, schedule=None, equipment=None):
        self.ensure_one()
        equip = equipment or self.equipment_id
        return {
            "name": self.env["ir.sequence"].next_by_code("pm.work.order") or "New",
            "plan_id": self.id,
            "schedule_id": schedule.id if schedule else False,
            "equipment_id": equip.id,
            "property_location": self._property_location_text(equipment=equip),
            "maintenance_type": self.maintenance_type,
            "team_id": self.team_id.id,
            "user_id": self.user_id.id,
            "supervisor_id": self.supervisor_id.id if self.supervisor_id else False,
            "date_scheduled": date_scheduled,
            "date_due": date_due,
            "priority": self.priority,
            "duration_planned": self.duration_hours,
            "state": "assigned" if self.user_id else "scheduled",
            "company_id": self.company_id.id,
            "mandatory_checklist": self.mandatory_checklist,
            "checklist_template_id": self.checklist_template_id.id,
            "instruction_snapshot": self.instruction or False,
        }

    def cron_expire_plans(self):
        today = fields.Date.today()
        plans = self.search([("state", "=", "active"), ("end_date", "!=", False), ("end_date", "<", today)])
        plans.write({"state": "expired"})

    def cron_generate_schedules(self):
        active = self.search([("state", "=", "active"), ("frequency_basis", "=", "time")])
        for plan in active:
            plan._generate_future_schedules()

    def action_refresh_schedules(self):
        """Generate/refresh schedule lines and work orders for active time-based plans."""
        self.cron_generate_schedules()
        return True
