# Part of Preventive Maintenance Management.

from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    pm_work_order_id = fields.Many2one(
        "pm.work.order",
        string="PM Work Order",
        ondelete="set null",
        index=True,
    )
    issue_category = fields.Selection(
        [
            ("mechanical", "Mechanical"),
            ("electrical", "Electrical"),
            ("plumbing", "Plumbing"),
            ("hvac", "HVAC"),
            ("safety", "Safety"),
            ("other", "Other"),
        ],
        string="Issue Category",
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
    )
