# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import KPI_AGGREGATIONS, KPI_CATEGORIES
from .utils import date_bounds, parse_domain, pct_change, pick_date_field, previous_bounds, company_domain, dt_end, dt_start, field_exists


class AnalyticsKpiDefinition(models.Model):
    _name = "analytics.kpi"
    _description = "Analytics KPI Definition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "category, name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    category = fields.Selection(
        KPI_CATEGORIES,
        required=True,
        default="operations",
        tracking=True,
        index=True,
    )
    target = fields.Float(
        help="Target value for this KPI when applicable.",
    )
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    data_source_id = fields.Many2one(
        "analytics.data.source",
        ondelete="set null",
        index=True,
        help="Registered analytics source for KPI calculation.",
    )
    source_model = fields.Char(
        help="Override or specify the Odoo model used for calculation.",
    )
    source_domain = fields.Text(
        help="Domain filter (Python list syntax) applied when computing the KPI.",
    )
    measure_field = fields.Char(
        help="Numeric field or measure identifier to aggregate.",
    )
    aggregation = fields.Selection(
        KPI_AGGREGATIONS,
        default="count",
        required=True,
    )
    config_notes = fields.Text(
        help="Free-form configuration notes for later calculation engines.",
    )
    unit = fields.Char()
    higher_is_better = fields.Boolean(default=True)

    def write(self, vals):
        for record in self:
            if any(key in vals for key in ("name", "target", "source_domain", "measure_field", "aggregation", "data_source_id")):
                self.env["analytics.audit.log"].log_event(
                    "write",
                    _("KPI updated: %s") % record.name,
                    kpi_id=record.id,
                )
        return super().write(vals)

    def _resolve_model(self):
        self.ensure_one()
        model_name = self.source_model or (self.data_source_id.model_name if self.data_source_id else False)
        if not model_name or model_name not in self.env:
            return False, _("Data unavailable")
        if not self.env[model_name].has_access("read"):
            return False, _("No permission to read this source")
        if self.data_source_id:
            available, reason = self.data_source_id._availability()
            if not available:
                return False, reason
        return self.env[model_name], False

    def compute_snapshot(self, filters=None):
        self.ensure_one()
        filters = filters or {}
        model, error = self._resolve_model()
        if error:
            return {
                "id": self.id,
                "name": self.name,
                "category": self.category,
                "available": False,
                "reason": error,
                "value": None,
                "previous": None,
                "target": self.target,
                "change": None,
                "status": "unavailable",
                "unit": self.unit or "",
            }
        start, end = date_bounds(filters.get("date_range") or "last_30", today=fields.Date.context_today(self))
        prev_start, prev_end = previous_bounds(start, end)
        try:
            current = self._compute_for_period(model, start, end, filters)
            previous = self._compute_for_period(model, prev_start, prev_end, filters)
        except Exception:
            return {
                "id": self.id,
                "name": self.name,
                "category": self.category,
                "available": False,
                "reason": _("Data unavailable"),
                "value": None,
                "previous": None,
                "target": self.target,
                "change": None,
                "status": "unavailable",
                "unit": self.unit or "",
            }
        change = pct_change(current, previous)
        status = "healthy"
        if current is None:
            status = "unavailable"
        elif self.target:
            if self.higher_is_better and current < self.target:
                status = "below"
            elif not self.higher_is_better and current > self.target:
                status = "above"
            else:
                status = "on_target"
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "available": current is not None,
            "reason": "" if current is not None else _("No Data"),
            "value": current,
            "previous": previous,
            "target": self.target,
            "change": change,
            "status": status,
            "unit": self.unit or "",
            "higher_is_better": self.higher_is_better,
        }

    def _compute_for_period(self, model, start, end, filters):
        domain = list(parse_domain(self.source_domain))
        domain += company_domain(model, self.env.company)
        date_field = pick_date_field(model)
        if date_field:
            ftype = model._fields[date_field].type
            if ftype == "datetime":
                domain += [(date_field, ">=", dt_start(start)), (date_field, "<=", dt_end(end))]
            else:
                domain += [(date_field, ">=", start), (date_field, "<=", end)]
        if filters.get("property_id") and field_exists(model, "property_id"):
            domain.append(("property_id", "=", filters["property_id"]))
        if filters.get("building_id") and field_exists(model, "building_id"):
            domain.append(("building_id", "=", filters["building_id"]))
        metric = {
            "name": self.measure_field or "__count",
            "aggregation": self.aggregation or "count",
        }
        return self.env["analytics.query.engine"]._aggregate(model, domain, metric)

    @api.model
    def get_dashboard_payload(self, filters=None):
        filters = filters or {}
        kpis = self.search([("active", "=", True)])
        cards = [kpi.compute_snapshot(filters) for kpi in kpis]
        chart = {"labels": [], "series": []}
        available = [card for card in cards if card["available"]]
        if available:
            chart = {
                "labels": [card["name"] for card in available],
                "series": [{"name": _("Current"), "data": [card["value"] or 0 for card in available]}],
            }
        return {
            "kpis": cards,
            "chart": chart,
            "available": bool(available),
            "reason": "" if available else _("No KPI sources returned data"),
        }
