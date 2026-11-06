# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FacilityBookingNotification(models.Model):
    _name = "facility.booking.notification"
    _description = "Facility Booking Notification"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    message = fields.Text(required=True)
    booking_id = fields.Many2one("facility.booking", ondelete="cascade", index=True)
    resident_id = fields.Many2one("fms.resident", index=True)
    user_id = fields.Many2one("res.users", index=True)
    category = fields.Selection(
        [
            ("booking", "Bookings"),
            ("approval", "Approvals"),
            ("cancellation", "Cancellations"),
            ("alert", "Alerts"),
            ("system", "System"),
        ],
        default="booking",
    )
    notification_type = fields.Selection(
        [
            ("booking_confirmation", "Booking Confirmation"),
            ("approval_pending", "Approval Pending"),
            ("booking_approved", "Booking Approved"),
            ("booking_rejected", "Booking Rejected"),
            ("booking_cancelled", "Booking Cancelled"),
            ("booking_reminder", "Booking Reminder"),
            ("payment_alert", "Payment Alert"),
            ("facility_alert", "Facility Alert"),
        ],
        required=True,
    )
    is_read = fields.Boolean(default=False, index=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model
    def create_notification(self, booking, notification_type, message):
        category_map = {
            "booking_confirmation": "booking",
            "approval_pending": "approval",
            "booking_approved": "approval",
            "booking_rejected": "approval",
            "booking_cancelled": "cancellation",
            "booking_reminder": "booking",
            "payment_alert": "alert",
            "facility_alert": "alert",
        }
        title_map = {
            "booking_confirmation": _("Booking Confirmed"),
            "approval_pending": _("Approval Pending"),
            "booking_approved": _("Booking Approved"),
            "booking_rejected": _("Booking Rejected"),
            "booking_cancelled": _("Booking Cancelled"),
            "booking_reminder": _("Booking Reminder"),
            "payment_alert": _("Payment Alert"),
            "facility_alert": _("Facility Alert"),
        }
        vals = {
            "name": title_map.get(notification_type, _("Notification")),
            "message": message,
            "booking_id": booking.id if booking else False,
            "resident_id": booking.resident_id.id if booking and booking.resident_id else False,
            "user_id": booking.resident_id.user_id.id
            if booking and booking.resident_id and booking.resident_id.user_id
            else False,
            "notification_type": notification_type,
            "category": category_map.get(notification_type, "system"),
        }
        return self.create(vals)

    @api.model
    def get_notifications(self, category=None, unread_only=False, search=None, limit=100):
        domain = []
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            resident = self.env["fms.resident"].get_resident_for_current_user()
            domain += ["|", ("user_id", "=", self.env.uid), ("resident_id", "=", resident.id if resident else 0)]
        if category and category != "all":
            if category == "unread":
                domain.append(("is_read", "=", False))
            else:
                domain.append(("category", "=", category))
        if unread_only:
            domain.append(("is_read", "=", False))
        if search:
            domain += ["|", ("name", "ilike", search), ("message", "ilike", search)]
        records = self.search(domain, limit=limit)
        return [
            {
                "id": r.id,
                "name": r.name,
                "message": r.message,
                "category": r.category,
                "notification_type": r.notification_type,
                "is_read": r.is_read,
                "booking_id": r.booking_id.id,
                "create_date": r.create_date,
            }
            for r in records
        ]

    def action_mark_read(self):
        self.write({"is_read": True})

    @api.model
    def action_mark_all_read(self):
        domain = []
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            resident = self.env["fms.resident"].get_resident_for_current_user()
            domain += ["|", ("user_id", "=", self.env.uid), ("resident_id", "=", resident.id if resident else 0)]
        self.search(domain + [("is_read", "=", False)]).write({"is_read": True})
