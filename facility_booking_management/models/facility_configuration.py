# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FacilityBookingConfig(models.Model):
    _name = "facility.booking.config"
    _description = "Facility Booking Configuration"
    _rec_name = "company_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    advance_booking_days = fields.Integer(default=30)
    min_booking_duration = fields.Float(default=1.0, string="Min Duration (hours)")
    max_booking_duration = fields.Float(default=8.0, string="Max Duration (hours)")
    max_guests = fields.Integer(default=50)
    allow_back_to_back = fields.Boolean(string="Allow Back-to-Back Booking", default=False)
    buffer_time = fields.Float(string="Default Buffer (hours)", default=0.5)

    free_cancellation_hours = fields.Float(default=24.0)
    refund_percent = fields.Float(default=100.0)
    cancellation_penalty_percent = fields.Float(default=10.0)
    no_show_penalty_percent = fields.Float(default=100.0)
    allow_rescheduling = fields.Boolean(default=True)

    approval_amount_threshold = fields.Monetary(currency_field="currency_id")
    auto_approval = fields.Boolean(default=False)
    approval_time_limit_hours = fields.Float(default=48.0)
    notify_approver = fields.Boolean(default=True)

    default_opening_time = fields.Float(default=6.0)
    default_closing_time = fields.Float(default=22.0)
    default_tax_percent = fields.Float(default=0.0)

    notify_booking_confirmation = fields.Boolean(default=True)
    notify_approval = fields.Boolean(default=True)
    notify_cancellation = fields.Boolean(default=True)
    notify_payment = fields.Boolean(default=True)
    notify_reminder = fields.Boolean(default=True)

    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Only one booking configuration per company is allowed."),
    ]

    @api.model
    def get_config(self):
        config = self.search([("company_id", "=", self.env.company.id)], limit=1)
        if not config:
            config = self.create({"company_id": self.env.company.id})
        return config

    @api.model
    def get_config_payload(self):
        config = self.get_config()
        return {
            "advance_booking_days": config.advance_booking_days,
            "min_booking_duration": config.min_booking_duration,
            "max_booking_duration": config.max_booking_duration,
            "max_guests": config.max_guests,
            "allow_back_to_back": config.allow_back_to_back,
            "buffer_time": config.buffer_time,
            "free_cancellation_hours": config.free_cancellation_hours,
            "refund_percent": config.refund_percent,
            "cancellation_penalty_percent": config.cancellation_penalty_percent,
            "no_show_penalty_percent": config.no_show_penalty_percent,
            "allow_rescheduling": config.allow_rescheduling,
            "approval_amount_threshold": config.approval_amount_threshold,
            "auto_approval": config.auto_approval,
            "approval_time_limit_hours": config.approval_time_limit_hours,
            "notify_approver": config.notify_approver,
            "default_opening_time": config.default_opening_time,
            "default_closing_time": config.default_closing_time,
            "default_tax_percent": config.default_tax_percent,
            "notify_booking_confirmation": config.notify_booking_confirmation,
            "notify_approval": config.notify_approval,
            "notify_cancellation": config.notify_cancellation,
            "notify_payment": config.notify_payment,
            "notify_reminder": config.notify_reminder,
        }

    @api.model
    def save_config_payload(self, values):
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            from odoo.exceptions import AccessError

            raise AccessError(_("Only facility managers can update configuration."))
        config = self.get_config()
        allowed = set(self.get_config_payload().keys())
        config.write({k: v for k, v in values.items() if k in allowed})
        return self.get_config_payload()
