# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError


class FacilityBookingPayment(models.Model):
    _inherit = "facility.booking"

    def action_confirm_payment(self, amount, payment_method, transaction_id=None):
        self._check_manager_access()
        for rec in self:
            if rec.payment_status == "free":
                raise UserError(_("This booking does not require payment."))
            if amount <= 0:
                raise UserError(_("Payment amount must be positive."))
            rec.paid_amount = (rec.paid_amount or 0) + amount
            rec.payment_method = payment_method
            if transaction_id:
                rec.transaction_id = transaction_id
            if rec.paid_amount >= rec.total_amount:
                rec.payment_status = "paid"
                if rec.approval_status in ("approved", "not_required"):
                    rec.booking_status = "confirmed"
                self.env["facility.booking.notification"].create_notification(
                    rec, "booking_confirmation", _("Payment received. Booking confirmed.")
                )
            else:
                rec.payment_status = "partial"


class FacilityBookingConfigPayment(models.Model):
    _inherit = "facility.booking.config"

    @api.model
    def get_payment_summary(self, property_id=None):
        domain = []
        if property_id:
            domain.append(("property_id", "=", property_id))
        bookings = self.env["facility.booking"].search(domain)
        return {
            "total_collections": sum(bookings.mapped("paid_amount")),
            "paid_bookings": len(bookings.filtered(lambda b: b.payment_status == "paid")),
            "pending_payments": len(bookings.filtered(lambda b: b.payment_status == "pending")),
            "overdue_payments": len(bookings.filtered(lambda b: b.payment_status == "overdue")),
            "refunds": len(bookings.filtered(lambda b: b.payment_status == "refunded")),
            "records": [
                b._serialize_booking()
                for b in bookings.filtered(lambda b: b.total_amount or b.payment_status != "free")
            ],
        }
