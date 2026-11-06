# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FacilitySlotConfig(models.Model):
    _name = "facility.slot.config"
    _description = "Facility Time Slot Configuration"
    _order = "facility_id, id"

    name = fields.Char(compute="_compute_name", store=True)
    facility_id = fields.Many2one(
        "facility.facility",
        required=True,
        ondelete="cascade",
        index=True,
    )
    working_day_ids = fields.Many2many(
        "facility.working.day",
        string="Working Days",
    )
    opening_time = fields.Float(string="Opening Time", required=True, default=6.0)
    closing_time = fields.Float(string="Closing Time", required=True, default=22.0)
    slot_duration = fields.Float(string="Slot Duration (hours)", required=True, default=2.0)
    break_start = fields.Float(string="Break Start")
    break_end = fields.Float(string="Break End")
    buffer_time = fields.Float(string="Buffer Time (hours)", default=0.5)
    holiday_ids = fields.One2many("facility.slot.holiday", "slot_config_id", string="Holidays")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )

    @api.depends("facility_id", "opening_time", "closing_time")
    def _compute_name(self):
        Facility = self.env["facility.facility"]
        for rec in self:
            if rec.facility_id:
                rec.name = "%s — %s–%s" % (
                    rec.facility_id.name,
                    Facility._float_to_time_str(rec.opening_time),
                    Facility._float_to_time_str(rec.closing_time),
                )
            else:
                rec.name = _("Slot Configuration")

    @api.constrains("opening_time", "closing_time", "slot_duration")
    def _check_times(self):
        for rec in self:
            if rec.closing_time <= rec.opening_time:
                raise ValidationError(_("Closing time must be after opening time."))
            if rec.slot_duration <= 0:
                raise ValidationError(_("Slot duration must be positive."))

    def _is_working_day(self, date):
        self.ensure_one()
        if not self.working_day_ids:
            return date.weekday() < 5
        weekday_codes = self.working_day_ids.mapped("code")
        day_map = {
            0: "mon",
            1: "tue",
            2: "wed",
            3: "thu",
            4: "fri",
            5: "sat",
            6: "sun",
        }
        return day_map.get(date.weekday()) in weekday_codes

    def _is_holiday(self, date):
        self.ensure_one()
        return bool(self.holiday_ids.filtered(lambda h: h.date == date and h.active))

    def get_active_config(self, facility, date):
        configs = facility.slot_config_ids.filtered(lambda c: c.active)
        if not configs:
            return self.env["facility.slot.config"]
        for config in configs:
            if config._is_holiday(date):
                continue
            if config._is_working_day(date):
                return config
        return self.env["facility.slot.config"]

    def generate_slot_lines(self, date):
        self.ensure_one()
        Facility = self.env["facility.facility"]
        facility = self.facility_id
        if self._is_holiday(date) or not self._is_working_day(date):
            return []

        slots = []
        cursor = self.opening_time
        duration = self.slot_duration
        buffer = self.buffer_time or 0.0

        while cursor + duration <= self.closing_time:
            slot_start = cursor
            slot_end = cursor + duration
            if self.break_start and self.break_end:
                if not (slot_end <= self.break_start or slot_start >= self.break_end):
                    cursor = self.break_end
                    continue
            status = facility._slot_status(date, slot_start, slot_end)
            slots.append(
                {
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "start_label": Facility._float_to_time_str(slot_start),
                    "end_label": Facility._float_to_time_str(slot_end),
                    "status": status,
                }
            )
            cursor = slot_end + buffer
        return slots


class FacilityWorkingDay(models.Model):
    _name = "facility.working.day"
    _description = "Working Day"
    _order = "sequence"

    name = fields.Char(required=True)
    code = fields.Selection(
        [
            ("mon", "Monday"),
            ("tue", "Tuesday"),
            ("wed", "Wednesday"),
            ("thu", "Thursday"),
            ("fri", "Friday"),
            ("sat", "Saturday"),
            ("sun", "Sunday"),
        ],
        required=True,
    )
    sequence = fields.Integer(default=10)


class FacilitySlotHoliday(models.Model):
    _name = "facility.slot.holiday"
    _description = "Facility Slot Holiday"

    slot_config_id = fields.Many2one("facility.slot.config", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    date = fields.Date(required=True)
    active = fields.Boolean(default=True)


class FacilitySlotConfigPortal(models.Model):
    _inherit = "facility.slot.config"

    @api.model
    def _serialize_config(self, config):
        Facility = self.env["facility.facility"]
        return {
            "id": config.id,
            "facility_id": config.facility_id.id,
            "facility_name": config.facility_id.name,
            "working_day_ids": config.working_day_ids.ids,
            "working_day_names": config.working_day_ids.mapped("name"),
            "opening_time": config.opening_time,
            "closing_time": config.closing_time,
            "opening_label": Facility._float_to_time_str(config.opening_time),
            "closing_label": Facility._float_to_time_str(config.closing_time),
            "slot_duration": config.slot_duration,
            "break_start": config.break_start,
            "break_end": config.break_end,
            "buffer_time": config.buffer_time,
            "active": config.active,
        }

    @api.model
    def search_slot_configs(self, facility_id=None):
        domain = []
        if facility_id:
            domain.append(("facility_id", "=", facility_id))
        return [self._serialize_config(c) for c in self.search(domain)]

    @api.model
    def save_slot_config_from_ui(self, values, config_id=None):
        if not self.env.user.has_group("facility_booking_management.group_facility_manager"):
            from odoo.exceptions import AccessError

            raise AccessError(_("Only facility managers can manage time slots."))
        if config_id:
            config = self.browse(config_id)
            config.write(values)
        else:
            config = self.create(values)
        return self._serialize_config(config)
