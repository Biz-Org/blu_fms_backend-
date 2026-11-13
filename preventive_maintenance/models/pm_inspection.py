# Part of Preventive Maintenance Management.

from odoo import fields, models


class PmInspection(models.Model):
    _name = "pm.inspection"
    _description = "PM Work Order Inspection"
    _inherit = ["mail.thread", "pm.audit.mixin"]

    work_order_id = fields.Many2one(
        "pm.work.order", required=True, ondelete="cascade", index=True
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
    )
    inspection_remarks = fields.Text()
    reviewer_id = fields.Many2one("res.users", string="Reviewed By")
    review_date = fields.Datetime()
