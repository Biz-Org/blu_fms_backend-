# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class FacilityFacility(models.Model):
    _name = "facility.facility"
    _description = "Bookable Facility"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        string="Facility ID",
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    facility_type_id = fields.Many2one(
        "facility.type",
        string="Facility Type",
        required=True,
        ondelete="restrict",
    )
    property_id = fields.Many2one("fms.property", string="Property / Building", ondelete="restrict")
    location = fields.Char()
    floor_block = fields.Char(string="Floor / Block")
    capacity = fields.Integer(default=1)
    description = fields.Html()
    operating_hours_note = fields.Char(string="Operating Hours Summary")

    booking_type = fields.Selection(
        [
            ("hourly", "Hourly"),
            ("slot", "Fixed Slot"),
            ("daily", "Daily"),
        ],
        default="slot",
        required=True,
    )
    charge_type = fields.Selection(
        [("free", "Free"), ("paid", "Paid")],
        default="free",
        required=True,
        string="Paid / Free",
    )
    base_charge = fields.Monetary(currency_field="currency_id")
    cleaning_charge = fields.Monetary(currency_field="currency_id")
    security_charge = fields.Monetary(currency_field="currency_id")
    additional_service_charge = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    approval_required = fields.Boolean(string="Approval Required", default=False)
    booking_status = fields.Selection(
        [("open", "Open for Booking"), ("closed", "Closed")],
        default="open",
        string="Booking Status",
    )
    availability_status = fields.Selection(
        [
            ("available", "Available"),
            ("partial", "Partially Available"),
            ("booked", "Booked"),
            ("blocked", "Blocked"),
            ("closed", "Closed"),
        ],
        compute="_compute_availability_status",
        store=False,
    )
    rules_restrictions = fields.Text(string="Rules / Restrictions")
    active = fields.Boolean(default=True, tracking=True)

    slot_config_ids = fields.One2many("facility.slot.config", "facility_id", string="Time Slot Configurations")
    booking_ids = fields.One2many("facility.booking", "facility_id")
    block_ids = fields.One2many("facility.block", "facility_id")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = self.env["ir.sequence"].next_by_code("facility.facility") or _("New")
        return super().create(vals_list)

    @api.depends("active", "booking_status")
    def _compute_availability_status(self):
        today = fields.Date.context_today(self)
        Booking = self.env["facility.booking"]
        Block = self.env["facility.block"]
        for facility in self:
            if not facility.active or facility.booking_status == "closed":
                facility.availability_status = "closed"
                continue
            blocks = Block.search_count(
                [
                    ("facility_id", "=", facility.id),
                    ("state", "=", "active"),
                    ("block_start_date", "<=", today),
                    ("block_end_date", ">=", today),
                ]
            )
            if blocks:
                facility.availability_status = "blocked"
                continue
            bookings = Booking.search_count(
                [
                    ("facility_id", "=", facility.id),
                    ("booking_date", "=", today),
                    ("booking_status", "in", ("confirmed", "pending_approval", "payment_pending")),
                ]
            )
            if bookings:
                facility.availability_status = "partial"
            else:
                facility.availability_status = "available"

    def action_activate(self):
        self.write({"active": True})

    def action_deactivate(self):
        self.write({"active": False})

    @api.model
    def _float_to_time_str(self, value):
        if value is False or value is None:
            return ""
        hours = int(value)
        minutes = int(round((value - hours) * 60))
        return f"{hours:02d}:{minutes:02d}"

    @api.model
    def _time_str_to_float(self, time_str):
        if not time_str:
            return 0.0
        parts = time_str.split(":")
        return int(parts[0]) + (int(parts[1]) / 60.0 if len(parts) > 1 else 0)

    def _slot_status(self, date, start_time, end_time):
        """Return availability status for a slot segment."""
        self.ensure_one()
        Block = self.env["facility.block"]
        Booking = self.env["facility.booking"]
        if not self.active or self.booking_status == "closed":
            return "closed"
        if Block.is_blocked(self.id, date, start_time, end_time):
            return "blocked"
        overlaps = Booking.search(
            [
                ("facility_id", "=", self.id),
                ("booking_date", "=", date),
                ("booking_status", "in", ("confirmed", "pending_approval", "payment_pending")),
            ]
        )
        for booking in overlaps:
            if booking._times_overlap(start_time, end_time, booking.start_time, booking.end_time):
                return "booked"
        return "available"

    @api.model
    def get_availability(self, facility_id, date):
        date = fields.Date.to_date(date)
        facility = self.browse(facility_id)
        if not facility.exists():
            return {"error": _("Facility not found.")}
        config = self.env["facility.slot.config"].get_active_config(facility, date)
        if not config:
            return {
                "facility_id": facility.id,
                "facility_name": facility.name,
                "date": str(date),
                "capacity": facility.capacity,
                "slots": [],
                "status": "closed",
            }
        slots = config.generate_slot_lines(date)
        statuses = [s["status"] for s in slots]
        if not slots:
            overall = "closed"
        elif all(s == "booked" for s in statuses):
            overall = "booked"
        elif all(s == "blocked" for s in statuses):
            overall = "blocked"
        elif any(s == "available" for s in statuses):
            overall = "partial" if any(s in ("booked", "blocked") for s in statuses) else "available"
        else:
            overall = "partial"
        return {
            "facility_id": facility.id,
            "facility_name": facility.name,
            "date": str(date),
            "capacity": facility.capacity,
            "slots": slots,
            "status": overall,
        }

    @api.model
    def _serialize_facility(self, facility):
        return {
            "id": facility.id,
            "code": facility.code,
            "name": facility.name,
            "facility_type_id": facility.facility_type_id.id,
            "facility_type_name": facility.facility_type_id.name,
            "property_id": facility.property_id.id,
            "property_name": facility.property_id.name,
            "location": facility.location,
            "floor_block": facility.floor_block,
            "capacity": facility.capacity,
            "description": facility.description,
            "operating_hours_note": facility.operating_hours_note,
            "booking_type": facility.booking_type,
            "charge_type": facility.charge_type,
            "base_charge": facility.base_charge,
            "approval_required": facility.approval_required,
            "booking_status": facility.booking_status,
            "availability_status": facility.availability_status,
            "rules_restrictions": facility.rules_restrictions,
            "active": facility.active,
        }

    @api.model
    def search_facilities(self, domain=None, limit=100, offset=0):
        domain = domain or []
        records = self.search(domain, limit=limit, offset=offset, order="name")
        return {
            "records": [self._serialize_facility(r) for r in records],
            "total": self.search_count(domain),
        }

    @api.model
    def save_facility_from_ui(self, values, facility_id=None):
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            raise AccessError(_("Only community managers can manage facilities."))
        vals = dict(values or {})
        for key in ("facility_type_name", "property_name", "availability_status", "code"):
            vals.pop(key, None)
        type_id = vals.get("facility_type_id")
        if type_id in (False, None, "", 0):
            raise ValidationError(_("Please select a facility type."))
        vals["facility_type_id"] = int(type_id)
        if vals.get("property_id"):
            vals["property_id"] = int(vals["property_id"])
        elif "property_id" in vals:
            vals["property_id"] = False
        if "capacity" in vals and vals["capacity"] not in (False, None, ""):
            vals["capacity"] = int(vals["capacity"])
        if facility_id:
            facility = self.browse(facility_id)
            if not facility.exists():
                raise AccessError(_("Facility not found."))
            facility.write(vals)
        else:
            if not vals.get("name"):
                raise ValidationError(_("Facility name is required."))
            facility = self.create(vals)
        return self._serialize_facility(facility)
