# -*- coding: utf-8 -*-
from odoo import fields, models


class FacilityApprovalHistory(models.Model):
    _name = "facility.approval.history"
    _description = "Facility Booking Approval History"
    _order = "action_date desc, id desc"

    booking_id = fields.Many2one("facility.booking", required=True, ondelete="cascade", index=True)
    approver_id = fields.Many2one("res.users", required=True)
    action = fields.Selection(
        [("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")],
        required=True,
    )
    action_date = fields.Datetime(default=fields.Datetime.now, required=True)
    comment = fields.Text()
    previous_status = fields.Char()
    new_status = fields.Char()
