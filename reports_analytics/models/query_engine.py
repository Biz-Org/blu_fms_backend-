# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

from .utils import (
    company_domain,
    date_bounds,
    dt_end,
    dt_start,
    field_exists,
    parse_domain,
    parse_json,
    pick_date_field,
)

SKIP_FIELD_TYPES = {"binary", "html", "one2many", "many2many"}
PREVIEW_LIMIT = 50
EXECUTE_LIMIT = 5000


class AnalyticsQueryEngine(models.AbstractModel):
    _name = "analytics.query.engine"
    _description = "Analytics Query Engine"

    def _can_view_financial(self):
        user = self.env.user
        return user.has_group("reports_analytics.group_analytics_management") or user.has_group(
            "reports_analytics.group_analytics_admin"
        ) or user.has_group("base.group_system")

    def _source(self, source):
        if isinstance(source, int):
            source = self.env["analytics.data.source"].browse(source)
        return source

    def _model_for(self, source):
        source = self._source(source)
        if not source:
            return False, _("Data source is missing")
        model = source.get_model()
        if not model:
            _available, reason = source._availability()
            return False, reason or _("Data unavailable")
        return model, False

    @api.model
    def get_source_schema(self, source_id):
        source = self.env["analytics.data.source"].browse(source_id)
        model, error = self._model_for(source)
        if error:
            return {"available": False, "reason": error, "fields": [], "metrics": [], "date_field": False}
        fields_payload = []
        metrics = [{"name": "__count", "label": _("Count of records"), "type": "integer", "aggregation": "count"}]
        for name, field in model._fields.items():
            if name == "id" or not field.store or field.type in SKIP_FIELD_TYPES:
                continue
            if getattr(field, "automatic", False) or name in ("message_main_attachment_id",):
                continue
            item = {
                "name": name,
                "label": field.string or name,
                "type": field.type,
                "groupable": field.type in ("char", "selection", "many2one", "boolean", "date", "datetime", "integer"),
                "filterable": field.type in ("char", "selection", "many2one", "boolean", "date", "datetime", "integer", "float", "monetary"),
            }
            fields_payload.append(item)
            if field.type in ("integer", "float", "monetary") and name != "id":
                metrics.append({
                    "name": name,
                    "label": field.string or name,
                    "type": field.type,
                    "aggregation": "sum",
                })
        date_field = pick_date_field(model)
        return {
            "available": True,
            "reason": "",
            "model": model._name,
            "fields": fields_payload[:80],
            "metrics": metrics[:40],
            "date_field": date_field,
            "has_property": field_exists(model, "property_id"),
            "has_building": field_exists(model, "building_id"),
            "has_state": field_exists(model, "state"),
        }

    def _apply_filters(self, model, filters):
        filters = filters or {}
        domain = list(parse_domain(filters.get("domain")))
        domain += company_domain(model, self.env.company)
        date_field = filters.get("date_field") or pick_date_field(model)
        start, end = date_bounds(
            filters.get("date_range"),
            filters.get("date_from"),
            filters.get("date_to"),
            today=fields.Date.context_today(self),
        )
        if date_field and field_exists(model, date_field):
            ftype = model._fields[date_field].type
            if ftype == "datetime":
                domain += [(date_field, ">=", dt_start(start)), (date_field, "<=", dt_end(end))]
            else:
                domain += [(date_field, ">=", start), (date_field, "<=", end)]
        for key, fname in (
            ("property_id", "property_id"),
            ("building_id", "building_id"),
            ("unit_id", "unit_id"),
            ("vendor_id", "vendor_id"),
            ("department_id", "department_id"),
            ("priority", "priority"),
            ("category", "category"),
            ("status", "state"),
        ):
            value = filters.get(key)
            if value in (None, False, "", "all"):
                continue
            if field_exists(model, fname):
                domain.append((fname, "=", value))
        if filters.get("module_state") and field_exists(model, "state"):
            domain.append(("state", "=", filters["module_state"]))
        return domain, start, end, date_field

    def _display(self, value):
        if isinstance(value, tuple) and len(value) == 2:
            return value[1]
        if value is False:
            return ""
        return value

    def _aggregate(self, model, domain, metric):
        aggregation = (metric or {}).get("aggregation") or "count"
        field_name = (metric or {}).get("name") or "__count"
        if aggregation == "count" or field_name == "__count":
            return float(model.search_count(domain))
        if not field_exists(model, field_name):
            return None
        try:
            grouped = model.read_group(domain, [field_name], [], lazy=False)
        except Exception:
            return None
        if not grouped:
            return 0.0
        key = f"{field_name}_{aggregation}" if aggregation != "sum" else field_name
        row = grouped[0]
        if aggregation == "avg":
            count = row.get("__count") or row.get(field_name + "_count") or 0
            total = row.get(field_name) or 0
            return round(float(total) / count, 2) if count else 0.0
        if aggregation == "min":
            return row.get(f"min_{field_name}", row.get(field_name))
        if aggregation == "max":
            return row.get(f"max_{field_name}", row.get(field_name))
        return row.get(field_name) or 0.0

    @api.model
    def execute_config(self, config, persist=False):
        config = parse_json(config, {})
        source_id = config.get("data_source_id")
        source = self.env["analytics.data.source"].browse(source_id) if source_id else self.env["analytics.data.source"]
        model, error = self._model_for(source)
        visualization = config.get("visualization") or "table"
        selected = config.get("fields") or []
        metrics = config.get("metrics") or []
        grouping = config.get("grouping") or []
        filters = config.get("filters") or {}
        if error:
            return {
                "available": False,
                "reason": error,
                "columns": [],
                "rows": [],
                "kpis": [],
                "chart": {"labels": [], "series": []},
                "insights": [],
                "visualization": visualization,
                "row_count": 0,
            }
        domain, start, end, date_field = self._apply_filters(model, filters)
        limit = PREVIEW_LIMIT if not persist else EXECUTE_LIMIT
        field_names = [name for name in selected if field_exists(model, name)]
        if "id" not in field_names:
            field_names = ["id"] + field_names
        if not any(name != "id" for name in field_names):
            for fallback in ("name", "display_name", "state", "create_date"):
                if field_exists(model, fallback) and fallback not in field_names:
                    field_names.append(fallback)
                    if len(field_names) >= 4:
                        break
        records = model.search_read(domain, field_names, limit=limit, order="id desc")
        columns = []
        for name in field_names:
            if name == "id":
                columns.append({"name": "id", "label": _("ID")})
                continue
            field = model._fields.get(name)
            columns.append({"name": name, "label": field.string if field else name})
        rows = []
        for rec in records:
            row = {"id": rec.get("id"), "model": model._name}
            for name in field_names:
                row[name] = self._display(rec.get(name))
            rows.append(row)
        kpi_cards = []
        for metric in metrics:
            value = self._aggregate(model, domain, metric)
            kpi_cards.append({
                "label": metric.get("label") or metric.get("name") or _("Metric"),
                "value": value,
                "available": value is not None,
            })
        if not kpi_cards:
            kpi_cards.append({"label": _("Records"), "value": model.search_count(domain), "available": True})
        chart = self._chart_payload(model, domain, grouping, metrics, visualization, date_field, start, end)
        insights = self._insights(kpi_cards, model, domain)
        return {
            "available": True,
            "reason": "",
            "model": model._name,
            "source_id": source.id,
            "source_name": source.name,
            "visualization": visualization,
            "columns": columns,
            "rows": rows,
            "kpis": kpi_cards,
            "chart": chart,
            "insights": insights,
            "row_count": model.search_count(domain),
            "date_from": fields.Date.to_string(start),
            "date_to": fields.Date.to_string(end),
        }

    def _chart_payload(self, model, domain, grouping, metrics, visualization, date_field, start, end):
        labels = []
        series = []
        measure = (metrics[0]["name"] if metrics else "__count")
        if grouping and field_exists(model, grouping[0]):
            group_field = grouping[0]
            try:
                grouped = model.read_group(domain, [measure if measure != "__count" else "id"], [group_field], lazy=False)
            except Exception:
                grouped = []
            for row in grouped:
                label = row.get(group_field)
                if isinstance(label, tuple):
                    label = label[1]
                labels.append(str(label or _("Undefined")))
                if measure == "__count":
                    series.append(row.get(group_field + "_count") or row.get("__count") or 0)
                else:
                    series.append(row.get(measure) or 0)
        elif date_field and field_exists(model, date_field):
            cursor = start
            while cursor <= end and len(labels) < 31:
                nxt = cursor + timedelta(days=1)
                ftype = model._fields[date_field].type
                if ftype == "datetime":
                    day_domain = domain + [(date_field, ">=", dt_start(cursor)), (date_field, "<", dt_start(nxt))]
                else:
                    day_domain = domain + [(date_field, "=", cursor)]
                labels.append(cursor.strftime("%d %b"))
                series.append(model.search_count(day_domain))
                cursor = nxt
        else:
            labels = [_("Records")]
            series = [model.search_count(domain)]
        return {"labels": labels, "series": [{"name": _("Value"), "data": series}]}

    def _insights(self, kpis, model, domain):
        notes = []
        total = model.search_count(domain)
        if not total:
            notes.append({
                "tone": "info",
                "title": _("No matching records"),
                "body": _("The selected source has no rows for the current filters."),
            })
            return notes
        notes.append({
            "tone": "info",
            "title": _("Record volume"),
            "body": _("%s records match the current filters.") % total,
        })
        if field_exists(model, "state"):
            grouped = model.read_group(domain, ["id"], ["state"], lazy=False)
            if grouped:
                top = max(grouped, key=lambda row: row.get("state_count") or row.get("__count") or 0)
                state = top.get("state")
                notes.append({
                    "tone": "warning" if state in ("failed", "overdue", "critical") else "success",
                    "title": _("Most common status"),
                    "body": _("%s is the most frequent status in this result set.") % (state or _("Undefined")),
                })
        return notes[:4]

    def _count_model(self, model_name, extra=None):
        if model_name not in self.env or not self.env[model_name].has_access("read"):
            return None
        model = self.env[model_name]
        domain = company_domain(model, self.env.company) + (extra or [])
        try:
            return model.search_count(domain)
        except Exception:
            return None

    def _safe_dashboard(self, model_name, method):
        if model_name not in self.env:
            return None
        try:
            return getattr(self.env[model_name], method)()
        except AccessError:
            return None
        except Exception:
            return None

    @api.model
    def lookup_filters(self):
        properties = []
        buildings = []
        for model_name, label_field in (
            ("fire.safety.property", "name"),
            ("compliance.property", "name"),
            ("integration.iot.property", "name"),
            ("community.communication.community", "name"),
        ):
            if model_name in self.env and self.env[model_name].has_access("read"):
                for rec in self.env[model_name].search_read([], [label_field], limit=100):
                    properties.append({
                        "key": f"{model_name}:{rec['id']}",
                        "id": rec["id"],
                        "model": model_name,
                        "name": rec.get(label_field) or str(rec["id"]),
                    })
        for model_name in ("fire.safety.building", "compliance.building", "integration.iot.building", "community.communication.building"):
            if model_name in self.env and self.env[model_name].has_access("read"):
                fields_list = ["name"]
                if "property_id" in self.env[model_name]._fields:
                    fields_list.append("property_id")
                for rec in self.env[model_name].search_read([], fields_list, limit=200):
                    buildings.append({
                        "key": f"{model_name}:{rec['id']}",
                        "id": rec["id"],
                        "model": model_name,
                        "name": rec.get("name") or str(rec["id"]),
                        "property_id": rec.get("property_id")[0] if isinstance(rec.get("property_id"), tuple) else rec.get("property_id"),
                    })
        return {"properties": properties, "buildings": buildings}

    def _kpi_unavailable(self, label, hint=""):
        return {
            "label": label,
            "value": None,
            "display": _("No Data"),
            "available": False,
            "hint": hint or _("Data unavailable"),
            "change": None,
            "tone": "muted",
        }

    def _kpi_value(self, label, value, hint="", suffix="", change=None, tone=""):
        if value is None:
            return self._kpi_unavailable(label, hint)
        display = value
        if isinstance(value, float):
            display = f"{value:.1f}{suffix}"
        elif suffix:
            display = f"{value}{suffix}"
        return {
            "label": label,
            "value": value,
            "display": display,
            "available": True,
            "hint": hint,
            "change": change,
            "tone": tone or "default",
        }
