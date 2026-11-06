# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

ACTIVE_BOOKING_STATUSES = (
    "pending_approval",
    "payment_pending",
    "confirmed",
)


class FacilityBooking(models.Model):
    _name = "facility.booking"
    _description = "Facility Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "booking_date desc, start_time desc, id desc"

    name = fields.Char(
        string="Booking ID",
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
    )
    facility_id = fields.Many2one("facility.facility", required=True, ondelete="restrict", tracking=True)
    property_id = fields.Many2one("fms.property", string="Property", ondelete="set null")
    resident_id = fields.Many2one("fms.resident", string="Requester", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Contact")
    contact_phone = fields.Char(string="Contact Number")
    contact_email = fields.Char(string="Email")
    booking_date = fields.Date(required=True, tracking=True, index=True)
    start_time = fields.Float(required=True)
    end_time = fields.Float(required=True)
    guest_count = fields.Integer(string="Guests", default=1)
    booking_type = fields.Selection(
        related="facility_id.booking_type",
        store=True,
        readonly=True,
    )
    purpose = fields.Char(string="Booking Purpose")
    special_requirements = fields.Text(string="Additional Requirements")
    attachment_ids = fields.Many2many("ir.attachment", string="Supporting Documents")

    base_charge = fields.Monetary(currency_field="currency_id")
    additional_charge = fields.Monetary(string="Additional Charges", currency_field="currency_id")
    tax_amount = fields.Monetary(string="Tax", currency_field="currency_id")
    discount_amount = fields.Monetary(string="Discount", currency_field="currency_id")
    total_amount = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    paid_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    payment_status = fields.Selection(
        [
            ("free", "Free"),
            ("pending", "Pending"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
            ("refunded", "Refunded"),
        ],
        default="pending",
        tracking=True,
    )
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank", "Bank Transfer"),
            ("online", "Online"),
            ("other", "Other"),
        ],
    )
    transaction_id = fields.Char(string="Transaction ID")

    approval_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="not_required",
        tracking=True,
    )
    booking_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("payment_pending", "Payment Pending"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
            ("rejected", "Rejected"),
            ("completed", "Completed"),
            ("expired", "Expired"),
        ],
        default="draft",
        tracking=True,
        index=True,
    )
    approver_id = fields.Many2one("res.users", string="Approver", readonly=True)
    approval_date = fields.Datetime(readonly=True)
    approval_comment = fields.Text(string="Approval Comments")
    cancellation_reason = fields.Text()
    priority = fields.Selection(
        [("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")],
        default="normal",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    approval_history_ids = fields.One2many("facility.approval.history", "booking_id")
    notification_ids = fields.One2many("facility.booking.notification", "booking_id")

    @api.depends("base_charge", "additional_charge", "tax_amount", "discount_amount")
    def _compute_amounts(self):
        for rec in self:
            rec.total_amount = (
                (rec.base_charge or 0)
                + (rec.additional_charge or 0)
                + (rec.tax_amount or 0)
                - (rec.discount_amount or 0)
            )

    @api.model
    def _times_overlap(self, start_a, end_a, start_b, end_b):
        return start_a < end_b and end_a > start_b

    @api.constrains("booking_date", "start_time", "end_time", "facility_id", "booking_status")
    def _check_no_double_booking(self):
        for rec in self:
            if rec.booking_status not in ACTIVE_BOOKING_STATUSES:
                continue
            if rec.end_time <= rec.start_time:
                raise ValidationError(_("End time must be after start time."))
            domain = [
                ("id", "!=", rec.id),
                ("facility_id", "=", rec.facility_id.id),
                ("booking_date", "=", rec.booking_date),
                ("booking_status", "in", ACTIVE_BOOKING_STATUSES),
            ]
            others = self.search(domain)
            for other in others:
                if self._times_overlap(rec.start_time, rec.end_time, other.start_time, other.end_time):
                    raise ValidationError(
                        _("This facility is already booked for the selected time slot (%s).")
                        % other.name
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("facility.booking") or _("New")
        records = super().create(vals_list)
        for rec in records:
            rec._apply_charges_from_facility()
            rec._validate_booking_rules()
            rec._set_initial_workflow_state()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("booking_date", "start_time", "end_time", "facility_id", "guest_count")):
            for rec in self:
                rec._validate_booking_rules()
        return res

    def _apply_charges_from_facility(self):
        for rec in self:
            facility = rec.facility_id
            if facility.charge_type == "free":
                rec.base_charge = 0
                rec.additional_charge = 0
                rec.payment_status = "free"
            else:
                rec.base_charge = facility.base_charge
                rec.additional_charge = (
                    (facility.cleaning_charge or 0)
                    + (facility.security_charge or 0)
                    + (facility.additional_service_charge or 0)
                )
                config = self.env["facility.booking.config"].get_config()
                if config.default_tax_percent:
                    taxable = (rec.base_charge or 0) + (rec.additional_charge or 0)
                    rec.tax_amount = taxable * (config.default_tax_percent / 100.0)

    def _validate_booking_rules(self):
        self.ensure_one()
        config = self.env["facility.booking.config"].get_config()
        facility = self.facility_id
        today = fields.Date.context_today(self)

        if not facility.active or facility.booking_status == "closed":
            raise ValidationError(_("This facility is not available for booking."))
        if self.guest_count > facility.capacity:
            raise ValidationError(_("Guest count exceeds facility capacity (%s).") % facility.capacity)
        if self.guest_count > config.max_guests:
            raise ValidationError(_("Guest count exceeds configured maximum (%s).") % config.max_guests)

        max_advance = today + timedelta(days=config.advance_booking_days)
        if self.booking_date > max_advance:
            raise ValidationError(_("Booking exceeds advance booking limit."))
        if self.booking_date < today:
            raise ValidationError(_("Booking date cannot be in the past."))

        duration = self.end_time - self.start_time
        if duration < config.min_booking_duration:
            raise ValidationError(_("Booking duration is below the minimum allowed."))
        if duration > config.max_booking_duration:
            raise ValidationError(_("Booking duration exceeds the maximum allowed."))

        slot_config = self.env["facility.slot.config"].get_active_config(facility, self.booking_date)
        if not slot_config:
            raise ValidationError(_("Facility is closed on the selected date."))
        if self.start_time < slot_config.opening_time or self.end_time > slot_config.closing_time:
            raise ValidationError(_("Selected time is outside operating hours."))

        if self.env["facility.block"].is_blocked(
            facility.id, self.booking_date, self.start_time, self.end_time
        ):
            raise ValidationError(_("Facility is blocked for the selected period."))

        if not config.allow_back_to_back:
            buffer = config.buffer_time or slot_config.buffer_time or 0
            domain = [
                ("id", "!=", self.id),
                ("facility_id", "=", facility.id),
                ("booking_date", "=", self.booking_date),
                ("booking_status", "in", ACTIVE_BOOKING_STATUSES),
            ]
            for other in self.search(domain):
                if self._times_overlap(
                    self.start_time - buffer,
                    self.end_time + buffer,
                    other.start_time,
                    other.end_time,
                ):
                    raise ValidationError(_("Booking violates buffer / back-to-back rules."))

    def _set_initial_workflow_state(self):
        Notification = self.env["facility.booking.notification"]
        for rec in self:
            facility = rec.facility_id
            config = self.env["facility.booking.config"].get_config()
            needs_approval = facility.approval_required or (
                config.approval_amount_threshold
                and rec.total_amount >= config.approval_amount_threshold
            )
            if config.auto_approval and not facility.approval_required:
                needs_approval = False

            if needs_approval:
                rec.write(
                    {
                        "approval_status": "pending",
                        "booking_status": "pending_approval",
                    }
                )
                Notification.create_notification(
                    rec, "approval_pending", _("Your booking is waiting for approval.")
                )
            elif facility.charge_type == "paid" and rec.total_amount > 0:
                rec.write({"booking_status": "payment_pending", "payment_status": "pending"})
                Notification.create_notification(rec, "payment_alert", _("Payment is pending for your booking."))
            else:
                rec.write({"booking_status": "confirmed", "payment_status": rec.payment_status or "free"})
                Notification.create_notification(
                    rec, "booking_confirmation", _("Your booking for %s has been confirmed.") % facility.name
                )

    def action_approve(self, comment=None):
        self._check_approver_access()
        for rec in self:
            if rec.approval_status != "pending":
                raise UserError(_("Only pending bookings can be approved."))
            rec.write(
                {
                    "approval_status": "approved",
                    "approver_id": self.env.uid,
                    "approval_date": fields.Datetime.now(),
                    "approval_comment": comment,
                }
            )
            rec._log_approval("approved", comment)
            if rec.facility_id.charge_type == "paid" and rec.total_amount > rec.paid_amount:
                rec.booking_status = "payment_pending"
            else:
                rec.booking_status = "confirmed"
            self.env["facility.booking.notification"].create_notification(
                rec, "booking_approved", _("Your booking has been approved.")
            )

    def action_reject(self, comment):
        self._check_approver_access()
        if not comment:
            raise UserError(_("Rejection reason is required."))
        for rec in self:
            if rec.approval_status != "pending":
                raise UserError(_("Only pending bookings can be rejected."))
            rec.write(
                {
                    "approval_status": "rejected",
                    "booking_status": "rejected",
                    "approver_id": self.env.uid,
                    "approval_date": fields.Datetime.now(),
                    "approval_comment": comment,
                }
            )
            rec._log_approval("rejected", comment)
            self.env["facility.booking.notification"].create_notification(
                rec, "booking_rejected", _("Your booking has been rejected.")
            )

    def action_cancel(self, reason=None):
        for rec in self:
            rec._check_cancel_access()
            config = self.env["facility.booking.config"].get_config()
            rec._apply_cancellation_penalty(config)
            rec.write(
                {
                    "booking_status": "cancelled",
                    "cancellation_reason": reason,
                }
            )
            self.env["facility.booking.notification"].create_notification(
                rec, "booking_cancelled", _("Your booking has been cancelled.")
            )

    def action_reschedule(self, booking_date, start_time, end_time):
        self.ensure_one()
        config = self.env["facility.booking.config"].get_config()
        if not config.allow_rescheduling and not self.env.user.has_group(
            "facility_booking_management.group_facility_manager"
        ):
            raise UserError(_("Rescheduling is not allowed by current policy."))
        self.write(
            {
                "booking_date": booking_date,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        return self._serialize_booking()

    def _apply_cancellation_penalty(self, config):
        self.ensure_one()
        if not self.booking_date:
            return
        hours_before = (
            datetime.combine(self.booking_date, datetime.min.time())
            - datetime.combine(fields.Date.context_today(self), datetime.min.time())
        ).total_seconds() / 3600.0
        free_hours = config.free_cancellation_hours
        if hours_before >= free_hours:
            return
        if config.cancellation_penalty_percent and self.paid_amount:
            penalty = self.paid_amount * (config.cancellation_penalty_percent / 100.0)
            refund = self.paid_amount - penalty
            if refund > 0 and config.refund_percent:
                refund = refund * (config.refund_percent / 100.0)
            self.paid_amount = max(self.paid_amount - refund, 0)

    def _log_approval(self, action, comment):
        self.ensure_one()
        self.env["facility.approval.history"].create(
            {
                "booking_id": self.id,
                "approver_id": self.env.uid,
                "action": action,
                "comment": comment,
                "previous_status": "pending",
                "new_status": "approved" if action == "approved" else "rejected",
            }
        )

    def _check_approver_access(self):
        if not (
            self.env.user.has_group("facility_booking_management.group_facility_approver")
            or self.env.user.has_group("facility_booking_management.group_facility_manager")
        ):
            raise AccessError(_("You are not allowed to approve or reject bookings."))

    def _check_manager_access(self):
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            raise AccessError(_("Only facility managers can perform this action."))

    def _check_cancel_access(self):
        self.ensure_one()
        if self.env.user.has_group("facility_booking_management.group_facility_manager"):
            return
        resident = self.env["fms.resident"].get_resident_for_current_user()
        if resident and self.resident_id == resident:
            return
        raise AccessError(_("You cannot cancel this booking."))

    def _serialize_booking(self):
        self.ensure_one()
        Facility = self.env["facility.facility"]
        return {
            "id": self.id,
            "name": self.name,
            "facility_id": self.facility_id.id,
            "facility_name": self.facility_id.name,
            "property_id": self.property_id.id,
            "property_name": self.property_id.name,
            "resident_id": self.resident_id.id,
            "resident_name": self.resident_id.name,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "booking_date": str(self.booking_date),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_label": Facility._float_to_time_str(self.start_time),
            "end_label": Facility._float_to_time_str(self.end_time),
            "guest_count": self.guest_count,
            "purpose": self.purpose,
            "special_requirements": self.special_requirements,
            "base_charge": self.base_charge,
            "additional_charge": self.additional_charge,
            "tax_amount": self.tax_amount,
            "discount_amount": self.discount_amount,
            "total_amount": self.total_amount,
            "paid_amount": self.paid_amount,
            "payment_status": self.payment_status,
            "payment_method": self.payment_method,
            "transaction_id": self.transaction_id,
            "approval_status": self.approval_status,
            "booking_status": self.booking_status,
            "approver_name": self.approver_id.name,
            "approval_date": self.approval_date,
            "approval_comment": self.approval_comment,
            "cancellation_reason": self.cancellation_reason,
            "priority": self.priority,
        }

    @api.model
    def search_bookings(self, domain=None, limit=80, offset=0, order="booking_date desc, id desc"):
        domain = domain or []
        bookings = self.search(domain, limit=limit, offset=offset, order=order)
        return {
            "records": [b._serialize_booking() for b in bookings],
            "total": self.search_count(domain),
        }

    @api.model
    def create_booking_from_ui(self, values):
        resident = self.env["fms.resident"].get_resident_for_current_user()
        if resident and not values.get("resident_id"):
            values["resident_id"] = resident.id
        if resident and not values.get("property_id") and resident.property_id:
            values["property_id"] = resident.property_id.id
        booking = self.create(values)
        return booking._serialize_booking()

    @api.model
    def get_dashboard_data(self, property_id=None, date_from=None, date_to=None):
        today = fields.Date.context_today(self)
        date_from = date_from or today
        date_to = date_to or today

        facility_domain = []
        if property_id:
            facility_domain.append(("property_id", "=", property_id))
        facilities = self.env["facility.facility"].search(facility_domain)
        booking_domain = [
            ("booking_date", ">=", date_from),
            ("booking_date", "<=", date_to),
        ]
        if property_id:
            booking_domain.append(("property_id", "=", property_id))

        all_bookings = self.search(booking_domain)
        today_bookings = self.search([("booking_date", "=", today)] + (booking_domain[2:] if property_id else []))
        pending = self.search(
            [("approval_status", "=", "pending"), ("booking_status", "=", "pending_approval")]
            + (booking_domain[2:] if property_id else [])
        )
        confirmed = all_bookings.filtered(lambda b: b.booking_status == "confirmed")
        revenue = sum(confirmed.mapped("paid_amount"))

        total_slots = 0
        booked_slots = 0
        for facility in facilities:
            config = self.env["facility.slot.config"].get_active_config(facility, today)
            if config:
                slots = config.generate_slot_lines(today)
                total_slots += len(slots)
                booked_slots += len([s for s in slots if s["status"] == "booked"])
        utilization = (booked_slots / total_slots * 100) if total_slots else 0

        upcoming = self.search(
            [
                ("booking_date", ">=", today),
                ("booking_status", "in", ACTIVE_BOOKING_STATUSES),
            ]
            + (booking_domain[2:] if property_id else []),
            limit=10,
            order="booking_date asc, start_time asc",
        )

        status_summary = {}
        for key in dict(self._fields["booking_status"].selection):
            status_summary[key] = len(all_bookings.filtered(lambda b: b.booking_status == key))

        alerts = self.env["facility.booking.notification"].search(
            [("is_read", "=", False)], limit=5, order="create_date desc"
        )

        return {
            "kpis": {
                "total_facilities": len(facilities),
                "active_facilities": len(facilities.filtered(lambda f: f.active)),
                "inactive_facilities": len(facilities.filtered(lambda f: not f.active)),
                "today_bookings": len(today_bookings),
                "pending_approvals": len(pending),
                "utilization_percent": round(utilization, 1),
                "booking_revenue": revenue,
            },
            "upcoming_bookings": [b._serialize_booking() for b in upcoming],
            "status_summary": status_summary,
            "alerts": [
                {
                    "id": a.id,
                    "title": a.name,
                    "message": a.message,
                    "category": a.category,
                    "is_read": a.is_read,
                }
                for a in alerts
            ],
        }

    @api.model
    def get_reports_data(self, date_from=None, date_to=None, facility_id=None, property_id=None):
        today = fields.Date.context_today(self)
        date_from = date_from or (today - timedelta(days=30))
        date_to = date_to or today
        domain = [("booking_date", ">=", date_from), ("booking_date", "<=", date_to)]
        if facility_id:
            domain.append(("facility_id", "=", facility_id))
        if property_id:
            domain.append(("property_id", "=", property_id))
        bookings = self.search(domain)
        by_facility = {}
        for b in bookings:
            key = b.facility_id.name
            by_facility.setdefault(key, {"count": 0, "revenue": 0})
            by_facility[key]["count"] += 1
            by_facility[key]["revenue"] += b.paid_amount or 0
        cancelled = len(bookings.filtered(lambda b: b.booking_status == "cancelled"))
        return {
            "total_bookings": len(bookings),
            "total_revenue": sum(bookings.mapped("paid_amount")),
            "pending_amount": sum(
                bookings.filtered(lambda b: b.payment_status == "pending").mapped("total_amount")
            ),
            "refunds": sum(bookings.filtered(lambda b: b.payment_status == "refunded").mapped("paid_amount")),
            "cancellation_rate": (cancelled / len(bookings) * 100) if bookings else 0,
            "average_value": (sum(bookings.mapped("total_amount")) / len(bookings)) if bookings else 0,
            "by_facility": by_facility,
        }

    @api.model
    def get_utilization_analytics(self, date_from=None, date_to=None):
        today = fields.Date.context_today(self)
        date_from = date_from or (today - timedelta(days=30))
        date_to = date_to or today
        facilities = self.env["facility.facility"].search([("active", "=", True)])
        results = []
        for facility in facilities:
            available_hours = booked_hours = blocked_hours = 0
            day = date_from
            while day <= date_to:
                config = self.env["facility.slot.config"].get_active_config(facility, day)
                if config:
                    for slot in config.generate_slot_lines(day):
                        hours = slot["end_time"] - slot["start_time"]
                        available_hours += hours
                        if slot["status"] == "booked":
                            booked_hours += hours
                        elif slot["status"] == "blocked":
                            blocked_hours += hours
                day += timedelta(days=1)
            util = (booked_hours / available_hours * 100) if available_hours else 0
            results.append(
                {
                    "facility_id": facility.id,
                    "facility_name": facility.name,
                    "available_hours": round(available_hours, 2),
                    "booked_hours": round(booked_hours, 2),
                    "blocked_hours": round(blocked_hours, 2),
                    "utilization_percent": round(util, 1),
                    "booking_count": self.search_count(
                        [
                            ("facility_id", "=", facility.id),
                            ("booking_date", ">=", date_from),
                            ("booking_date", "<=", date_to),
                        ]
                    ),
                }
            )
        results.sort(key=lambda r: r["utilization_percent"], reverse=True)
        return {"facilities": results}

    @api.model
    def cron_send_reminders(self):
        tomorrow = fields.Date.context_today(self) + timedelta(days=1)
        bookings = self.search(
            [
                ("booking_date", "=", tomorrow),
                ("booking_status", "=", "confirmed"),
            ]
        )
        Notification = self.env["facility.booking.notification"]
        for booking in bookings:
            Notification.create_notification(
                booking, "booking_reminder", _("Your booking starts tomorrow.")
            )

    @api.model
    def cron_mark_completed(self):
        today = fields.Date.context_today(self)
        bookings = self.search(
            [
                ("booking_date", "<", today),
                ("booking_status", "=", "confirmed"),
            ]
        )
        bookings.write({"booking_status": "completed"})

    @api.model
    def cron_mark_expired(self):
        today = fields.Date.context_today(self)
        bookings = self.search(
            [
                ("booking_date", "<", today),
                ("booking_status", "in", ("payment_pending", "pending_approval")),
            ]
        )
        bookings.write({"booking_status": "expired"})

    @api.model
    def get_calendar_events(self, date_start, date_end, facility_id=None, property_id=None, status=None):
        domain = [
            ("booking_date", ">=", date_start),
            ("booking_date", "<=", date_end),
        ]
        if facility_id:
            domain.append(("facility_id", "=", facility_id))
        if property_id:
            domain.append(("property_id", "=", property_id))
        if status:
            domain.append(("booking_status", "=", status))
        bookings = self.search(domain)
        events = []
        for b in bookings:
            events.append(
                {
                    "id": b.id,
                    "type": "booking",
                    "title": "%s — %s" % (b.facility_id.name, b.name),
                    "date": str(b.booking_date),
                    "start_time": b.start_time,
                    "end_time": b.end_time,
                    "status": b.booking_status,
                    "facility_id": b.facility_id.id,
                }
            )
        block_domain = [
            ("state", "=", "active"),
            ("block_start_date", "<=", date_end),
            ("block_end_date", ">=", date_start),
        ]
        if facility_id:
            block_domain.append(("facility_id", "=", facility_id))
        blocks = self.env["facility.block"].search(block_domain)
        for block in blocks:
            day = block.block_start_date
            while day <= block.block_end_date:
                if date_start <= day <= date_end:
                    events.append(
                        {
                            "id": block.id,
                            "type": "block",
                            "title": _("Blocked: %s") % block.facility_id.name,
                            "date": str(day),
                            "start_time": block.start_time if not block.all_day else 0,
                            "end_time": block.end_time if not block.all_day else 24,
                            "status": "blocked",
                            "facility_id": block.facility_id.id,
                        }
                    )
                day += timedelta(days=1)
        return events

    @api.model
    def get_user_context(self):
        self.env["fms.property"]._fbm_migrate_property_managers_once()
        user = self.env.user
        resident = self.env["fms.resident"].get_resident_for_current_user()
        Property = self.env["fms.property"]
        properties = Property.search([("active", "=", True)])
        return {
            "user_name": user.name,
            "is_manager": user.has_group("facility_booking_management.group_facility_manager"),
            "is_approver": user.has_group("facility_booking_management.group_facility_approver"),
            "is_resident": user.has_group("facility_booking_management.group_facility_resident"),
            "resident_id": resident.id if resident else False,
            "resident_property_id": resident.property_id.id if resident and resident.property_id else False,
            "can_manage_properties": user.has_group("facility_booking_management.group_facility_manager"),
            "properties": [{"id": p.id, "name": p.name} for p in properties],
            "facility_types": [
                {"id": t.id, "name": t.name}
                for t in self.env["facility.type"].search([("active", "=", True)])
            ],
            "working_days": [
                {"id": d.id, "name": d.name, "code": d.code}
                for d in self.env["facility.working.day"].search([])
            ],
        }
