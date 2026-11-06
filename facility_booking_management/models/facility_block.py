# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class FacilityBlock(models.Model):
    _name = "facility.block"
    _description = "Facility Block"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "block_start_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    facility_id = fields.Many2one("facility.facility", required=True, ondelete="restrict", tracking=True)
    block_start_date = fields.Date(required=True, tracking=True)
    block_end_date = fields.Date(required=True, tracking=True)
    start_time = fields.Float()
    end_time = fields.Float()
    all_day = fields.Boolean(default=True)
    block_reason = fields.Selection(
        [
            ("maintenance", "Maintenance"),
            ("cleaning", "Cleaning"),
            ("private_event", "Private Event"),
            ("renovation", "Renovation"),
            ("safety", "Safety Issue"),
            ("holiday", "Holiday"),
            ("management", "Management Restriction"),
            ("other", "Other"),
        ],
        required=True,
        default="maintenance",
    )
    description = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("cancelled", "Cancelled")],
        default="active",
        tracking=True,
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Supporting Documents")
    created_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    affected_booking_ids = fields.Many2many(
        "facility.booking",
        compute="_compute_affected_bookings",
        string="Affected Bookings",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("facility_id", "block_start_date", "block_end_date")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.facility_id.name if rec.facility_id else _("Block")

    @api.constrains("block_start_date", "block_end_date")
    def _check_dates(self):
        for rec in self:
            if rec.block_end_date < rec.block_start_date:
                raise ValidationError(_("Block end date must be on or after start date."))

    @api.depends("facility_id", "block_start_date", "block_end_date", "start_time", "end_time", "all_day")
    def _compute_affected_bookings(self):
        Booking = self.env["facility.booking"]
        for rec in self:
            domain = [
                ("facility_id", "=", rec.facility_id.id),
                ("booking_date", ">=", rec.block_start_date),
                ("booking_date", "<=", rec.block_end_date),
                ("booking_status", "in", ("confirmed", "pending_approval", "payment_pending")),
            ]
            bookings = Booking.search(domain)
            if not rec.all_day and rec.start_time and rec.end_time:
                bookings = bookings.filtered(
                    lambda b: b._times_overlap(rec.start_time, rec.end_time, b.start_time, b.end_time)
                )
            rec.affected_booking_ids = bookings

    def action_cancel_block(self):
        self.write({"state": "cancelled"})

    def action_extend_block(self, new_end_date):
        for rec in self:
            if new_end_date < rec.block_end_date:
                raise UserError(_("Extension date must be after current end date."))
            rec.block_end_date = new_end_date

    @api.model
    def is_blocked(self, facility_id, booking_date, start_time, end_time):
        blocks = self.search(
            [
                ("facility_id", "=", facility_id),
                ("state", "=", "active"),
                ("block_start_date", "<=", booking_date),
                ("block_end_date", ">=", booking_date),
            ]
        )
        for block in blocks:
            if block.all_day:
                return True
            if block.start_time is not False and block.end_time is not False:
                if self.env["facility.booking"]._times_overlap(
                    start_time, end_time, block.start_time, block.end_time
                ):
                    return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        Notification = self.env["facility.booking.notification"]
        for rec in records:
            for booking in rec.affected_booking_ids:
                Notification.create_notification(
                    booking,
                    "facility_alert",
                    _("Facility unavailable: %s is blocked from %s to %s.")
                    % (rec.facility_id.name, rec.block_start_date, rec.block_end_date),
                )
        return records

    @api.model
    def _serialize_block(self, block):
        return {
            "id": block.id,
            "facility_id": block.facility_id.id,
            "facility_name": block.facility_id.name,
            "block_start_date": str(block.block_start_date),
            "block_end_date": str(block.block_end_date),
            "start_time": block.start_time,
            "end_time": block.end_time,
            "all_day": block.all_day,
            "block_reason": block.block_reason,
            "description": block.description,
            "state": block.state,
            "created_by": block.created_by_id.name,
            "affected_booking_count": len(block.affected_booking_ids),
        }

    @api.model
    def search_blocks(self, domain=None, limit=80):
        domain = domain or []
        records = self.search(domain, limit=limit, order="block_start_date desc")
        return [self._serialize_block(r) for r in records]

    @api.model
    def save_block_from_ui(self, values, block_id=None):
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            raise AccessError(_("Only facility managers can manage blocks."))
        if block_id:
            block = self.browse(block_id)
            block.write(values)
        else:
            block = self.create(values)
        return self._serialize_block(block)
