# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import OUTPUT_FORMATS, SCHEDULE_FREQUENCIES, WEEKDAYS
from .utils import next_schedule_datetime


class AnalyticsReportSchedule(models.Model):
    _name = "analytics.report.schedule"
    _description = "Scheduled Analytics Report"
    _inherit = ["mail.thread"]
    _order = "next_run asc, id desc"
    _check_company_auto = True

    name = fields.Char(related="report_id.name", store=True)
    report_id = fields.Many2one(
        "analytics.report",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    recipient_ids = fields.Many2many(
        "res.users",
        "analytics_schedule_user_rel",
        "schedule_id",
        "user_id",
        string="Recipients",
        required=True,
    )
    frequency = fields.Selection(SCHEDULE_FREQUENCIES, required=True, default="weekly", tracking=True)
    weekday = fields.Selection(WEEKDAYS, default="0")
    month_day = fields.Integer(default=1)
    hour = fields.Integer(default=8)
    minute = fields.Integer(default=0)
    interval_days = fields.Integer(default=1)
    output_format = fields.Selection(OUTPUT_FORMATS, required=True, default="pdf")
    active = fields.Boolean(default=True, tracking=True)
    next_run = fields.Datetime(index=True)
    last_run = fields.Datetime(readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.next_run:
                record.next_run = next_schedule_datetime(
                    record.frequency,
                    weekday=int(record.weekday or 0),
                    month_day=record.month_day,
                    hour=record.hour,
                    minute=record.minute,
                    interval_days=record.interval_days,
                )
            record.report_id.status = "scheduled"
            self.env["analytics.audit.log"].log_event(
                "schedule",
                _("Schedule created for %s") % record.report_id.name,
                report_id=record.report_id.id,
                schedule_id=record.id,
            )
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(key in vals for key in ("frequency", "weekday", "month_day", "hour", "minute", "interval_days", "active")):
            for record in self:
                record.next_run = next_schedule_datetime(
                    record.frequency,
                    weekday=int(record.weekday or 0),
                    month_day=record.month_day,
                    hour=record.hour,
                    minute=record.minute,
                    interval_days=record.interval_days,
                )
                self.env["analytics.audit.log"].log_event(
                    "schedule",
                    _("Schedule updated for %s") % record.report_id.name,
                    report_id=record.report_id.id,
                    schedule_id=record.id,
                )
        return res

    def ui_row(self):
        self.ensure_one()
        return {
            "id": self.id,
            "report_id": self.report_id.id,
            "report_name": self.report_id.name,
            "output_format": self.output_format,
            "frequency": self.frequency,
            "weekday": self.weekday,
            "month_day": self.month_day,
            "hour": self.hour,
            "minute": self.minute,
            "next_run": fields.Datetime.to_string(self.next_run) if self.next_run else False,
            "last_run": fields.Datetime.to_string(self.last_run) if self.last_run else False,
            "active": self.active,
            "status": "active" if self.active else "paused",
            "recipients": [{"id": user.id, "name": user.name} for user in self.recipient_ids],
        }

    @api.model
    def action_create_from_ui(self, vals):
        if not vals.get("report_id"):
            raise UserError(_("Select a report to schedule."))
        if not vals.get("recipient_ids"):
            raise UserError(_("Select at least one recipient."))
        record = self.create({
            "report_id": vals["report_id"],
            "recipient_ids": [(6, 0, vals["recipient_ids"])],
            "frequency": vals.get("frequency") or "weekly",
            "weekday": str(vals.get("weekday") or "0"),
            "month_day": vals.get("month_day") or 1,
            "hour": vals.get("hour") or 8,
            "minute": vals.get("minute") or 0,
            "interval_days": vals.get("interval_days") or 1,
            "output_format": vals.get("output_format") or "pdf",
            "active": bool(vals.get("active", True)),
        })
        return record.ui_row()

    def action_run_now(self):
        for record in self:
            record._run()
        return True

    def _run(self):
        self.ensure_one()
        execution = self.report_id._execute(output_format=self.output_format, scheduled=True)
        execution.schedule_id = self.id
        self.last_run = fields.Datetime.now()
        self.next_run = next_schedule_datetime(
            self.frequency,
            weekday=int(self.weekday or 0),
            month_day=self.month_day,
            hour=self.hour,
            minute=self.minute,
            interval_days=self.interval_days,
        )
        self._notify(execution)
        return execution

    def _notify(self, execution):
        partners = self.recipient_ids.mapped("partner_id")
        if not partners:
            return
        template = self.env.ref("reports_analytics.mail_template_scheduled_report", raise_if_not_found=False)
        if template:
            for user in self.recipient_ids:
                if user.partner_id.email:
                    template.send_mail(execution.id, force_send=False, email_values={
                        "email_to": user.partner_id.email,
                        "recipient_ids": [(6, 0, user.partner_id.ids)],
                    })
        else:
            execution.message_post = getattr(execution, "message_post", None)
        if execution.attachment_id:
            self.report_id.message_post(
                body=_("Scheduled report delivered: %s") % self.report_id.name,
                partner_ids=partners.ids,
                attachment_ids=execution.attachment_id.ids,
                subtype_xmlid="mail.mt_note",
            )

    @api.model
    def _cron_run_schedules(self):
        now = fields.Datetime.now()
        due = self.search([("active", "=", True), ("next_run", "<=", now)])
        for record in due:
            try:
                record._run()
            except Exception as exc:
                record.message_post(body=_("Scheduled run failed: %s") % exc)
        return True
