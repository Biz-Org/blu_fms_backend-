# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import AUDIT_ACTIONS


class AnalyticsAuditLog(models.Model):
    _name = "analytics.audit.log"
    _description = "Analytics Audit Log"
    _order = "event_datetime desc, id desc"
    _check_company_auto = True

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    action = fields.Selection(
        AUDIT_ACTIONS,
        required=True,
        default="other",
        index=True,
    )
    event_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    report_id = fields.Many2one(
        "analytics.report",
        ondelete="set null",
        index=True,
    )
    dashboard_id = fields.Many2one(
        "analytics.dashboard",
        ondelete="set null",
        index=True,
    )
    kpi_id = fields.Many2one("analytics.kpi", ondelete="set null", index=True)
    schedule_id = fields.Many2one("analytics.report.schedule", ondelete="set null", index=True)
    alert_id = fields.Many2one("analytics.alert", ondelete="set null", index=True)
    related_module = fields.Char(
        string="Related Module",
        index=True,
        help="FMS module technical name related to this event.",
    )
    previous_value = fields.Text(
        help="Previous value or snapshot before the change.",
    )
    new_value = fields.Text(
        help="New value or snapshot after the change.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    description = fields.Char(
        help="Short human-readable summary of the audited event.",
    )

    @api.model
    def log_event(self, action, description, **kwargs):
        if not self.has_access("create"):
            return self.browse()
        vals = {
            "action": action or "other",
            "description": description,
            "company_id": kwargs.get("company_id") or self.env.company.id,
            "user_id": self.env.user.id,
        }
        for key in ("report_id", "dashboard_id", "kpi_id", "schedule_id", "alert_id", "related_module", "previous_value", "new_value"):
            if kwargs.get(key):
                vals[key] = kwargs[key]
        return self.create(vals)
