# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

from .constants import EVENT_CATEGORIES


class CommunityCommunicationEvent(models.Model):
    _name = "community.communication.event"
    _description = "Community Event"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.audience.mixin",
        "community.communication.attachment.mixin",
        "community.communication.state.mixin",
    ]
    _order = "date_start"
    _cc_state_transitions = {
        "draft": {"published", "cancelled"},
        "published": {"cancelled", "completed"},
        "cancelled": set(),
        "completed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    category = fields.Selection(EVENT_CATEGORIES, default="activities", required=True)
    description = fields.Html(sanitize=True)
    image_1920 = fields.Image()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "cc_event_attach_rel",
        "event_id",
        "attachment_id",
        string="Attachments",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
            ("cancelled", "Cancelled"),
            ("completed", "Completed"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    date_start = fields.Datetime(required=True, index=True)
    date_end = fields.Datetime(required=True)
    building_id = fields.Many2one(
        "community.communication.building",
        domain="[('community_id', '=', community_id)]",
    )
    venue_id = fields.Many2one(
        "community.communication.venue",
        domain="[('community_id', '=', community_id)]",
    )
    location = fields.Char()
    building_ids = fields.Many2many(
        "community.communication.building",
        "cc_event_building_rel",
        "event_id",
        "building_id",
        string="Target Buildings",
        domain="[('community_id', '=', community_id)]",
    )
    audience_group_ids = fields.Many2many(
        "community.communication.group",
        "cc_event_group_rel",
        "event_id",
        "group_id",
        string="Target Groups",
        domain="[('community_id', '=', community_id)]",
    )
    require_registration = fields.Boolean(default=True)
    date_deadline = fields.Datetime(string="Registration Deadline")
    capacity = fields.Integer()
    reminder_enabled = fields.Boolean(default=True)
    reminder_sent = fields.Boolean(copy=False)
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
    )
    registration_ids = fields.One2many(
        "community.communication.event.registration",
        "event_id",
        string="Registrations",
    )
    confirmed_count = fields.Integer(compute="_compute_registration_counts", store=True, compute_sudo=True)
    waitlist_count = fields.Integer(compute="_compute_registration_counts", store=True, compute_sudo=True)
    spots_available = fields.Integer(compute="_compute_spots_available")
    attendance_count = fields.Integer(compute="_compute_attendance_count", compute_sudo=True)

    @api.depends("registration_ids.state")
    def _compute_registration_counts(self):
        for record in self:
            record.confirmed_count = len(
                record.registration_ids.filtered(lambda r: r.state == "confirmed")
            )
            record.waitlist_count = len(
                record.registration_ids.filtered(lambda r: r.state == "waitlisted")
            )

    @api.depends("confirmed_count", "capacity")
    def _compute_spots_available(self):
        for record in self:
            record.spots_available = (
                max(record.capacity - record.confirmed_count, 0) if record.capacity else 0
            )

    @api.depends("registration_ids.state")
    def _compute_attendance_count(self):
        for record in self:
            record.attendance_count = len(
                record.registration_ids.filtered(lambda r: r.state == "attended")
            )

    @api.constrains("date_start", "date_end", "date_deadline")
    def _check_dates(self):
        for record in self:
            if record.date_end < record.date_start:
                raise ValidationError(_("Event end must be after the start."))
            if record.date_deadline and record.date_deadline > record.date_start:
                raise ValidationError(_("Registration deadline must be before the event start."))

    def action_publish(self):
        self._cc_require_officer()
        self._cc_set_state("published")

    def action_cancel(self):
        self._cc_require_officer()
        self._cc_set_state("cancelled")
        self.registration_ids.filtered(
            lambda r: r.state in ("pending", "confirmed", "waitlisted")
        ).action_cancel()

    def action_complete(self):
        self._cc_require_officer()
        self._cc_set_state("completed")

    def _promote_waitlist(self):
        for event in self:
            if not event.capacity:
                continue
            while event.confirmed_count < event.capacity:
                nxt = event.registration_ids.filtered(
                    lambda r: r.state == "waitlisted"
                ).sorted("registered_on")[:1]
                if not nxt:
                    break
                nxt.sudo().action_confirm()
                event.invalidate_recordset(["confirmed_count", "registration_ids"])

    def _cc_assert_open_for_registration(self, resident):
        self.ensure_one()
        if self.state != "published":
            raise UserError(_("This event is not open for registration."))
        if not self.require_registration:
            raise UserError(_("This event does not require registration."))
        if self.date_deadline and fields.Datetime.now() > self.date_deadline:
            raise UserError(_("The registration deadline has passed."))
        existing = self.registration_ids.filtered(
            lambda r: r.resident_id == resident and r.state != "cancelled"
        )
        if existing:
            raise UserError(_("You are already registered for this event."))
        return True

    def _cc_resident_registration_state(self):
        self.ensure_one()
        if self.capacity and self.confirmed_count >= self.capacity:
            return "waitlisted"
        return "confirmed"

    def action_register(self):
        self.ensure_one()
        resident = self._cc_current_resident()
        self._cc_assert_open_for_registration(resident)
        registration = self.env["community.communication.event.registration"].create({
            "event_id": self.id,
            "resident_id": resident.id,
            "community_id": self.community_id.id,
            "state": self._cc_resident_registration_state(),
        })
        self._cc_send_mail_template(
            "community_communication.mail_template_event_confirm",
            partners=resident.partner_id,
        )
        return registration

    def action_unregister(self):
        self.ensure_one()
        resident = self._cc_current_resident()
        registration = self.registration_ids.filtered(
            lambda r: r.resident_id == resident and r.state != "cancelled"
        )[:1]
        if not registration:
            raise UserError(_("You are not registered for this event."))
        registration.action_cancel()
        return True

    def get_my_registration(self):
        self.ensure_one()
        resident = self.env.user.cc_resident_ids[:1]
        rec = self.registration_ids.filtered(
            lambda r: r.resident_id == resident and r.state != "cancelled"
        )[:1]
        if not rec:
            return {}
        return {"id": rec.id, "state": rec.state}

    @api.model
    def _cron_send_reminders(self):
        now = fields.Datetime.now()
        horizon = now + timedelta(hours=24)
        events = self.search([
            ("state", "=", "published"),
            ("reminder_enabled", "=", True),
            ("reminder_sent", "=", False),
            ("date_start", ">", now),
            ("date_start", "<=", horizon),
        ])
        for event in events:
            partners = event.registration_ids.filtered(
                lambda r: r.state in ("confirmed", "waitlisted")
            ).mapped("resident_id.partner_id")
            event._cc_send_mail_template(
                "community_communication.mail_template_event_reminder",
                partners=partners,
            )
            event.reminder_sent = True

    @api.model
    def _cron_complete_past(self):
        past = self.search([
            ("state", "=", "published"),
            ("date_end", "<", fields.Datetime.now()),
        ])
        if past:
            past.action_complete()


class CommunityCommunicationEventRegistration(models.Model):
    _name = "community.communication.event.registration"
    _description = "Event Registration"
    _inherit = [
        "mail.thread",
        "community.communication.state.mixin",
    ]
    _order = "registered_on desc"
    _cc_state_transitions = {
        "pending": {"confirmed", "waitlisted", "rejected", "cancelled"},
        "confirmed": {"cancelled", "attended", "waitlisted"},
        "waitlisted": {"confirmed", "cancelled", "rejected"},
        "rejected": {"cancelled"},
        "cancelled": set(),
        "attended": set(),
    }

    event_id = fields.Many2one(
        "community.communication.event",
        required=True,
        ondelete="cascade",
        index=True,
    )
    resident_id = fields.Many2one(
        "community.communication.resident",
        required=True,
        ondelete="restrict",
        index=True,
    )
    partner_name = fields.Char(related="resident_id.name")
    unit_id = fields.Many2one(related="resident_id.unit_id")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("waitlisted", "Waitlisted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("attended", "Attended"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    registered_on = fields.Datetime(default=fields.Datetime.now, required=True)
    waitlist_rank = fields.Integer(compute="_compute_waitlist_rank")
    community_id = fields.Many2one(
        related="event_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="event_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    def _compute_waitlist_rank(self):
        for record in self:
            if record.state != "waitlisted":
                record.waitlist_rank = 0
                continue
            waitlisted = record.event_id.registration_ids.filtered(
                lambda r: r.state == "waitlisted"
            ).sorted("registered_on")
            record.waitlist_rank = waitlisted.ids.index(record.id) + 1 if record.id in waitlisted.ids else 0

    @api.constrains("event_id", "resident_id", "state")
    def _check_one_active_registration(self):
        for record in self:
            if record.state in ("cancelled", "rejected"):
                continue
            duplicate = self.search_count([
                ("id", "!=", record.id),
                ("event_id", "=", record.event_id.id),
                ("resident_id", "=", record.resident_id.id),
                ("state", "not in", ("cancelled", "rejected")),
            ])
            if duplicate:
                raise ValidationError(_("This resident is already registered for the event."))

    @api.model_create_multi
    def create(self, vals_list):
        officer = self.env.su or self.env.user._cc_is_community_officer()
        if not officer:
            resident = self.env.user.cc_resident_ids[:1]
            if not resident:
                raise ValidationError(_("No resident profile is linked to the current user."))
            for vals in vals_list:
                vals["resident_id"] = resident.id
                event = self.env["community.communication.event"].browse(int(vals.get("event_id") or 0))
                if not event.exists():
                    raise UserError(_("Select a valid event."))
                event._cc_assert_open_for_registration(resident)
                vals["state"] = event._cc_resident_registration_state()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            raise AccessError(_("Residents cannot modify event registrations directly."))
        return super().write(vals)

    def action_confirm(self):
        self.env["community.communication.event"]._cc_require_officer()
        for record in self:
            event = record.event_id
            if event.capacity and event.confirmed_count >= event.capacity and record.state != "confirmed":
                raise UserError(_("This event is at capacity. Use the waitlist."))
        self._cc_set_state("confirmed")

    def action_waitlist(self):
        self.env["community.communication.event"]._cc_require_officer()
        self._cc_set_state("waitlisted")

    def action_reject(self):
        self.env["community.communication.event"]._cc_require_officer()
        self._cc_set_state("rejected")

    def action_cancel(self):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            if self.filtered(lambda rec: rec.resident_id.user_id != self.env.user):
                raise UserError(_("You can only cancel your own registration."))
            for record in self:
                event = record.event_id
                if event.state != "published":
                    raise UserError(_("This event is not open for registration changes."))
                if event.date_deadline and fields.Datetime.now() > event.date_deadline:
                    raise UserError(_("The registration deadline has passed."))
        self.sudo()._cc_set_state("cancelled")
        self.sudo().mapped("event_id")._promote_waitlist()

    def action_attended(self):
        self.env["community.communication.event"]._cc_require_officer()
        self._cc_set_state("attended")
