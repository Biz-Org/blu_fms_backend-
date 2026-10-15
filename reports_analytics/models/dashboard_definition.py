# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import DASHBOARD_TYPES


class AnalyticsDashboardDefinition(models.Model):
    _name = "analytics.dashboard"
    _description = "Analytics Dashboard Definition"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True)
    dashboard_type = fields.Selection(
        DASHBOARD_TYPES,
        required=True,
        default="operational",
        index=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    source_module = fields.Char(
        string="Module / Source",
        index=True,
        help="Primary FMS module or scope for this dashboard.",
    )
    report_ids = fields.Many2many(
        "analytics.report",
        "analytics_dashboard_report_rel",
        "dashboard_id",
        "report_id",
        string="Reports",
        help="Report definitions linked to this dashboard layout.",
    )
    kpi_ids = fields.Many2many(
        "analytics.kpi",
        "analytics_dashboard_kpi_rel",
        "dashboard_id",
        "kpi_id",
        string="KPIs",
    )
    layout_json = fields.Json(default=lambda self: {})

    def write(self, vals):
        for record in self:
            self.env["analytics.audit.log"].log_event(
                "write",
                _("Dashboard updated: %s") % record.name,
                dashboard_id=record.id,
            )
        return super().write(vals)

    @api.model
    def action_create_from_ui(self, vals):
        record = self.create({
            "name": vals.get("name") or _("Analytics Dashboard"),
            "dashboard_type": vals.get("dashboard_type") or "operational",
            "source_module": vals.get("source_module"),
            "kpi_ids": [(6, 0, vals.get("kpi_ids") or [])],
            "report_ids": [(6, 0, vals.get("report_ids") or [])],
        })
        self.env["analytics.audit.log"].log_event(
            "create",
            _("Dashboard created: %s") % record.name,
            dashboard_id=record.id,
        )
        return {"id": record.id, "name": record.name}
