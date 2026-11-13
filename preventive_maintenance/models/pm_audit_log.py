# Part of Preventive Maintenance Management.

from odoo import fields, models


class PmAuditLog(models.Model):
    _name = "pm.audit.log"
    _description = "PM Audit Log"
    _order = "create_date desc"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one("res.users", string="User", required=True, default=lambda self: self.env.user)
    res_model = fields.Char(string="Resource Model", index=True)
    res_id = fields.Integer(string="Resource ID", index=True)
    action_type = fields.Selection(
        selection=[
            ("plan_create", "Plan Created"),
            ("plan_write", "Plan Updated"),
            ("plan_activate", "Plan Activated"),
            ("plan_deactivate", "Plan Deactivated"),
            ("schedule_reschedule", "Schedule Rescheduled"),
            ("schedule_generate", "Schedule Generated"),
            ("wo_assign", "Work Order Assignment"),
            ("wo_state", "Work Order State Change"),
            ("wo_skip", "Work Order Skipped"),
            ("wo_cancel", "Work Order Cancelled"),
            ("inspection", "Inspection"),
            ("configuration_update", "Configuration Update"),
            ("other", "Other"),
        ],
        required=True,
    )
    details = fields.Text()
    value_before = fields.Text()
    value_after = fields.Text()
