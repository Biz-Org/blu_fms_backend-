# -*- coding: utf-8 -*-
from odoo import fields, models


class FacilityBookingRejectWizard(models.TransientModel):
    _name = "facility.booking.reject.wizard"
    _description = "Reject Facility Booking"

    booking_id = fields.Many2one("facility.booking", required=True)
    comment = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_reject(self):
        self.booking_id.action_reject(self.comment)
        return {"type": "ir.actions.act_window_close"}
