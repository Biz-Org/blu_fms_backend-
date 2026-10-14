# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.translate import _

from .source_catalog import OPEN_STATE_HINTS
from .utils import (
    company_domain,
    date_bounds,
    dt_end,
    dt_start,
    field_exists,
    pct_change,
    pick_date_field,
    previous_bounds,
    trend_label,
)


class AnalyticsDashboardService(models.AbstractModel):
    _name = "analytics.dashboard.service"
    _inherit = "analytics.query.engine"
    _description = "Analytics OWL payloads"

    def _group_xmlids(self):
        user = self.env.user
        return {
            "is_management": user.has_group("reports_analytics.group_analytics_management"),
            "is_admin": user.has_group("reports_analytics.group_analytics_admin"),
            "is_manager": user.has_group("reports_analytics.group_analytics_manager"),
            "can_configure": user.has_group("reports_analytics.group_analytics_admin") or user.has_group("base.group_system"),
            "can_edit": user.has_group("reports_analytics.group_analytics_admin")
            or user.has_group("reports_analytics.group_analytics_manager")
            or user.has_group("base.group_system"),
            "can_view_financial": self._can_view_financial(),
        }

    @api.model
    def get_bootstrap(self):
        self.env["analytics.data.source"]._sync_known_sources()
        lookups = self.lookup_filters()
        return {
            "groups": self._group_xmlids(),
            "sources": self.env["analytics.data.source"].get_registry_payload(),
            "properties": lookups["properties"],
            "buildings": lookups["buildings"],
            "users": [
                {"id": rec.id, "name": rec.name}
                for rec in self.env["res.users"].search([("share", "=", False)], limit=80)
            ],
        }

    def _open_domain(self, model_name):
        return list(OPEN_STATE_HINTS.get(model_name, []))

    def _module_score(self, key):
        if key == "compliance":
            data = self._safe_dashboard("compliance.dashboard", "get_dashboard_data")
            if not data:
                return None
            kpis = data.get("kpis") or {}
            return kpis.get("overall_compliance_rate")
        if key == "fire_safety":
            data = self._safe_dashboard("fire.safety.dashboard", "get_dashboard_data")
            if not data or not data.get("compliance"):
                return None
            return (data["compliance"] or {}).get("compliance")
        if key == "energy":
            if "integration.iot.energy.reading" not in self.env:
                return None
            if not self.env["integration.iot.energy.reading"].has_access("read"):
                return None
            return None if not self.env["integration.iot.energy.reading"].search([], limit=1) else 0
        if key == "community":
            count = self._count_model("community.communication.feedback")
            return None if count is None else 0
        return None

    @api.model
    def get_analytics_dashboard(self, filters=None):
        filters = filters or {}
        compliance = self._safe_dashboard("compliance.dashboard", "get_dashboard_data")
        fire = self._safe_dashboard("fire.safety.dashboard", "get_dashboard_data")
        iot = self._safe_dashboard("integration.iot.dashboard", "get_dashboard_data")
        community = self._safe_dashboard("community.communication.dashboard", "get_dashboard_data")

        open_issues = 0
        open_available = False
        for model_name in (
            "compliance.non.compliance",
            "fire.safety.finding",
            "fire.safety.action",
            "community.communication.feedback",
            "integration.iot.alert",
        ):
            count = self._count_model(model_name, self._open_domain(model_name))
            if count is not None:
                open_issues += count
                open_available = True

        compliance_score = None
        if compliance:
            compliance_score = (compliance.get("kpis") or {}).get("overall_compliance_rate")
        elif fire and fire.get("compliance"):
            compliance_score = fire["compliance"].get("compliance")

        energy_value = None
        energy_hint = _("Source unavailable")
        if iot and iot.get("energy"):
            trend = (iot["energy"] or {}).get("trend") or []
            if trend:
                energy_value = sum(row.get("kwh") or 0 for row in trend)
                energy_hint = _("From IoT energy readings")
            elif "integration.iot.energy.reading" in self.env and self.env["integration.iot.energy.reading"].has_access("read"):
                readings = self.env["integration.iot.energy.reading"].search([], limit=500)
                measure = "kwh" if readings and "kwh" in readings._fields else False
                if measure:
                    energy_value = sum(readings.mapped(measure))
                    energy_hint = _("From IoT energy readings")
                elif readings:
                    energy_hint = _("Readings exist but no numeric measure is mapped")

        sla = None
        scores = [value for value in (compliance_score,) if value is not None]
        overall = round(sum(scores) / len(scores), 1) if scores else None

        kpis = [
            self._kpi_value(_("Overall Performance"), overall, suffix="%", hint=_("Average of available module scores") if overall is not None else _("No Data")),
            self._kpi_value(_("Open Issues"), open_issues if open_available else None, hint=_("Open findings, actions, feedback and IoT alerts")),
            self._kpi_unavailable(_("SLA Compliance"), _("No SLA source module is installed")),
            self._kpi_unavailable(_("Operating Cost"), _("Finance source is not available")) if not self._financial_available() else self._financial_kpis()["operating"],
            self._kpi_value(_("Energy Consumption"), energy_value, hint=energy_hint),
            self._kpi_value(_("Compliance Score"), compliance_score, suffix="%", hint=_("From Compliance / Fire & Safety")),
        ]

        performance = self._performance_series()
        modules = self._module_performance(compliance, fire, iot)
        attention = self._attention_items(compliance, fire, iot, community)
        return {
            "kpis": kpis,
            "performance": performance,
            "modules": modules,
            "attention": attention,
            "groups": self._group_xmlids(),
        }

    def _financial_available(self):
        if not self._can_view_financial():
            return False
        return "account.move" in self.env and self.env["account.move"].has_access("read")

    def _financial_kpis(self):
        payload = self.get_financial_analytics({})
        kpis = {row["key"]: row for row in payload.get("kpis") or []}
        return {
            "operating": kpis.get("opex") or self._kpi_unavailable(_("Operating Cost")),
        }

    def _performance_series(self):
        today = fields.Date.context_today(self)
        start = today - timedelta(days=150)
        labels = []
        data = []
        cursor = start.replace(day=1)
        any_data = False
        models = [
            name for name in ("compliance.check", "fire.safety.inspection", "community.communication.feedback", "integration.iot.alert")
            if name in self.env and self.env[name].has_access("read")
        ]
        while cursor <= today:
            nxt = (cursor + timedelta(days=32)).replace(day=1)
            labels.append(cursor.strftime("%b"))
            total = 0
            for name in models:
                model = self.env[name]
                date_field = pick_date_field(model)
                if not date_field:
                    continue
                ftype = model._fields[date_field].type
                if ftype == "datetime":
                    domain = [(date_field, ">=", dt_start(cursor)), (date_field, "<", dt_start(nxt))]
                else:
                    domain = [(date_field, ">=", cursor), (date_field, "<", nxt)]
                total += model.search_count(company_domain(model, self.env.company) + domain)
            if total:
                any_data = True
            data.append(total)
            cursor = nxt
        if not any_data:
            return {"available": False, "labels": [], "series": [], "reason": _("No Data")}
        maximum = max(data) or 1
        scaled = [round(value / maximum * 100, 1) for value in data]
        return {"available": True, "labels": labels, "series": [{"name": _("Activity"), "data": scaled}]}

    def _module_performance(self, compliance, fire, iot):
        rows = []
        if compliance:
            score = (compliance.get("kpis") or {}).get("overall_compliance_rate")
            rows.append({"module": _("Compliance"), "score": score, "available": score is not None, "trend": "stable", "status": "healthy" if (score or 0) >= 80 else "review"})
        else:
            rows.append({"module": _("Compliance"), "score": None, "available": False, "trend": "", "status": "unavailable"})
        if fire and fire.get("compliance"):
            score = fire["compliance"].get("compliance")
            rows.append({"module": _("Fire & Safety"), "score": score, "available": True, "trend": "stable", "status": "healthy" if (score or 0) >= 80 else "review"})
        else:
            rows.append({"module": _("Fire & Safety"), "score": None, "available": bool(fire), "trend": "", "status": "unavailable" if not fire else "review"})
        energy_available = bool(iot and (iot.get("energy") or {}).get("trend"))
        rows.append({
            "module": _("Energy"),
            "score": None,
            "available": energy_available,
            "trend": "stable" if energy_available else "",
            "status": "healthy" if energy_available else "unavailable",
            "reason": "" if energy_available else _("No energy readings"),
        })
        maint = self._count_model("maintenance.request")
        rows.append({
            "module": _("Maintenance"),
            "score": None,
            "available": maint is not None,
            "status": "unavailable" if maint is None else "healthy",
            "reason": _("Module not installed") if maint is None else "",
        })
        rows.append({"module": _("Space Util."), "score": None, "available": False, "status": "unavailable", "reason": _("Space planning source is not installed")})
        return rows

    def _attention_items(self, compliance, fire, iot, community):
        items = []
        if compliance:
            overdue = (compliance.get("kpis") or {}).get("overdue_activities")
            if overdue:
                items.append({"title": _("%s overdue compliance activities") % overdue, "detail": _("Compliance"), "tone": "danger"})
            nc = (compliance.get("kpis") or {}).get("open_non_compliance")
            if nc:
                items.append({"title": _("%s open non-compliances") % nc, "detail": _("Compliance"), "tone": "warning"})
        if fire:
            overdue = fire.get("overdue_inspections")
            if overdue:
                items.append({"title": _("%s overdue fire inspections") % overdue, "detail": _("Fire & Safety"), "tone": "danger"})
            actions = fire.get("open_actions")
            if actions:
                items.append({"title": _("%s open fire-safety actions") % actions, "detail": _("Fire & Safety"), "tone": "warning"})
        if iot:
            attention = iot.get("attention") or []
            for row in attention[:4]:
                items.append({
                    "title": row.get("name") or row.get("title") or _("IoT attention item"),
                    "detail": row.get("hint") or _("Integration & IoT"),
                    "tone": "warning",
                })
        if community:
            feedback = (community.get("kpis") or {}).get("feedback")
            if feedback:
                items.append({"title": _("%s open community feedback items") % feedback, "detail": _("Community"), "tone": "info"})
        return items[:8]

    @api.model
    def get_management_dashboard(self, filters=None):
        groups = self._group_xmlids()
        if not (groups["is_management"] or groups["is_admin"] or groups["is_manager"] or self.env.user.has_group("base.group_system")):
            return {"restricted": True, "reason": _("You do not have access to the management dashboard.")}
        fire = self._safe_dashboard("fire.safety.dashboard", "get_dashboard_data")
        compliance = self._safe_dashboard("compliance.dashboard", "get_dashboard_data")
        iot = self._safe_dashboard("integration.iot.dashboard", "get_dashboard_data")
        financial = self.get_financial_analytics(filters or {})
        uptime = None
        if iot and iot.get("kpis"):
            connected = iot["kpis"].get("connected_devices")
            total = iot["kpis"].get("total_devices") or iot["kpis"].get("devices")
            if connected is not None and total:
                uptime = round(connected / total * 100, 1)
        open_work = self._count_model("maintenance.request", self._open_domain("maintenance.request"))
        audit_pass = None
        if compliance:
            audit_pass = (compliance.get("kpis") or {}).get("overall_compliance_rate")
        pending_certs = None
        if compliance:
            pending_certs = (compliance.get("kpis") or {}).get("expiring_documents")
        safety_score = (fire or {}).get("compliance") or {}
        energy = None
        if iot and iot.get("energy"):
            trend = iot["energy"].get("trend") or []
            energy = sum(row.get("kwh") or 0 for row in trend) if trend else None
        return {
            "restricted": False,
            "groups": groups,
            "uptime": self._kpi_value(_("Overall Uptime"), uptime, suffix="%", hint=_("Connected IoT devices") if uptime is not None else _("No IoT device data")),
            "open_work_orders": self._kpi_value(_("Open Work Orders"), open_work, hint=_("Maintenance") if open_work is not None else _("Maintenance module is not installed")),
            "financial": financial,
            "audit_pass": self._kpi_value(_("Audit Pass Rate"), audit_pass, suffix="%", hint=_("Compliance")),
            "pending_certs": self._kpi_value(_("Pending Certifications"), pending_certs, hint=_("Requires action") if pending_certs else _("Compliance documents")),
            "safety": {
                "available": bool(safety_score),
                "score": safety_score.get("compliance"),
                "inspection": safety_score.get("inspection_score"),
                "equipment": safety_score.get("equipment_score"),
                "action": safety_score.get("action_score"),
            },
            "energy": self._kpi_value(_("Total Consumption"), energy, suffix=" kWh", hint=_("IoT energy")),
            "carbon": self._kpi_unavailable(_("Carbon Footprint"), _("No carbon accounting source is installed")),
            "uptime_trend": self._performance_series(),
        }

    @api.model
    def get_operational_analytics(self, filters=None):
        filters = filters or {}
        start, end = date_bounds(filters.get("date_range"), today=fields.Date.context_today(self))
        open_requests = 0
        open_available = False
        for model_name in ("community.communication.feedback", "fire.safety.incident", "compliance.non.compliance", "integration.iot.alert"):
            count = self._count_model(model_name, self._open_domain(model_name))
            if count is not None:
                open_requests += count
                open_available = True
        resolution = self._average_resolution_hours()
        downtime = self._asset_downtime()
        maintenance_chart = self._maintenance_types(start, end)
        vendors = {"available": False, "reason": _("Vendor performance source is not installed"), "rows": []}
        return {
            "kpis": [
                self._kpi_value(_("Open Requests"), open_requests if open_available else None, hint=_("Feedback, incidents, non-compliances, IoT alerts")),
                self._kpi_value(_("Avg Resolution Time"), resolution, suffix=" h", hint=_("Completed fire-safety inspections") if resolution is not None else _("Insufficient completion timestamps")),
                self._kpi_value(_("Asset Downtime"), downtime, suffix="%", hint=_("Offline IoT devices") if downtime is not None else _("No device status source")),
            ],
            "maintenance": maintenance_chart,
            "vendors": vendors,
        }

    def _average_resolution_hours(self):
        if "fire.safety.inspection" not in self.env or not self.env["fire.safety.inspection"].has_access("read"):
            return None
        Inspection = self.env["fire.safety.inspection"]
        if not field_exists(Inspection, "complete_datetime") or not field_exists(Inspection, "start_datetime"):
            return None
        records = Inspection.search([
            ("complete_datetime", "!=", False),
            ("start_datetime", "!=", False),
        ], limit=200)
        if not records:
            return None
        hours = []
        for rec in records:
            delta = rec.complete_datetime - rec.start_datetime
            hours.append(delta.total_seconds() / 3600.0)
        if not hours:
            return None
        return round(sum(hours) / len(hours), 1)

    def _asset_downtime(self):
        if "integration.iot.device" not in self.env or not self.env["integration.iot.device"].has_access("read"):
            return None
        Device = self.env["integration.iot.device"]
        total = Device.search_count([])
        if not total:
            return None
        offline_domain = [("state", "in", ["offline", "faulty", "alarm"])] if field_exists(Device, "state") else []
        if not offline_domain:
            return None
        offline = Device.search_count(offline_domain)
        return round(offline / total * 100.0, 1)

    def _maintenance_types(self, start, end):
        if "maintenance.request" in self.env and self.env["maintenance.request"].has_access("read"):
            return {"available": True, "labels": [], "series": [], "reason": ""}
        inspections = "fire.safety.inspection" in self.env and self.env["fire.safety.inspection"].has_access("read")
        if not inspections:
            return {"available": False, "reason": _("Maintenance module is not installed"), "labels": [], "series": []}
        model = self.env["fire.safety.inspection"]
        date_field = pick_date_field(model)
        labels = []
        preventive = []
        corrective = []
        cursor = start.replace(day=1) if hasattr(start, "replace") else start
        today = fields.Date.context_today(self)
        while cursor <= today and len(labels) < 6:
            nxt = (cursor + timedelta(days=32)).replace(day=1)
            labels.append(cursor.strftime("%b"))
            domain = company_domain(model, self.env.company)
            if date_field:
                ftype = model._fields[date_field].type
                if ftype == "datetime":
                    domain += [(date_field, ">=", dt_start(cursor)), (date_field, "<", dt_start(nxt))]
                else:
                    domain += [(date_field, ">=", cursor), (date_field, "<", nxt)]
            preventive.append(model.search_count(domain + [("inspection_type", "ilike", "inspect")] if field_exists(model, "inspection_type") else domain))
            corrective.append(model.search_count(domain + [("state", "in", ["pending", "in_progress"])] if field_exists(model, "state") else domain))
            cursor = nxt
        return {
            "available": True,
            "labels": labels,
            "series": [
                {"name": _("Inspections"), "data": preventive},
                {"name": _("Open / pending"), "data": corrective},
            ],
            "reason": _("Shown from Fire & Safety inspections until Maintenance is installed"),
        }

    @api.model
    def get_financial_analytics(self, filters=None):
        if not self._can_view_financial():
            return {
                "available": False,
                "restricted": True,
                "reason": _("Financial analytics are limited to Management and Admin roles."),
                "kpis": [],
                "budget": {"available": False},
                "opex": {"available": False},
                "properties": [],
            }
        if not self._financial_available():
            return {
                "available": False,
                "restricted": False,
                "reason": _("Finance/Accounting source is not installed."),
                "kpis": [
                    self._kpi_unavailable(_("Total Revenue")),
                    self._kpi_unavailable(_("Operating Expenses")),
                    self._kpi_unavailable(_("Outstanding Amounts")),
                    self._kpi_unavailable(_("Collection Rate")),
                ],
                "budget": {"available": False, "reason": _("No budget source")},
                "opex": {"available": False, "reason": _("No expense source")},
                "properties": [],
            }
        Move = self.env["account.move"]
        start, end = date_bounds(filters.get("date_range") if filters else "this_year", today=fields.Date.context_today(self))
        invoices = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
        ])
        bills = Move.search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
        ])
        revenue = sum(invoices.mapped("amount_total_signed")) if invoices else 0.0
        opex = abs(sum(bills.mapped("amount_total_signed"))) if bills else 0.0
        residual = sum(invoices.mapped("amount_residual")) if invoices and "amount_residual" in invoices._fields else 0.0
        collection = round((1 - residual / revenue) * 100, 1) if revenue else None
        return {
            "available": True,
            "restricted": False,
            "reason": "",
            "kpis": [
                {"key": "revenue", **self._kpi_value(_("Total Revenue"), round(revenue, 2))},
                {"key": "opex", **self._kpi_value(_("Operating Expenses"), round(opex, 2))},
                {"key": "outstanding", **self._kpi_value(_("Outstanding Amounts"), round(residual, 2))},
                {"key": "collection", **self._kpi_value(_("Collection Rate"), collection, suffix="%")},
            ],
            "budget": {"available": False, "reason": _("No FMS budget source is registered")},
            "opex_chart": self._monthly_sums(bills if bills else invoices, start, end),
            "properties": [],
        }

    def _monthly_sums(self, records, start, end):
        if not records:
            return {"available": False, "labels": [], "series": []}
        buckets = defaultdict(float)
        for rec in records:
            day = rec.invoice_date or fields.Date.context_today(self)
            key = day.strftime("%Y-%m")
            buckets[key] += abs(rec.amount_total_signed or 0.0)
        labels = sorted(buckets)
        return {"available": bool(labels), "labels": labels, "series": [{"name": _("Amount"), "data": [round(buckets[k], 2) for k in labels]}]}

    @api.model
    def get_trend_analysis(self, filters=None):
        filters = filters or {}
        sources = self.env["analytics.data.source"].get_registry_payload()
        available = [row for row in sources if row["available"]]
        metric_key = filters.get("metric") or (available[0]["technical_identifier"] if available else False)
        source = self.env["analytics.data.source"].search([("technical_identifier", "=", metric_key)], limit=1)
        if not source:
            source = self.env["analytics.data.source"].search([("active", "=", True)], limit=1)
        model, error = self._model_for(source) if source else (False, _("No available source"))
        if error:
            return {
                "available": False,
                "reason": error,
                "metrics": available,
                "kpis": [],
                "chart": {"labels": [], "current": [], "previous": []},
                "trend": "Stable",
            }
        start, end = date_bounds(filters.get("date_range") or "last_30", today=fields.Date.context_today(self))
        prev_start, prev_end = previous_bounds(start, end)
        date_field = pick_date_field(model)
        extra = []
        if filters.get("category") and field_exists(model, "category"):
            extra.append(("category", "=", filters["category"]))
        current_count = model.search_count(self._period_domain(model, date_field, start, end) + extra)
        previous_count = model.search_count(self._period_domain(model, date_field, prev_start, prev_end) + extra)
        change = pct_change(current_count, previous_count)
        labels, current_series, previous_series = self._daily_compare(model, date_field, start, end, prev_start)
        return {
            "available": True,
            "reason": "",
            "metrics": available,
            "source": source.technical_identifier,
            "kpis": [
                {**self._kpi_value(_("Volume"), current_count, hint=_("This period")), "change": change, "trend": trend_label(change)},
                self._kpi_value(_("Previous Period"), previous_count),
                self._kpi_value(_("Change %"), change, suffix="%"),
            ],
            "chart": {"labels": labels, "current": current_series, "previous": previous_series},
            "trend": trend_label(change),
        }

    def _period_domain(self, model, date_field, start, end):
        domain = company_domain(model, self.env.company)
        if not date_field or not field_exists(model, date_field):
            return domain
        ftype = model._fields[date_field].type
        if ftype == "datetime":
            return domain + [(date_field, ">=", dt_start(start)), (date_field, "<=", dt_end(end))]
        return domain + [(date_field, ">=", start), (date_field, "<=", end)]

    def _daily_compare(self, model, date_field, start, end, prev_start):
        labels = []
        current = []
        previous = []
        if not date_field:
            return labels, current, previous
        span = (end - start).days + 1
        for offset in range(min(span, 31)):
            day = start + timedelta(days=offset)
            prev = prev_start + timedelta(days=offset)
            labels.append(_("Day %s") % (offset + 1))
            current.append(model.search_count(self._period_domain(model, date_field, day, day)))
            previous.append(model.search_count(self._period_domain(model, date_field, prev, prev)))
        return labels, current, previous

    @api.model
    def get_cross_module(self, filters=None):
        filters = filters or {}
        sources = [row for row in self.env["analytics.data.source"].get_registry_payload() if row["available"]]
        if len(sources) < 2:
            return {
                "available": False,
                "reason": _("At least two available data sources are required."),
                "sources": sources,
                "rows": [],
                "chart": {"labels": [], "a": [], "b": []},
                "insight": False,
                "anomalies": [],
            }
        source_a = self.env["analytics.data.source"].browse(int(filters.get("module_a") or sources[0]["id"]))
        source_b = self.env["analytics.data.source"].browse(int(filters.get("module_b") or sources[1]["id"]))
        model_a, err_a = self._model_for(source_a)
        model_b, err_b = self._model_for(source_b)
        if err_a or err_b:
            return {
                "available": False,
                "reason": err_a or err_b,
                "sources": sources,
                "rows": [],
                "chart": {"labels": [], "a": [], "b": []},
                "insight": False,
                "anomalies": [],
            }
        start, end = date_bounds(filters.get("date_range") or "last_30", today=fields.Date.context_today(self))
        labels = []
        series_a = []
        series_b = []
        date_a = pick_date_field(model_a)
        date_b = pick_date_field(model_b)
        for offset in range(min((end - start).days + 1, 30)):
            day = start + timedelta(days=offset)
            labels.append(day.strftime("%d %b"))
            series_a.append(model_a.search_count(self._period_domain(model_a, date_a, day, day)))
            series_b.append(model_b.search_count(self._period_domain(model_b, date_b, day, day)))
        correlation = self._pearson(series_a, series_b)
        insight = False
        if correlation is not None and len(series_a) >= 5:
            insight = {
                "title": _("Relationship between %s and %s") % (source_a.name, source_b.name),
                "body": _("Pearson correlation on daily volumes is %.2f. This is a descriptive statistic, not a causal model.") % correlation,
                "confidence": None,
            }
        else:
            insight = {
                "title": _("Insufficient overlapping data"),
                "body": _("No prediction or correlation confidence is shown because the series is too short or constant."),
                "confidence": None,
            }
        return {
            "available": True,
            "reason": "",
            "sources": sources,
            "module_a": source_a.id,
            "module_b": source_b.id,
            "chart": {"labels": labels, "a": series_a, "b": series_b, "name_a": source_a.name, "name_b": source_b.name},
            "insight": insight,
            "anomalies": [],
            "rows": [],
            "correlation": correlation,
        }

    def _pearson(self, xs, ys):
        if not xs or not ys or len(xs) != len(ys) or len(xs) < 5:
            return None
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
        den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
        den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
        if not den_x or not den_y:
            return None
        return round(num / (den_x * den_y), 3)

    @api.model
    def get_predictive_analytics(self, filters=None):
        """Architecture only: do not invent ML output."""
        return {
            "available": False,
            "reason": _("No prediction available — insufficient data"),
            "items": [],
            "historical_basis": _("A predictive model is not configured. Historical series can be added later without changing this screen contract."),
        }

    @api.model
    def run_analysis(self, vals):
        vals = vals or {}
        analysis_type = vals.get("analysis_type") or "operational"
        self.env["analytics.audit.log"].log_event(
            "analyze",
            _("Ran %s analysis") % analysis_type,
            related_module=vals.get("module"),
            new_value=str(vals),
        )
        screens = {
            "operational": "reports_analytics.action_operational",
            "financial": "reports_analytics.action_financial",
            "trends": "reports_analytics.action_trends",
            "cross_module": "reports_analytics.action_cross_module",
            "predictive": "reports_analytics.action_predictive",
        }
        return {"tag": screens.get(analysis_type, "reports_analytics.action_operational"), "filters": vals}

    @api.model
    def search_reports(self, params=None):
        params = params or {}
        domain = [("active", "=", True)]
        if params.get("search"):
            domain.append(("name", "ilike", params["search"]))
        if params.get("module"):
            domain.append(("source_module", "=", params["module"]))
        if params.get("report_type"):
            domain.append(("report_type", "=", params["report_type"]))
        if params.get("status"):
            domain.append(("status", "=", params["status"]))
        if params.get("library"):
            domain.append(("status", "in", ["active", "scheduled"]))
        offset = int(params.get("offset") or 0)
        limit = int(params.get("limit") or 20)
        Report = self.env["analytics.report"]
        total = Report.search_count(domain)
        rows = Report.search(domain, offset=offset, limit=limit, order="write_date desc")
        return {
            "total": total,
            "rows": [rec.ui_row() for rec in rows],
        }
