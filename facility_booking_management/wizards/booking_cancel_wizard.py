# -*- coding: utf-8 -*-
from odoo import fields, models


class FacilityBookingCancelWizard(models.TransientModel):
    _name = "facility.booking.cancel.wizard"
    _description = "Cancel Facility Booking"

    booking_id = fields.Many2one("facility.booking", required=True)
    reason = fields.Text(string="Cancellation Reason")

    def action_confirm_cancel(self):
        self.booking_id.action_cancel(self.reason)
        return {"type": "ir.actions.act_window_close"}
