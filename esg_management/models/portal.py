import csv
import io
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class EsgPortal(models.AbstractModel):
    _name = "esg.portal"
    _description = "ESG Portal API"

    UNITS = {
        "energy": "kWh",
        "water": "m3",
        "carbon": "tCO2e",
        "waste": "%",
        "renewable": "%",
    }

    @api.model
    def _seed_demo(self):
        if self.env["esg.reading"].search_count([]):
            return
        sites = [
            ("ESG-HQ", "HQ Campus", "Main Tower", "office", 1.15, 92000),
            ("ESG-NR", "North Region", "Logistics Center A", "warehouse", 0.82, 140000),
            ("ESG-WW", "West Warehouse", "Storage Hub", "warehouse", 0.7, 160000),
            ("ESG-RD", "R&D Campus", "R&D Facility", "manufacturing", 0.95, 78000),
            ("ESG-DC", "Data Center North", "Data Hall", "office", 1.35, 54000),
            ("ESG-RE", "Retail East", "Pavilion A", "other", 0.62, 48000),
        ]
        Property = self.env["property.property"]
        Building = self.env["property.building"]
        created = []
        for code, prop_name, bld_name, segment, factor, area in sites:
            prop = Property.search([("code", "=", code)], limit=1)
            if not prop:
                prop = Property.create({
                    "name": prop_name,
                    "code": code,
                    "property_type": "commercial",
                    "area_sqft": area,
                    "city": "Pune",
                })
            building = Building.search([("property_id", "=", prop.id), ("name", "=", bld_name)], limit=1)
            if not building:
                building = Building.create({"name": bld_name, "property_id": prop.id, "usage": "commercial"})
            created.append((prop, building, segment, factor))

        rows = []
        months = []
        for year in (2024, 2025, 2026):
            last = 10 if year == 2026 else 12
            for month in range(1, last + 1):
                months.append(date(year, month, 1))
        for index, (prop, building, segment, factor) in enumerate(created):
            for month_index, day in enumerate(months):
                wave = 0.78 + ((month_index + index) % 6) * 0.07
                energy = round(18500 * factor * wave, 1)
                water = round(1350 * factor * wave, 1)
                carbon = round(52 * factor * wave, 2)
                rows.append({
                    "property_id": prop.id, "building_id": building.id, "metric": "energy",
                    "date": day, "value": round(energy * 0.65, 1), "unit": "kWh",
                    "peak": True, "segment": segment,
                })
                rows.append({
                    "property_id": prop.id, "building_id": building.id, "metric": "energy",
                    "date": day, "value": round(energy * 0.35, 1), "unit": "kWh",
                    "peak": False, "segment": segment,
                })
                rows.append({
                    "property_id": prop.id, "building_id": building.id, "metric": "water",
                    "date": day, "value": water, "unit": "m3", "segment": segment,
                })
                for scope, share in (("1", 0.25), ("2", 0.65), ("3", 0.10)):
                    rows.append({
                        "property_id": prop.id, "building_id": building.id, "metric": "carbon",
                        "date": day, "value": round(carbon * share, 2), "unit": "tCO2e",
                        "scope": scope, "segment": segment,
                    })
                rows.append({
                    "property_id": prop.id, "building_id": building.id, "metric": "waste",
                    "date": day, "value": round(72 + ((month_index + index) % 5) * 2.4, 1),
                    "unit": "%", "segment": segment,
                })
                rows.append({
                    "property_id": prop.id, "building_id": building.id, "metric": "renewable",
                    "date": day, "value": round(34 + ((month_index + index) % 4) * 2.5, 1),
                    "unit": "%", "segment": segment,
                })
        self.env["esg.reading"].create(rows)
        self.env["esg.kpi"].create([
            {"name": "Grid Energy Consumption", "category": "energy", "metric": "energy", "target": 1.20, "unit": "GWh", "direction": "lower", "scale": 1000000},
            {"name": "Total Water Withdrawal", "category": "water", "metric": "water", "target": 90, "unit": "ML", "direction": "lower", "scale": 1000},
            {"name": "Scope 1 Emissions", "category": "carbon", "metric": "carbon", "target": 900, "unit": "tCO2e", "direction": "lower", "scale": 1},
            {"name": "Waste Diversion Rate", "category": "waste", "metric": "waste", "target": 85, "unit": "%", "direction": "higher", "scale": 1},
        ])
        self.env["esg.target"].create([
            {"name": "Reduce Energy Intensity", "subtitle": "kWh per sqft", "category": "energy", "metric": "energy", "measure": "intensity", "direction": "lower", "baseline": 18, "target_value": 13, "unit": "kWh/sqft", "due_date": "2026-12-31"},
            {"name": "Zero Waste to Landfill", "subtitle": "Diversion rate", "category": "waste", "metric": "waste", "measure": "rate", "direction": "higher", "baseline": 60, "target_value": 95, "unit": "%", "due_date": "2026-12-31"},
            {"name": "Scope 1 & 2 Emissions", "subtitle": "Carbon reduction", "category": "carbon", "metric": "carbon", "measure": "total", "direction": "lower", "baseline": 4200, "target_value": 3000, "unit": "tCO2e", "due_date": "2026-12-31"},
            {"name": "Facility Water Usage", "subtitle": "Water conservation", "category": "water", "metric": "water", "measure": "total", "direction": "lower", "baseline": 120000, "target_value": 90000, "unit": "m3", "due_date": "2026-12-31"},
            {"name": "Renewable Energy Mix", "subtitle": "Energy reduction", "category": "energy", "metric": "renewable", "measure": "rate", "direction": "higher", "baseline": 15, "target_value": 40, "unit": "%", "due_date": "2026-12-31"},
        ])
        now = fields.Datetime.now()
        self.env["esg.activity"].create([
            {"name": "Energy audit completed for HQ Building.", "detail": "Today, 10:30 AM", "metric": "energy", "occurred_at": now},
            {"name": "Water leak detected and resolved in North Campus.", "detail": "Yesterday, 14:15", "metric": "water", "occurred_at": now - timedelta(days=1)},
            {"name": "Monthly sustainability report published.", "detail": "Oct 01, 09:00 AM", "metric": "report", "occurred_at": now - timedelta(days=2)},
        ])
        self.env["esg.report"].create([
            {"name": "Q3 2026 Carbon Summary", "template": "carbon", "period_label": "Q3 2026", "report_date": "2026-10-01", "status": "done"},
            {"name": "Annual Water Analysis", "template": "water", "period_label": "FY 2025", "report_date": "2026-09-28", "status": "done"},
            {"name": "YTD Energy Efficiency", "template": "energy", "period_label": "YTD 2026", "report_date": date.today(), "status": "processing"},
        ])

    def _history_months(self):
        today = date.today()
        months = []
        for year in (today.year - 2, today.year - 1, today.year):
            last = today.month if year == today.year else 12
            for month in range(1, last + 1):
                months.append(date(year, month, 1))
        return months

    def _rows_for_building(self, prop, building, index, months):
        usage = building.usage if building else False
        segment = {
            "residential": "other",
            "parking": "logistics",
            "mixed": "office",
            "commercial": "office",
        }.get(usage, "office")
        factor = 0.68 + (index % 6) * 0.11
        rows = []
        for month_index, day in enumerate(months):
            wave = 0.78 + ((month_index + index) % 6) * 0.07
            energy = round(18500 * factor * wave, 1)
            water = round(1350 * factor * wave, 1)
            carbon = round(52 * factor * wave, 2)
            base = {
                "property_id": prop.id,
                "building_id": building.id if building else False,
                "date": day,
                "segment": segment,
            }
            rows.append({**base, "metric": "energy", "value": round(energy * 0.65, 1), "unit": "kWh", "peak": True})
            rows.append({**base, "metric": "energy", "value": round(energy * 0.35, 1), "unit": "kWh", "peak": False})
            rows.append({**base, "metric": "water", "value": water, "unit": "m3"})
            for scope, share in (("1", 0.25), ("2", 0.65), ("3", 0.10)):
                rows.append({**base, "metric": "carbon", "value": round(carbon * share, 2), "unit": "tCO2e", "scope": scope})
            rows.append({**base, "metric": "waste", "value": round(72 + ((month_index + index) % 5) * 2.4, 1), "unit": "%"})
            rows.append({**base, "metric": "renewable", "value": round(34 + ((month_index + index) % 4) * 2.5, 1), "unit": "%"})
        return rows

    def _ensure_property_readings(self):
        Reading = self.env["esg.reading"]
        covered = {
            group["building_id"][0]
            for group in Reading.read_group([("metric", "=", "energy"), ("building_id", "!=", False)], ["building_id"], ["building_id"])
            if group.get("building_id")
        }
        months = self._history_months()
        rows = []
        for index, building in enumerate(self.env["property.building"].search([])):
            if building.id in covered or not building.property_id:
                continue
            rows.extend(self._rows_for_building(building.property_id, building, index, months))
        if rows:
            Reading.create(rows)

    def _filters(self, filters):
        filters = filters or {}
        property_id = int(filters.get("property_id") or 0)
        building_id = int(filters.get("building_id") or 0)
        if building_id:
            building = self.env["property.building"].browse(building_id)
            if not building.exists() or (property_id and building.property_id.id != property_id):
                building_id = 0
            elif not property_id and building.property_id:
                property_id = building.property_id.id
        return {
            "property_id": property_id,
            "building_id": building_id,
            "period": filters.get("period") or "ytd",
        }

    def _bounds(self, period):
        today = date.today()
        if period == "prev":
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
        elif period == "30d":
            start = today - timedelta(days=30)
            end = today
        elif period == "12m":
            start = date(today.year - 1, today.month, 1)
            end = today
        else:
            start = date(today.year, 1, 1)
            end = today
        return start, end

    def _previous_bounds(self, start, end):
        span = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        return prev_start, prev_end

    def _readings(self, metric, filters, start, end):
        domain = [("metric", "=", metric), ("date", ">=", start), ("date", "<=", end)]
        if filters["property_id"]:
            domain.append(("property_id", "=", filters["property_id"]))
        if filters["building_id"]:
            domain.append(("building_id", "=", filters["building_id"]))
        return self.env["esg.reading"].search(domain)

    def _sum(self, readings):
        return sum(readings.mapped("value"))

    def _avg(self, readings):
        values = readings.mapped("value")
        return sum(values) / len(values) if values else 0.0

    def _fmt(self, value, kind="num"):
        value = float(value or 0)
        sign = "-" if value < 0 else ""
        value = abs(value)
        if kind == "pct":
            return f"{sign}{value:.1f}%"
        if value >= 1000000:
            return f"{sign}{value / 1000000:.2f}M"
        if value >= 1000:
            return f"{sign}{value / 1000:.1f}k"
        if abs(value - round(value)) < 0.05:
            return f"{sign}{int(round(value))}"
        return f"{sign}{value:.1f}"

    def _delta(self, current, previous):
        if not previous:
            return 0.0
        return (current - previous) / previous * 100

    def _conservation(self, readings):
        """Average drop from each building's peak month to its latest month."""
        groups = {}
        for rec in readings:
            building_key = rec.building_id.id or 0
            month = rec.date.strftime("%Y-%m")
            bucket = groups.setdefault(building_key, {})
            bucket[month] = bucket.get(month, 0) + rec.value
        scores = []
        for months in groups.values():
            values = [months[key] for key in sorted(months)]
            peak = max(values) if values else 0
            if peak:
                scores.append((peak - values[-1]) / peak * 100)
        reduction = round(sum(scores) / len(scores), 1) if scores else 0.0
        goal_fill = round(min(100.0, max(reduction, 0) / 15 * 100), 1)
        return reduction, goal_fill

    def _bars(self, pairs):
        peak = max([value for _label, value in pairs] or [0]) or 1
        return [
            {"label": label, "value": round(value, 2), "label_value": self._fmt(value), "pct": round(value / peak * 100)}
            for label, value in pairs
        ]

    def _month_key(self, day):
        return day.strftime("%Y-%m")

    def _month_label(self, key):
        year, month = key.split("-")
        return date(int(year), int(month), 1).strftime("%b %y")

    def _by_month(self, readings):
        buckets = {}
        for rec in readings:
            key = self._month_key(rec.date)
            buckets[key] = buckets.get(key, 0) + rec.value
        keys = sorted(buckets)
        return [(self._month_label(key), buckets[key]) for key in keys]

    def _achievement(self, direction, baseline, target, current):
        if direction == "lower":
            span = baseline - target
            done = baseline - current
        else:
            span = target - baseline
            done = current - baseline
        if not span:
            return 0
        return max(0, min(100, round(done / span * 100)))

    def _status_from_variance(self, variance, higher_better=False):
        good = variance >= 0 if higher_better else variance <= 0
        if good:
            return "on_track"
        if abs(variance) < 5:
            return "review"
        return "at_risk"

    def _status_from_achievement(self, achievement, direction):
        if direction == "higher":
            if achievement >= 100:
                return "achieved"
            if achievement >= 90:
                return "on_track"
            if achievement >= 75:
                return "review"
            return "below"
        if achievement >= 100:
            return "achieved"
        if achievement >= 85:
            return "on_track"
        if achievement >= 70:
            return "review"
        return "at_risk"

    def _area(self, filters):
        domain = [("area_sqft", ">", 0)]
        if filters["property_id"]:
            domain.append(("id", "=", filters["property_id"]))
        props = self.env["property.property"].search(domain)
        if filters["building_id"]:
            building = self.env["property.building"].browse(filters["building_id"])
            if building.property_id:
                props = building.property_id
        return sum(props.mapped("area_sqft")) or 1

    def _live_current(self, target, filters, start, end):
        readings = self._readings(target.metric, filters, start, end)
        if target.measure == "rate":
            return self._avg(readings)
        if target.measure == "intensity":
            return self._sum(readings) / self._area(filters)
        if target.metric == "carbon":
            readings = readings.filtered(lambda rec: rec.scope in ("1", "2", False))
        return self._sum(readings)

    def _target_row(self, target, filters, start, end):
        current = self._live_current(target, filters, start, end)
        achievement = self._achievement(target.direction, target.baseline, target.target_value, current)
        status = self._status_from_achievement(achievement, target.direction)
        return {
            "id": target.id,
            "name": target.name,
            "subtitle": target.subtitle or "",
            "category": target.category,
            "metric": target.metric,
            "measure": target.measure,
            "direction": target.direction,
            "baseline": target.baseline,
            "baseline_label": f"{self._fmt(target.baseline)} {target.unit}",
            "target": target.target_value,
            "target_label": f"{self._fmt(target.target_value)} {target.unit}",
            "current": round(current, 2),
            "current_label": f"{self._fmt(current)} {target.unit}",
            "unit": target.unit,
            "due": target.due_date.strftime("%b %Y") if target.due_date else "",
            "due_date": target.due_date.isoformat() if target.due_date else "",
            "achievement": achievement,
            "status": status,
        }

    def _property_rows(self, current_readings, previous_readings, unit, higher_better=False):
        current = {}
        previous = {}
        meta = {}
        for rec in current_readings:
            key = (rec.property_id.id, rec.building_id.id)
            current[key] = current.get(key, 0) + rec.value
            meta[key] = rec
        for rec in previous_readings:
            key = (rec.property_id.id, rec.building_id.id)
            previous[key] = previous.get(key, 0) + rec.value
            meta.setdefault(key, rec)
        rows = []
        for key, value in current.items():
            rec = meta[key]
            prev = previous.get(key, 0)
            variance = self._delta(value, prev)
            rows.append({
                "property": rec.property_id.name,
                "building": rec.building_id.name or "—",
                "property_id": rec.property_id.id,
                "building_id": rec.building_id.id or 0,
                "segment": rec.segment or "other",
                "current": round(value, 2),
                "current_label": self._fmt(value),
                "previous": round(prev, 2),
                "previous_label": self._fmt(prev),
                "variance": round(variance, 1),
                "variance_label": f"{variance:+.1f}%",
                "unit": unit,
                "status": self._status_from_variance(variance, higher_better),
            })
        rows.sort(key=lambda row: row["current"], reverse=True)
        return rows

    def _segment_share(self, readings):
        totals = {}
        for rec in readings:
            totals[rec.segment or "other"] = totals.get(rec.segment or "other", 0) + rec.value
        grand = sum(totals.values()) or 1
        order = ["manufacturing", "warehouse", "office", "logistics", "other"]
        return [
            {"key": key, "label": key.replace("_", " ").title(), "value": round(totals.get(key, 0), 1), "pct": round(totals.get(key, 0) / grand * 100)}
            for key in order if totals.get(key)
        ]

    @api.model
    def get_dashboard_data(self, filters=None):
        self._ensure_property_readings()
        filters = self._filters(filters)
        start, end = self._bounds(filters["period"])
        prev_start, prev_end = self._previous_bounds(start, end)
        energy = self._readings("energy", filters, start, end)
        energy_prev = self._readings("energy", filters, prev_start, prev_end)
        water = self._readings("water", filters, start, end)
        water_prev = self._readings("water", filters, prev_start, prev_end)
        carbon = self._readings("carbon", filters, start, end)
        carbon_prev = self._readings("carbon", filters, prev_start, prev_end)
        waste = self._readings("waste", filters, start, end)
        renewable = self._readings("renewable", filters, start, end)

        energy_total = self._sum(energy)
        water_total = self._sum(water)
        carbon_total = self._sum(carbon)
        energy_delta = self._delta(energy_total, self._sum(energy_prev))
        water_delta = self._delta(water_total, self._sum(water_prev))
        carbon_delta = self._delta(carbon_total, self._sum(carbon_prev))
        scope1 = self._sum(carbon.filtered(lambda rec: rec.scope == "1"))
        scope2 = self._sum(carbon.filtered(lambda rec: rec.scope == "2"))
        scope3 = self._sum(carbon.filtered(lambda rec: rec.scope == "3"))
        scope_total = scope1 + scope2 + scope3 or 1

        targets = [
            self._target_row(target, filters, start, end)
            for target in self.env["esg.target"].search([])
        ]
        score = round(sum(row["achievement"] for row in targets) / len(targets)) if targets else 0

        properties = self.env["property.property"].search([])
        buildings = self.env["property.building"].search([])
        kpis = []
        for kpi in self.env["esg.kpi"].search([]):
            actual = kpi.actual
            if kpi.metric:
                readings = self._readings(kpi.metric, filters, start, end)
                if kpi.metric == "carbon" and "Scope 1" in (kpi.name or ""):
                    readings = readings.filtered(lambda rec: rec.scope == "1")
                raw = self._avg(readings) if kpi.metric in ("waste", "renewable") else self._sum(readings)
                actual = raw / (kpi.scale or 1)
            gap = self._delta(actual, kpi.target) if kpi.direction == "higher" else self._delta(kpi.target, actual) * -1
            achievement = (actual / kpi.target * 100) if kpi.target and kpi.direction == "higher" else ((kpi.target / actual * 100) if actual else 0)
            achievement = max(0, min(150, round(achievement, 1)))
            kpis.append({
                "id": kpi.id,
                "name": kpi.name,
                "category": kpi.category,
                "target": kpi.target,
                "target_label": f"{kpi.target:g} {kpi.unit}",
                "actual": round(actual, 2),
                "actual_label": f"{actual:.1f} {kpi.unit}",
                "unit": kpi.unit,
                "direction": kpi.direction,
                "delta": round(self._delta(actual, kpi.target), 1),
                "achievement": achievement,
                "status": self._status_from_achievement(min(achievement, 100), kpi.direction),
                "card": self._fmt(actual),
            })

        energy_rows = self._property_rows(energy, energy_prev, "kWh")
        water_rows = self._property_rows(water, water_prev, "m3")
        carbon_rows = self._property_rows(carbon, carbon_prev, "tCO2e")
        peak = self._sum(energy.filtered("peak"))
        offpeak = energy_total - peak
        activities = [{
            "id": rec.id,
            "name": rec.name,
            "detail": rec.detail or "",
            "metric": rec.metric,
        } for rec in self.env["esg.activity"].search([], limit=6)]
        reports = [{
            "id": rec.id,
            "name": rec.name,
            "template": rec.template,
            "period": rec.period_label or "",
            "date": rec.report_date.strftime("%b %d") if rec.report_date else "",
            "status": rec.status,
            "property": rec.property_id.name or "All Properties",
        } for rec in self.env["esg.report"].search([], limit=12)]

        month_energy = self._by_month(energy)
        month_water = self._by_month(water)
        month_carbon = self._by_month(carbon)
        carbon_prev_pairs = self._by_month(carbon_prev)
        curr = month_carbon[-6:]
        prev_vals = [value for _label, value in carbon_prev_pairs][-len(curr):] if curr else []
        carbon_months = []
        month_peak = max([value for _label, value in curr] + prev_vals + [0]) or 1
        for index, (label, value) in enumerate(curr):
            previous = prev_vals[index] if index < len(prev_vals) else 0
            carbon_months.append({
                "label": label,
                "current": round(value, 1),
                "current_pct": round(value / month_peak * 100),
                "previous": round(previous, 1),
                "previous_pct": round(previous / month_peak * 100),
            })

        period_names = {"ytd": "YTD", "prev": "Previous Year", "30d": "Last 30 Days", "12m": "Last 12 Months"}
        property_name = "All Properties"
        building_name = "All Buildings"
        if filters["property_id"]:
            property_name = self.env["property.property"].browse(filters["property_id"]).name or property_name
        if filters["building_id"]:
            building_name = self.env["property.building"].browse(filters["building_id"]).name or building_name
        energy_scope = f"{property_name} · {building_name} · {period_names.get(filters['period'], 'YTD')}"

        return {
            "filters": filters,
            "period_label": f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}",
            "properties": [{"id": rec.id, "name": rec.name} for rec in properties],
            "buildings": [{"id": rec.id, "name": rec.name, "property_id": rec.property_id.id} for rec in buildings],
            "dashboard": {
                "energy": self._fmt(energy_total),
                "energy_delta": round(energy_delta, 1),
                "water": self._fmt(water_total),
                "water_delta": round(water_delta, 1),
                "footprint": self._fmt(carbon_total),
                "footprint_delta": round(carbon_delta, 1),
                "emissions": self._fmt(scope1 + scope2),
                "emissions_delta": round(carbon_delta, 1),
                "score": score,
                "target_ach": score,
                "energy_scope": energy_scope,
                "energy_trend": self._bars(month_energy[-12:]),
                "water_trend": self._bars(month_water[-12:]),
                "carbon_trend": self._bars(month_carbon[-12:]),
                "scopes": [
                    {"key": "2", "label": "Scope 2 (Indirect)", "pct": round(scope2 / scope_total * 100), "color": "#5b3fd6"},
                    {"key": "1", "label": "Scope 1 (Direct)", "pct": round(scope1 / scope_total * 100), "color": "#b9a7f5"},
                    {"key": "3", "label": "Scope 3 (Value Chain)", "pct": round(scope3 / scope_total * 100), "color": "#e7e2f8"},
                ],
            },
            "energy": {
                "total": self._fmt(energy_total),
                "current": self._fmt(month_energy[-1][1] if month_energy else 0),
                "previous": self._fmt(month_energy[-2][1] if len(month_energy) > 1 else 0),
                "variance": round(energy_delta, 1),
                "intensity": round(energy_total / self._area(filters), 2),
                "daily": self._bars(month_energy[-10:]),
                "monthly": self._bars(month_energy[-6:]),
                "rows": energy_rows,
            },
            "water": {
                "total": self._fmt(water_total),
                "daily": self._fmt(water_total / max((end - start).days, 1)),
                "saved": self._fmt(max(self._sum(water_prev) - water_total, 0)),
                "saved_delta": round(-water_delta, 1),
                "rate": round(max(-water_delta, 0), 1),
                "trend": self._bars(month_water[-12:]),
                "by_building": [
                    {"name": row["building"], "pct": row["current"] and round(row["current"] / (water_total or 1) * 100), "value": row["current_label"]}
                    for row in water_rows[:4]
                ],
                "goal": next((row["achievement"] for row in targets if row["metric"] == "water"), 0),
                "rows": water_rows,
            },
            "carbon": {
                "total": self._fmt(carbon_total),
                "per_property": round(carbon_total / max(len({row["property_id"] for row in carbon_rows}), 1), 1),
                "trend": round(carbon_delta, 1),
                "goal": next((row["achievement"] for row in targets if row["metric"] == "carbon"), 0),
                "goal_target": 25,
                "months": carbon_months,
                "scopes": [],
                "rows": carbon_rows,
            },
            "kpis": kpis,
            "analysis": {
                "total": self._fmt(energy_total),
                "vs_previous": round(energy_delta, 1),
                "vs_target": round(self._delta(energy_total, self._sum(energy_prev) * 0.97), 1) if energy_prev else 0,
                "trend": self._bars(month_energy[-12:]),
                "peak_pct": round(peak / (energy_total or 1) * 100),
                "peak": self._fmt(peak),
                "offpeak": self._fmt(offpeak),
                "rows": energy_rows[:6],
            },
            "water_analysis": {
                "trend": self._bars(month_water[-12:]),
                "reduction": self._conservation(water)[0],
                "goal_fill": self._conservation(water)[1],
                "goal_note": "Latest month versus the peak month in this filter. Target pace is 15%.",
                "current": self._fmt(water_total),
                "previous": self._fmt(self._sum(water_prev)),
                "variance": round(water_delta, 1),
                "segments": self._segment_share(water),
                "top": water_rows[:5],
                "rows": water_rows,
            },
            "emissions": {
                "total": self._fmt(carbon_total),
                "trend": round(carbon_delta, 1),
                "reduction_target": next((row["achievement"] for row in targets if row["metric"] == "carbon"), 0),
                "intensity": round(carbon_total / self._area(filters) * 1000, 2),
                "monthly": self._bars(month_carbon[-9:]),
                "scopes": [
                    {"key": "2", "label": "Scope 2", "pct": round(scope2 / scope_total * 100)},
                    {"key": "1", "label": "Scope 1", "pct": round(scope1 / scope_total * 100)},
                    {"key": "3", "label": "Scope 3", "pct": round(scope3 / scope_total * 100)},
                ],
                "yoy": self._bars(month_carbon[-6:]),
                "yoy_prev": self._bars(carbon_prev_pairs[-6:]),
                "rows": carbon_rows,
            },
            "targets": targets,
            "activities": activities,
            "reports": reports,
            "waste_rate": round(self._avg(waste), 1),
            "renewable_rate": round(self._avg(renewable), 1),
        }

    def _refresh(self, filters):
        return self.get_dashboard_data(filters)

    @api.model
    def add_reading(self, values):
        values = values or {}
        metric = values.get("metric") or "energy"
        if metric not in self.UNITS:
            raise UserError("Choose a metric.")
        if not values.get("property_id"):
            raise UserError("Choose a property.")
        if not values.get("date") or values.get("value") in (None, ""):
            raise UserError("Date and value are required.")
        reading = self.env["esg.reading"].create({
            "property_id": int(values["property_id"]),
            "building_id": int(values["building_id"]) if values.get("building_id") else False,
            "metric": metric,
            "date": values["date"],
            "value": float(values["value"]),
            "unit": self.UNITS[metric],
            "scope": values.get("scope") or False,
            "peak": bool(values.get("peak")),
            "segment": values.get("segment") or "office",
            "note": values.get("note") or "Manual entry",
        })
        self.env["esg.activity"].create({
            "name": f"{metric.title()} reading {reading.value:g} {reading.unit} saved.",
            "detail": reading.date.strftime("%b %d"),
            "metric": metric if metric in ("energy", "water", "carbon") else "report",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def add_kpi(self, values):
        values = values or {}
        if not values.get("name") or not values.get("target"):
            raise UserError("KPI name and target are required.")
        self.env["esg.kpi"].create({
            "name": values["name"],
            "category": values.get("category") or "energy",
            "target": float(values["target"]),
            "actual": float(values.get("actual") or 0),
            "unit": values.get("unit") or "kWh",
            "direction": values.get("direction") or "lower",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def add_target(self, values):
        values = values or {}
        if not values.get("name"):
            raise UserError("Target name is required.")
        metric = values.get("metric") or "energy"
        self.env["esg.target"].create({
            "name": values["name"],
            "subtitle": values.get("subtitle") or "",
            "category": values.get("category") or metric if metric in ("energy", "water", "carbon", "waste") else "energy",
            "metric": metric,
            "measure": values.get("measure") or "total",
            "direction": values.get("direction") or "lower",
            "baseline": float(values.get("baseline") or 0),
            "target_value": float(values.get("target_value") or 0),
            "unit": values.get("unit") or self.UNITS.get(metric, ""),
            "due_date": values.get("due_date") or False,
        })
        return self._refresh(values.get("filters"))

    @api.model
    def update_target(self, target_id, values):
        values = values or {}
        target = self.env["esg.target"].browse(int(target_id))
        if not target.exists():
            raise UserError("Target was not found.")
        write_vals = {}
        for key in ("name", "subtitle", "unit", "due_date", "category", "metric", "measure", "direction"):
            if values.get(key) not in (None, ""):
                write_vals[key] = values[key]
        for key in ("baseline", "target_value"):
            if values.get(key) not in (None, ""):
                write_vals[key] = float(values[key])
        if write_vals:
            target.write(write_vals)
        return self._refresh(values.get("filters"))

    @api.model
    def generate_report(self, values):
        values = values or {}
        template = values.get("template") or "energy"
        labels = dict(self.env["esg.report"]._fields["template"].selection)
        period = (values.get("filters") or {}).get("period") or "ytd"
        period_label = {"ytd": "YTD", "prev": "Previous Year", "30d": "Last 30 Days", "12m": "Last 12 Months"}.get(period, period)
        prop = self.env["property.property"].browse(int(values.get("property_id") or 0))
        self.env["esg.report"].create({
            "name": f"{labels.get(template, 'ESG')} Report",
            "template": template,
            "period_label": period_label,
            "property_id": prop.id if prop else False,
            "building_id": int(values.get("building_id") or 0) or False,
            "report_date": date.today(),
            "status": "done",
        })
        self.env["esg.activity"].create({
            "name": f"{labels.get(template, 'ESG')} report published.",
            "detail": date.today().strftime("%b %d"),
            "metric": "report",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def report_file(self, template, filters=None):
        data = self.get_dashboard_data(filters)
        template = template or "energy"
        if template == "water":
            rows = data["water"]["rows"]
            header = ["Property", "Building", "Usage", "Previous", "Variance"]
            body = [[r["property"], r["building"], r["current_label"], r["previous_label"], r["variance_label"]] for r in rows]
        elif template == "carbon":
            rows = data["carbon"]["rows"]
            header = ["Property", "Building", "Emissions", "Previous", "Variance", "Status"]
            body = [[r["property"], r["building"], r["current_label"], r["previous_label"], r["variance_label"], r["status"]] for r in rows]
        elif template == "kpis":
            header = ["KPI", "Category", "Target", "Actual", "Achievement", "Status"]
            body = [[r["name"], r["category"], r["target_label"], r["actual_label"], r["achievement"], r["status"]] for r in data["kpis"]]
        elif template == "targets":
            header = ["Target", "Current", "Target", "Achievement", "Status"]
            body = [[r["name"], r["current_label"], r["target_label"], r["achievement"], r["status"]] for r in data["targets"]]
        else:
            rows = data["energy"]["rows"]
            header = ["Property", "Building", "Consumption", "Previous", "Variance", "Status"]
            body = [[r["property"], r["building"], r["current_label"], r["previous_label"], r["variance_label"], r["status"]] for r in rows]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(body)
        return {"filename": f"esg-{template}.csv", "content": buffer.getvalue()}
