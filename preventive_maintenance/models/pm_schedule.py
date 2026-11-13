# Part of Preventive Maintenance Management.

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .pm_access import pm_is_manager


class PmSchedule(models.Model):
    _name = "pm.schedule"
    _description = "PM Schedule Line"
    _inherit = ["mail.thread", "pm.audit.mixin"]
    _order = "date_planned desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    plan_id = fields.Many2one("pm.plan", required=True, ondelete="cascade", index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Asset", required=True, ondelete="restrict", index=True
    )
    property_location = fields.Char(string="Property / Location")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    date_planned = fields.Date(required=True, index=True)
    original_date_planned = fields.Date(required=True)
    date_due = fields.Date(required=True)

    duration_expected = fields.Float(string="Expected Duration (hours)")

    work_order_id = fields.Many2one("pm.work.order", string="Work Order", ondelete="set null")

    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("due", "Due"),
            ("overdue", "Overdue"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("skipped", "Skipped"),
            ("rescheduled", "Rescheduled"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
        required=True,
        index=True,
    )

    rescheduling_reason = fields.Text()
    reschedule_history_ids = fields.One2many(
        "pm.schedule.reschedule", "schedule_id", string="Reschedule History"
    )

    @api.depends("plan_id", "date_planned")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.plan_id.reference or rec.plan_id.name} — {rec.date_planned or ''}"

    def _sync_work_order_state(self, target_state):
        for rec in self:
            if rec.work_order_id and rec.work_order_id.state in (
                "scheduled",
                "assigned",
                "in_progress",
                "on_hold",
                "pending_inspection",
                "rework",
            ):
                # Schedule line mirrors terminal WO states when closed
                if target_state == "completed":
                    rec.state = "completed"
                elif target_state == "skipped":
                    rec.state = "skipped"
                elif target_state == "cancelled":
                    rec.state = "cancelled"

    @api.model
    def cron_update_schedule_states(self):
        """Set due/overdue from dates."""
        today = fields.Date.today()
        lines = self.search(
            [
                ("state", "in", ("scheduled", "due", "overdue", "rescheduled")),
            ]
        )
        for line in lines:
            if line.work_order_id and line.work_order_id.state == "in_progress":
                line.state = "in_progress"
                continue
            if line.date_due < today and line.state not in ("completed", "skipped", "cancelled"):
                line.state = "overdue"
            elif line.date_planned <= today <= line.date_due and line.state in (
                "scheduled",
                "rescheduled",
            ):
                line.state = "due"

    def action_open_work_order(self):
        self.ensure_one()
        if not self.work_order_id:
            raise UserError("No work order linked to this schedule line.")
        return {
            "type": "ir.actions.client",
            "tag": "preventive_maintenance_pm_app",
            "params": {"screen": "execution", "workOrderId": self.work_order_id.id},
        }

    def action_reschedule(self, new_date, reason):
        if not pm_is_manager(self.env):
            raise AccessError("Only Maintenance Managers can reschedule.")
        self.ensure_one()
        old = self.date_planned
        plan = self.plan_id
        new_due = plan._due_date_from_planned(new_date)
        self.write(
            {
                "date_planned": new_date,
                "date_due": new_due,
                "state": "rescheduled",
                "rescheduling_reason": reason,
            }
        )
        self.env["pm.schedule.reschedule"].create(
            {
                "schedule_id": self.id,
                "date_from": old,
                "date_to": new_date,
                "reason": reason,
                "user_id": self.env.user.id,
            }
        )
        if self.work_order_id:
            self.work_order_id.write({"date_scheduled": new_date, "date_due": new_due})
        self._pm_audit_log(
            "schedule_reschedule",
            f"Rescheduled from {old} to {new_date}",
            res_model="pm.schedule",
            res_id=self.id,
            old_vals={"date_planned": str(old)},
            new_vals={"date_planned": str(new_date), "reason": reason},
        )


class PmScheduleReschedule(models.Model):
    _name = "pm.schedule.reschedule"
    _description = "PM Schedule Reschedule History"
    _order = "create_date desc"

    schedule_id = fields.Many2one("pm.schedule", required=True, ondelete="cascade")
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    reason = fields.Text(required=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
