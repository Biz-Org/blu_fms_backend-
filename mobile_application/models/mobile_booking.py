# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import BOOKING_STATES


class MobileBooking(models.Model):
    _name = "mobile.booking"
    _description = "Mobile Amenity Booking"
    _order = "booking_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    amenity_name = fields.Char(required=True)
    booking_date = fields.Date(required=True, index=True)
    slot_label = fields.Char(required=True)
    state = fields.Selection(BOOKING_STATES, default="requested", required=True, index=True)
    notes = fields.Text()
    idempotency_key = fields.Char(index=True)
    external_model = fields.Char(index=True)
    external_id = fields.Integer(index=True)

    _sql_constraints = [
        (
            "idempotency_uniq",
            "unique(idempotency_key)",
            "This booking was already submitted.",
        ),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.env["mobile.application.notification"].sudo().create({
                "user_id": record.user_id.id,
                "title": _("Booking requested"),
                "message": _("Your booking for %s is %s.") % (record.amenity_name, record.state),
                "notification_type": "booking",
                "res_model": record._name,
                "res_id": record.id,
                "action_route": "bookings",
            })
        return records

    def action_cancel(self):
        self.ensure_one()
        if self.user_id != self.env.user:
            raise AccessError(_("You can only cancel your own bookings."))
        if self.state in ("cancelled", "completed"):
            raise UserError(_("This booking cannot be cancelled."))
        self.write({"state": "cancelled"})
