# Part of Preventive Maintenance Management.

from odoo import api, fields, models

from .pm_access import pm_is_manager


class PmConfiguration(models.Model):
    _name = "pm.configuration"
    _description = "PM Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin", "pm.audit.mixin"]

    name = fields.Char(default="PM Configuration", required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    default_lead_days = fields.Integer(
        string="Default Lead Time (days)", default=3, tracking=True
    )
    default_task_duration = fields.Float(
        string="Default Task Duration (hours)", default=2.0, tracking=True
    )
    reminder_days = fields.Integer(string="Reminder Before Due (days)", default=1, tracking=True)
    escalation_overdue_days = fields.Integer(
        string="Overdue Escalation After (days)", default=1, tracking=True
    )

    sequence_prefix_wo = fields.Char(string="Work Order Prefix", default="PM/WO/", tracking=True)
    sequence_padding_wo = fields.Integer(default=5)

    mandatory_checklist_default = fields.Boolean(
        string="Mandatory Checklist by Default", default=True
    )
    auto_generate_wo_default = fields.Boolean(
        string="Auto-generate Work Orders by Default", default=True
    )
    auto_next_schedule_default = fields.Boolean(
        string="Auto Next Schedule by Default", default=True
    )

    notification_email = fields.Boolean(string="Email Notifications", default=True)
    notification_activity = fields.Boolean(string="Activity Notifications", default=True)
    notification_sms = fields.Boolean(string="SMS Notifications", default=False)
    notify_on_schedule = fields.Boolean(string="Notify on New Schedule", default=True)
    notify_on_overdue = fields.Boolean(string="Notify on Overdue", default=True)
    notify_on_completion = fields.Boolean(string="Notify on Completion", default=True)

    overdue_grace_days = fields.Integer(
        string="Overdue Grace Period (days)", default=0, tracking=True,
        help="Days after due date before a work order is marked overdue.",
    )

    escalation_rule_ids = fields.One2many(
        "pm.escalation.rule", "configuration_id", string="Escalation Rules"
    )
    escalation_matrix_notes = fields.Text(string="Escalation Matrix Notes")

    _sql_constraints = [
        ("pm_configuration_company_uniq", "unique(company_id)", "Only one PM configuration per company."),
    ]

    @api.model
    def get_config(self):
        """Return singleton configuration for current company (auto-created)."""
        company = self.env.company
        cfg = self.search([("company_id", "=", company.id)], limit=1)
        if not cfg:
            cfg = self.create(
                {
                    "name": "PM Configuration",
                    "company_id": company.id,
                }
            )
        return cfg

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if not pm_is_manager(self.env):
                continue
            rec._pm_audit_log("configuration_update", "PM configuration updated", new_vals=vals)
        return res
