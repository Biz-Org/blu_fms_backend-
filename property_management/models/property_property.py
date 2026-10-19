from collections import defaultdict
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class PropertyProperty(models.Model):
    _name = "property.property"
    _description = "Property"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char()
    region = fields.Char()
    street = fields.Char()
    city = fields.Char()
    location = fields.Char()
    property_type = fields.Selection(
        [("residential", "Residential"), ("commercial", "Commercial")],
        default="residential",
        required=True,
    )
    operational_status = fields.Selection(
        [("active", "Active"), ("maintenance", "Maintenance")],
        default="active",
        required=True,
    )
    image_128 = fields.Image("Image", max_width=128, max_height=128)
    description = fields.Text()
    state_name = fields.Char(string="State / Province")
    zip = fields.Char(string="Postal Code")
    country = fields.Char(default="India")
    planned_buildings = fields.Integer(default=1)
    planned_floors = fields.Integer(default=0)
    planned_units = fields.Integer(default=0)
    category = fields.Selection(
        [("class_a", "Class A"), ("class_b", "Class B"), ("class_c", "Class C")],
        default="class_a",
        string="Category",
    )
    lifecycle_state = fields.Selection(
        [("draft", "Draft"), ("active", "Active")],
        default="active",
        required=True,
    )
    area_sqft = fields.Float(string="Area (sqft)")
    year_built = fields.Integer()
    acquisition_date = fields.Date()
    manager_id = fields.Many2one("res.partner", string="Property Manager")
    amenity_notes = fields.Text()
    active = fields.Boolean(default=True)
    building_ids = fields.One2many("property.building", "property_id")
    unit_ids = fields.One2many("property.unit", "property_id")
    owner_ids = fields.One2many("property.owner", "property_id")
    document_ids = fields.One2many("property.document", "property_id")
    activity_log_ids = fields.One2many("property.activity.log", "property_id")

    building_count = fields.Integer(compute="_compute_stats", store=True)
    unit_count = fields.Integer(compute="_compute_stats", store=True)
    occupied_count = fields.Integer(compute="_compute_stats", store=True)
    vacant_count = fields.Integer(compute="_compute_stats", store=True)
    occupancy_rate = fields.Float(compute="_compute_stats", store=True)
    health_status = fields.Selection(
        [("healthy", "Healthy"), ("review", "Review Needed")],
        compute="_compute_stats",
        store=True,
    )

    @api.depends("building_ids", "unit_ids", "unit_ids.status")
    def _compute_stats(self):
        for rec in self:
            units = rec.unit_ids
            rec.building_count = len(rec.building_ids)
            rec.unit_count = len(units)
            rec.occupied_count = len(units.filtered(lambda u: u.status == "occupied"))
            rec.vacant_count = len(units.filtered(lambda u: u.status == "vacant"))
            rec.occupancy_rate = (rec.occupied_count / rec.unit_count * 100) if rec.unit_count else 0.0
            vacant_rate = (rec.vacant_count / rec.unit_count * 100) if rec.unit_count else 0.0
            rec.health_status = "review" if vacant_rate >= 20 else "healthy"

    def _portfolio_manager(self):
        Partner = self.env["res.partner"]
        manager = Partner.search([("name", "=", "Jane Doe")], limit=1)
        return manager or Partner.create({
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
        })

    def _format_gla(self, sqft):
        value = float(sqft or 0)
        if value >= 1000000:
            return f"{value / 1000000:.1f}M sq ft"
        if value >= 1000:
            return f"{value / 1000:.1f}K sq ft"
        if value:
            return f"{int(value)} sq ft"
        return "—"

    def _format_activity_when(self, event_date):
        if not event_date:
            return ""
        now = fields.Datetime.now()
        local = fields.Datetime.context_timestamp(self, event_date)
        today = fields.Datetime.context_timestamp(self, now).date()
        stamp = local.strftime("%I:%M %p").lstrip("0")
        if local.date() == today:
            return f"Today, {stamp}"
        if local.date() == today - timedelta(days=1):
            return f"Yesterday, {stamp}"
        return local.strftime("%b %d, %I:%M %p").replace(" 0", " ")

    @api.model
    def _format_activity_ago(self, event_date):
        if not event_date:
            return ""
        now = fields.Datetime.now()
        seconds = max(0, (now - event_date).total_seconds())
        if seconds < 3600:
            return f"{int(seconds // 60) or 1}m ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        days = int(seconds // 86400)
        if days == 1:
            return "Yesterday"
        if days < 7:
            return f"{days}d ago"
        local = fields.Datetime.context_timestamp(self, event_date)
        return local.strftime("%b %d")

    def _ensure_screen_fields(self):
        city_locations = {
            "Mumbai": "Downtown Metro",
            "Delhi": "North Ridge",
            "Pune": "Central Quarter",
            "Bengaluru": "Tech Park",
            "Hyderabad": "Financial District",
            "Kolkata": "Riverside",
            "Chennai": "Marina Bay",
            "Jaipur": "Heritage District",
            "Ahmedabad": "Westside Arts",
            "Kochi": "Harbor Line",
            "Bhubaneswar": "East Campus",
        }
        manager = self._portfolio_manager()
        Activity = self.env["property.activity.log"]
        usage_cycle = ["commercial", "residential", "parking"]
        for index, prop in enumerate(self.search([]), start=1):
            values = {}
            if not prop.code:
                values["code"] = f"PRP-{1000 + index}"
            if not prop.location:
                values["location"] = city_locations.get(prop.city) or prop.city or prop.region or "Downtown Metro"
            if not prop.property_type:
                values["property_type"] = "commercial" if index % 3 == 0 else "residential"
            if not prop.operational_status:
                values["operational_status"] = "maintenance" if prop.health_status == "review" else "active"
            if not prop.year_built:
                values["year_built"] = 2012 + (index % 10)
            if not prop.acquisition_date:
                values["acquisition_date"] = date(2016, 3, 12) + timedelta(days=index * 37)
            if not prop.manager_id:
                values["manager_id"] = manager.id
            if not prop.area_sqft:
                values["area_sqft"] = max(prop.unit_count or 1, 1) * 1200
            if values:
                prop.write(values)
            for building_index, building in enumerate(prop.building_ids):
                expected = usage_cycle[building_index % len(usage_cycle)]
                if building.usage in (False, "mixed") or not building.usage:
                    building.usage = expected
            if not prop.activity_log_ids:
                Activity.create({
                    "name": "Rent roll updated",
                    "description": "System",
                    "activity_type": "document",
                    "property_id": prop.id,
                    "event_date": fields.Datetime.now() - timedelta(days=6),
                })
                Activity.create({
                    "name": "Fire safety inspection passed",
                    "description": "Entire Property",
                    "activity_type": "maintenance",
                    "property_id": prop.id,
                    "event_date": fields.Datetime.now() - timedelta(days=4),
                })
                if prop.unit_ids[:1]:
                    unit = prop.unit_ids[:1]
                    Activity.create({
                        "name": f"Unit {unit.name} lease signed",
                        "description": unit.building_id.name or "Tower",
                        "activity_type": "lease",
                        "property_id": prop.id,
                        "unit_id": unit.id,
                        "event_date": fields.Datetime.now() - timedelta(hours=3),
                    })

    @api.model
    def create_from_dashboard(self, vals):
        vals = dict(vals or {})
        documents = vals.pop("documents", []) or []
        is_draft = bool(vals.pop("is_draft", False))
        name = (vals.get("name") or "").strip()
        if not name:
            raise UserError("Property Name is required.")
        if not is_draft:
            missing = []
            for field, label in [
                ("code", "Property Code"),
                ("property_type", "Property Type"),
                ("street", "Address Line 1"),
                ("city", "City"),
                ("state_name", "State / Province"),
                ("zip", "Postal Code"),
                ("country", "Country"),
            ]:
                if not (vals.get(field) or "").strip():
                    missing.append(label)
            if missing:
                raise UserError("Please fill required fields: %s" % ", ".join(missing))

        planned_buildings = max(0, int(vals.get("planned_buildings") or 1))
        planned_floors = max(0, int(vals.get("planned_floors") or 0))
        planned_units = max(0, int(vals.get("planned_units") or 0))
        property_type = vals.get("property_type") or "residential"
        if property_type not in ("residential", "commercial"):
            property_type = "residential"
        operational_status = vals.get("operational_status") or "active"
        if operational_status not in ("active", "maintenance"):
            operational_status = "active"
        category = vals.get("category") or "class_a"
        if category not in ("class_a", "class_b", "class_c"):
            category = "class_a"

        city = (vals.get("city") or "").strip()
        prop = self.create({
            "name": name,
            "code": (vals.get("code") or "").strip() or False,
            "property_type": property_type,
            "operational_status": operational_status,
            "description": vals.get("description") or False,
            "street": (vals.get("street") or "").strip() or False,
            "city": city or False,
            "state_name": (vals.get("state_name") or "").strip() or False,
            "zip": (vals.get("zip") or "").strip() or False,
            "country": (vals.get("country") or "").strip() or "India",
            "location": city or (vals.get("location") or "").strip() or False,
            "region": (vals.get("state_name") or "").strip() or False,
            "planned_buildings": planned_buildings,
            "planned_floors": planned_floors,
            "planned_units": planned_units,
            "category": category,
            "lifecycle_state": "draft" if is_draft else "active",
            "amenity_notes": vals.get("description") or False,
        })

        Building = self.env["property.building"]
        Floor = self.env["property.floor"]
        Unit = self.env["property.unit"]
        for index in range(planned_buildings or 0):
            building = Building.create({
                "name": f"{name} — Tower {index + 1}",
                "property_id": prop.id,
                "region": prop.region,
                "tower_code": f"T{index + 1}",
            })
            for floor_no in range(1, (planned_floors or 0) + 1):
                Floor.create({
                    "name": f"Floor {floor_no}",
                    "building_id": building.id,
                    "floor_number": floor_no,
                    "wing": "A" if floor_no % 2 else "B",
                })

        buildings = Building.search([("property_id", "=", prop.id)])
        floors = Floor.search([("building_id", "in", buildings.ids)]) if buildings else Floor.browse()
        unit_type = "2 BHK" if property_type == "residential" else "Office"
        for seq in range(1, (planned_units or 0) + 1):
            floor = floors[(seq - 1) % len(floors)] if floors else False
            building = floor.building_id if floor else (buildings[(seq - 1) % len(buildings)] if buildings else False)
            Unit.create({
                "name": f"{seq:03d}",
                "property_id": prop.id,
                "building_id": building.id if building else False,
                "floor_id": floor.id if floor else False,
                "status": "available",
                "unit_type": unit_type,
            })

        Document = self.env["property.document"]
        type_names = {
            "property_reg": "Property Registration",
            "ownership": "Ownership",
            "building": "Building Docs",
            "other": "Other Docs",
        }
        for doc in documents:
            if not doc or not doc.get("data"):
                continue
            doc_type = doc.get("type") if doc.get("type") in type_names else "other"
            Document.create({
                "name": doc.get("name") or type_names[doc_type],
                "property_id": prop.id,
                "document_type": doc_type,
                "attachment": doc.get("data"),
                "filename": doc.get("name") or type_names[doc_type],
            })

        self.env["property.activity.log"].create({
            "name": "Draft saved" if is_draft else "Property created",
            "description": f"{name} was added from FMS Dashboard",
            "activity_type": "document",
            "property_id": prop.id,
        })
        return {"id": prop.id}

    @api.model
    def get_form_values(self, property_id):
        prop = self.browse(int(property_id or 0)).exists()
        if not prop:
            raise UserError("Property not found.")
        return {
            "id": prop.id,
            "name": prop.name or "",
            "code": prop.code or "",
            "property_type": prop.property_type or "residential",
            "operational_status": prop.operational_status or "active",
            "description": prop.description or "",
            "street": prop.street or "",
            "city": prop.city or "",
            "state_name": prop.state_name or "",
            "zip": prop.zip or "",
            "country": prop.country or "",
            "planned_buildings": prop.planned_buildings or 0,
            "planned_floors": prop.planned_floors or 0,
            "planned_units": prop.planned_units or 0,
            "category": prop.category or "class_a",
        }

    @api.model
    def update_from_dashboard(self, vals):
        vals = dict(vals or {})
        documents = vals.pop("documents", []) or []
        is_draft = bool(vals.pop("is_draft", False))
        prop = self.browse(int(vals.get("id") or 0)).exists()
        if not prop:
            raise UserError("Property not found.")
        name = (vals.get("name") or "").strip()
        if not name:
            raise UserError("Property Name is required.")
        if not is_draft:
            missing = []
            for field, label in [
                ("code", "Property Code"),
                ("property_type", "Property Type"),
                ("street", "Address Line 1"),
                ("city", "City"),
                ("state_name", "State / Province"),
                ("zip", "Postal Code"),
                ("country", "Country"),
            ]:
                if not (vals.get(field) or "").strip():
                    missing.append(label)
            if missing:
                raise UserError("Please fill required fields: %s" % ", ".join(missing))
        property_type = vals.get("property_type") or prop.property_type or "residential"
        if property_type not in ("residential", "commercial"):
            property_type = "residential"
        operational_status = vals.get("operational_status") or prop.operational_status or "active"
        if operational_status not in ("active", "maintenance"):
            operational_status = "active"
        category = vals.get("category") or prop.category or "class_a"
        if category not in ("class_a", "class_b", "class_c"):
            category = "class_a"
        city = (vals.get("city") or "").strip()
        prop.write({
            "name": name,
            "code": (vals.get("code") or "").strip() or False,
            "property_type": property_type,
            "operational_status": operational_status,
            "description": vals.get("description") or False,
            "street": (vals.get("street") or "").strip() or False,
            "city": city or False,
            "state_name": (vals.get("state_name") or "").strip() or False,
            "zip": (vals.get("zip") or "").strip() or False,
            "country": (vals.get("country") or "").strip() or prop.country or "India",
            "location": city or prop.location,
            "region": (vals.get("state_name") or "").strip() or prop.region,
            "planned_buildings": max(0, int(vals.get("planned_buildings") or 0)),
            "planned_floors": max(0, int(vals.get("planned_floors") or 0)),
            "planned_units": max(0, int(vals.get("planned_units") or 0)),
            "category": category,
            "lifecycle_state": "draft" if is_draft else "active",
        })
        type_names = {
            "property_reg": "Property Registration",
            "ownership": "Ownership",
            "building": "Building Docs",
            "other": "Other Docs",
        }
        Document = self.env["property.document"]
        for doc in documents:
            if not doc or not doc.get("data"):
                continue
            doc_type = doc.get("type") if doc.get("type") in type_names else "other"
            Document.create({
                "name": doc.get("name") or type_names[doc_type],
                "property_id": prop.id,
                "document_type": doc_type,
                "attachment": doc.get("data"),
                "filename": doc.get("name") or type_names[doc_type],
            })
        self.env["property.activity.log"].create({
            "name": "Property updated",
            "description": f"{prop.name} was saved from FMS Dashboard",
            "activity_type": "document",
            "property_id": prop.id,
        })
        return {"id": prop.id}

    def _property_row(self, prop):
        type_labels = dict(self._fields["property_type"].selection)
        status_labels = dict(self._fields["operational_status"].selection)
        return {
            "id": prop.id,
            "name": prop.name,
            "code": prop.code or f"PRP-{prop.id:04d}",
            "initials": "".join(part[0] for part in (prop.name or "P").split()[:2]).upper(),
            "type": prop.property_type or "residential",
            "type_label": type_labels.get(prop.property_type) or "Residential",
            "location": prop.location or prop.city or "",
            "building_count": prop.building_count,
            "unit_count": prop.unit_count,
            "occupancy": round(prop.occupancy_rate or 0),
            "status": "draft" if prop.lifecycle_state == "draft" else (prop.operational_status or "active"),
            "status_label": "Draft" if prop.lifecycle_state == "draft" else (status_labels.get(prop.operational_status) or "Active"),
        }

    @api.model
    def get_dashboard_data(self):
        self._ensure_screen_fields()
        properties = self.search([])
        units = self.env["property.unit"].search([])
        buildings = self.env["property.building"].search([])
        total_units = len(units)
        occupied = len(units.filtered(lambda u: u.status == "occupied"))
        vacant = len(units.filtered(lambda u: u.status == "vacant"))
        maintenance = len(units.filtered(lambda u: u.status == "maintenance"))
        reserved = len(units.filtered(lambda u: u.status == "reserved"))
        available = len(units.filtered(lambda u: u.status == "available"))
        occupancy = round(occupied / total_units * 100) if total_units else 0
        regions = len(set(filter(None, buildings.mapped("region") + properties.mapped("region"))))

        colors = ["#7c3aed", "#14b8a6", "#22c55e", "#f59e0b", "#f43f5e", "#6366f1"]
        today = fields.Date.context_today(self)
        tenancies = self.env["property.tenancy"].search([])
        trends = []
        for index, offset in enumerate(range(5, -1, -1)):
            month_index = today.month - offset
            year = today.year
            while month_index <= 0:
                month_index += 12
                year -= 1
            start = date(year, month_index, 1)
            end = date(year + (1 if month_index == 12 else 0), 1 if month_index == 12 else month_index + 1, 1) - timedelta(days=1)
            if offset == 0:
                occupied_month = occupied
            else:
                occupied_month = len({
                    tenancy.unit_id.id
                    for tenancy in tenancies
                    if tenancy.unit_id and tenancy.date_start and tenancy.date_start <= end and (tenancy.date_end or date(9999, 12, 31)) >= start
                })
            value = round(occupied_month / total_units * 100) if total_units else 0
            trends.append({
                "month": start.strftime("%b"),
                "value": value,
                "color": colors[index % len(colors)],
            })
        max_trend = max((row["value"] for row in trends), default=1) or 1
        for row in trends:
            row["height"] = round(row["value"] / max_trend * 100)
        prior = trends[-2]["value"] if len(trends) > 1 else occupancy
        occupancy_delta = occupancy - prior

        featured_names = ["The Azure Tower", "Oakwood Estates", "Meridian Lofts"]
        ordered = sorted(
            properties,
            key=lambda p: (
                featured_names.index(p.name) if p.name in featured_names else 99,
                -p.unit_count,
            ),
        )
        summary = []
        for prop in ordered[:8]:
            summary.append({
                "id": prop.id,
                "name": prop.name,
                "unit_count": prop.unit_count,
                "occupied_count": prop.occupied_count,
                "vacant_count": prop.vacant_count,
                "health_status": prop.health_status,
                "health_label": "Healthy" if prop.health_status == "healthy" else "Review Needed",
            })

        activities = []
        now = fields.Datetime.now()
        for activity in self.env["property.activity.log"].search([], limit=8):
            when = ""
            if activity.event_date:
                seconds = max(0, (now - activity.event_date).total_seconds())
                if seconds < 3600:
                    when = f"{int(seconds // 60) or 1} minutes ago"
                elif seconds < 86400:
                    when = f"{int(seconds // 3600)} hours ago"
                else:
                    when = f"{int(seconds // 86400)} days ago"
            activities.append({
                "id": activity.id,
                "title": activity.name,
                "description": activity.description or "",
                "type": activity.activity_type,
                "when": when,
            })

        return {
            "kpis": {
                "properties": len(properties),
                "properties_delta": f"{len(properties)} on record",
                "buildings": len(buildings),
                "buildings_hint": f"Across {regions or 1} region{'s' if (regions or 1) != 1 else ''}",
                "units": total_units,
                "units_delta": f"{occupied} occupied",
                "occupancy": occupancy,
                "occupancy_delta": f"{occupancy_delta:+.0f}% vs prior month",
                "occupancy_down": occupancy_delta < 0,
            },
            "status": {
                "occupied": occupied,
                "vacant": vacant,
                "maintenance": maintenance,
                "reserved": reserved,
                "available": available,
            },
            "trends": trends,
            "summary": summary,
            "activities": activities,
            "properties": [self._property_row(prop) for prop in properties],
        }

    def _hierarchy_group_status(self, units, kind, rec=None):
        occupied = sum(1 for unit in units if unit.status == "occupied")
        maintenance = sum(1 for unit in units if unit.status == "maintenance")
        count = len(units)
        if kind == "floor":
            if count and occupied == count:
                return "full", "Full"
            if maintenance:
                return "maintenance", "Maintenance"
            return "active", "Active"
        if kind == "property" and rec is not None:
            if rec.lifecycle_state == "draft":
                return "draft", "Draft"
            if rec.operational_status == "maintenance":
                return "maintenance", "Maintenance"
        if count and maintenance == count:
            return "maintenance", "Maintenance"
        return "active", "Active"

    def _hierarchy_node(self, rec, kind, units, children, parent_id=False):
        unit_labels = dict(self.env["property.unit"]._fields["status"].selection)
        if kind == "unit":
            occupied = 1 if rec.status == "occupied" else 0
            status, status_label = rec.status, unit_labels.get(rec.status) or (rec.status or "").title()
            unit_count = "-"
            code = rec.name if str(rec.name).upper().startswith("U-") else f"U-{rec.name}"
            name = rec.name if str(rec.name).lower().startswith("unit") else f"Unit {rec.name}"
        else:
            occupied = sum(1 for unit in units if unit.status == "occupied")
            status, status_label = self._hierarchy_group_status(units, kind, rec)
            unit_count = len(units)
            if kind == "property":
                code = rec.code or f"PRP-{rec.id:04d}"
                name = rec.name
            elif kind == "building":
                code = rec.tower_code or f"B-{rec.id:02d}"
                name = rec.name
            else:
                code = f"FL-{rec.floor_number:02d}" if rec.floor_number else f"FL-{rec.id:02d}"
                name = rec.name
                if rec.wing and rec.wing not in (rec.name or ""):
                    name = f"{rec.name} - {rec.wing}"
        return {
            "id": f"{kind}-{rec.id}",
            "resId": rec.id,
            "type": kind,
            "name": name,
            "code": code,
            "units": unit_count,
            "occupancy": occupied,
            "status": status,
            "status_label": status_label,
            "parentId": parent_id or False,
            "children": children,
        }

    @api.model
    def get_hierarchy_data(self):
        self._ensure_screen_fields()
        properties = self.search([]).sorted(lambda prop: (-prop.unit_count, prop.name or ""))
        buildings = self.env["property.building"].search([])
        floors = self.env["property.floor"].search([])
        units = self.env["property.unit"].search([])

        buildings_by_property = defaultdict(list)
        floors_by_building = defaultdict(list)
        units_by_property = defaultdict(list)
        units_by_building = defaultdict(list)
        units_by_floor = defaultdict(list)

        for building in buildings:
            buildings_by_property[building.property_id.id].append(building)
        for floor in floors:
            floors_by_building[floor.building_id.id].append(floor)
        for unit in units:
            units_by_property[unit.property_id.id].append(unit)
            if unit.building_id:
                units_by_building[unit.building_id.id].append(unit)
            if unit.floor_id:
                units_by_floor[unit.floor_id.id].append(unit)

        tree = []
        for prop in properties:
            building_nodes = []
            for building in sorted(buildings_by_property.get(prop.id, []), key=lambda rec: rec.tower_code or rec.name or ""):
                floor_nodes = []
                for floor in floors_by_building.get(building.id, []):
                    unit_nodes = [
                        self._hierarchy_node(unit, "unit", [unit], [])
                        for unit in units_by_floor.get(floor.id, [])
                    ]
                    floor_nodes.append(self._hierarchy_node(floor, "floor", units_by_floor.get(floor.id, []), unit_nodes, parent_id=building.id))
                loose_units = [
                    self._hierarchy_node(unit, "unit", [unit], [])
                    for unit in units_by_building.get(building.id, [])
                    if not unit.floor_id
                ]
                building_nodes.append(
                    self._hierarchy_node(building, "building", units_by_building.get(building.id, []), floor_nodes + loose_units)
                )
            tree.append(self._hierarchy_node(prop, "property", units_by_property.get(prop.id, []), building_nodes))
        return {"hierarchy": tree}

    def _building_short_name(self, building, index):
        letters = "ABCDEFGHIJK"
        code = (building.tower_code or "").strip().upper()
        if code.startswith("T") and code[1:].isdigit():
            pos = max(0, int(code[1:]) - 1)
            return f"Tower {letters[pos % len(letters)]}"
        if "—" in (building.name or ""):
            return building.name.split("—")[-1].strip()
        return building.name or f"Tower {letters[index % len(letters)]}"

    def _floor_bands(self, floors, units_by_floor):
        floors = sorted(floors, key=lambda rec: (rec.floor_number or 0, rec.name or ""))
        if not floors:
            return []
        size = max(1, (len(floors) + 2) // 3)
        uses = ["Retail", "Office", "Residential"]
        bands = []
        for index in range(0, len(floors), size):
            chunk = floors[index:index + size]
            start = chunk[0].floor_number or (index + 1)
            end = chunk[-1].floor_number or (index + len(chunk))
            label = f"Floors {start}-{end}" if start != end else f"Floor {start}"
            use = uses[(index // size) % len(uses)]
            mid = chunk[len(chunk) // 2]
            mid_units = units_by_floor.get(mid.id, [])
            occupied = sum(1 for unit in mid_units if unit.status == "occupied")
            bands.append({
                "id": f"band-{chunk[0].id}",
                "label": f"{label} ({use})",
                "title": f"{mid.name} Details",
                "floor_id": mid.id,
                "units_total": len(mid_units),
                "units_occupied": occupied,
                "occupancy": round(occupied / len(mid_units) * 100) if mid_units else 0,
            })
        return bands

    @api.model
    def get_property_detail(self, property_id):
        self._ensure_screen_fields()
        prop = self.browse(int(property_id or 0)).exists()
        if not prop:
            raise UserError("Property not found.")
        floors = self.env["property.floor"].search([("property_id", "=", prop.id)])
        units = prop.unit_ids
        occupied = len(units.filtered(lambda unit: unit.status == "occupied"))
        vacant = len(units.filtered(lambda unit: unit.status == "vacant"))
        usage_labels = dict(self.env["property.building"]._fields["usage"].selection)
        unit_labels = dict(self.env["property.unit"]._fields["status"].selection)
        type_label = "Commercial / Mixed-Use" if prop.property_type == "commercial" else (dict(self._fields["property_type"].selection).get(prop.property_type) or "Residential")
        status = "draft" if prop.lifecycle_state == "draft" else (prop.operational_status or "active")
        status_label = "Draft" if status == "draft" else (dict(self._fields["operational_status"].selection).get(prop.operational_status) or "Active")
        manager = prop.manager_id
        manager_name = manager.name if manager else "—"
        manager_initials = "".join(part[0] for part in (manager_name or "PM").split()[:2]).upper()
        location = ", ".join(part for part in [prop.location or prop.city, prop.state_name, prop.country] if part)

        units_by_floor = defaultdict(list)
        units_by_building = defaultdict(list)
        for unit in units:
            if unit.floor_id:
                units_by_floor[unit.floor_id.id].append(unit)
            if unit.building_id:
                units_by_building[unit.building_id.id].append(unit)

        hierarchy_buildings = []
        building_rows = []
        for index, building in enumerate(sorted(prop.building_ids, key=lambda rec: rec.tower_code or rec.name or "")):
            b_units = units_by_building.get(building.id, [])
            b_occupied = sum(1 for unit in b_units if unit.status == "occupied")
            short = self._building_short_name(building, index)
            usage = building.usage or ("commercial" if index == 0 else "residential" if index == 1 else "parking")
            hierarchy_buildings.append({
                "id": building.id,
                "name": short,
                "subtitle": (usage_labels.get(usage) or usage).upper(),
                "bands": self._floor_bands(building.floor_ids, units_by_floor),
            })
            building_rows.append({
                "id": building.id,
                "name": building.name,
                "code": building.tower_code or short,
                "usage": usage_labels.get(usage) or usage,
                "floors": building.floor_count,
                "units": len(b_units),
                "occupied": b_occupied,
                "occupancy": round(b_occupied / len(b_units) * 100) if b_units else 0,
            })

        activities = []
        for activity in prop.activity_log_ids[:8]:
            place = activity.description or "Entire Property"
            if activity.unit_id:
                place = f"Unit {activity.unit_id.name}"
                if activity.unit_id.building_id:
                    place = f"{place} • {self._building_short_name(activity.unit_id.building_id, 0)}"
            activities.append({
                "id": activity.id,
                "title": activity.name,
                "when": self._format_activity_when(activity.event_date),
                "place": place,
                "type": activity.activity_type or "document",
            })

        unit_rows = []
        for unit in units[:40]:
            unit_rows.append({
                "id": unit.id,
                "name": unit.name,
                "building": unit.building_id.name or "—",
                "floor": unit.floor_id.name or "—",
                "type": unit.unit_type or "—",
                "status": unit.status,
                "status_label": unit_labels.get(unit.status) or unit.status,
            })

        owners = [{
            "id": owner.id,
            "name": owner.partner_id.name,
            "share": owner.share_percent,
        } for owner in prop.owner_ids]
        documents = [{
            "id": doc.id,
            "name": doc.name,
            "type": dict(doc._fields["document_type"].selection).get(doc.document_type) or doc.document_type,
        } for doc in prop.document_ids]

        return {
            "property": {
                "id": prop.id,
                "name": prop.name,
                "code": prop.code or f"PRP-{prop.id:04d}",
                "location": location or prop.city or "—",
                "status": status,
                "status_label": status_label,
                "type_label": type_label,
                "year_built": prop.year_built or "—",
                "gla": self._format_gla(prop.area_sqft),
                "manager_name": manager_name,
                "manager_initials": manager_initials,
                "acquisition": prop.acquisition_date.strftime("%b %d, %Y") if prop.acquisition_date else "—",
            },
            "kpis": {
                "buildings": len(prop.building_ids),
                "floors": len(floors),
                "units": len(units),
                "occupied": occupied,
                "vacant": vacant,
                "occupancy_pct": round(occupied / len(units) * 100) if units else 0,
                "vacant_pct": round(vacant / len(units) * 100) if units else 0,
            },
            "activities": activities,
            "hierarchy": {
                "root": f"{prop.name} - PROPERTY ROOT",
                "buildings": hierarchy_buildings,
            },
            "buildings": building_rows,
            "units": unit_rows,
            "unit_total": len(units),
            "owners": owners,
            "documents": documents,
        }

    @api.model
    def _seed_demo_portfolio(self):
        if self.search_count([]):
            return True

        Partner = self.env["res.partner"]
        Building = self.env["property.building"]
        Floor = self.env["property.floor"]
        Unit = self.env["property.unit"]
        Owner = self.env["property.owner"]
        Tenancy = self.env["property.tenancy"]
        Activity = self.env["property.activity.log"]
        Document = self.env["property.document"]

        featured = [
            {
                "name": "The Azure Tower",
                "region": "West",
                "city": "Mumbai",
                "buildings": 4,
                "counts": {"occupied": 295, "vacant": 25, "maintenance": 0, "reserved": 0, "available": 0},
            },
            {
                "name": "Oakwood Estates",
                "region": "North",
                "city": "Delhi",
                "buildings": 3,
                "counts": {"occupied": 110, "vacant": 40, "maintenance": 0, "reserved": 0, "available": 0},
            },
            {
                "name": "Meridian Lofts",
                "region": "Central",
                "city": "Pune",
                "buildings": 2,
                "counts": {"occupied": 82, "vacant": 3, "maintenance": 0, "reserved": 0, "available": 0},
            },
        ]
        rest = [
            ("Harbor Point", "West", "Mumbai", 3, 90, 12, 4, 2, 4),
            ("Cedar Park Residences", "South", "Bengaluru", 4, 70, 8, 5, 2, 3),
            ("Riviera Heights", "East", "Hyderabad", 3, 64, 7, 3, 2, 2),
            ("Summit Place", "North", "Delhi", 3, 58, 6, 4, 2, 3),
            ("Lakeside Court", "East", "Kolkata", 3, 55, 5, 3, 1, 2),
            ("Pinecrest Villas", "South", "Chennai", 3, 52, 6, 3, 2, 2),
            ("The Grand Arcade", "Central", "Pune", 4, 48, 8, 3, 2, 3),
            ("Willow Creek", "North", "Jaipur", 3, 40, 7, 2, 1, 2),
            ("Sunset Ridge", "West", "Ahmedabad", 3, 28, 6, 2, 1, 2),
            ("Maple Grove", "South", "Kochi", 2, 20, 6, 2, 1, 1),
            ("Greenfield Commons", "East", "Bhubaneswar", 2, 13, 6, 1, 2, 6),
        ]

        specs = featured + [
            {
                "name": name,
                "region": region,
                "city": city,
                "buildings": n_buildings,
                "counts": {
                    "occupied": occ,
                    "vacant": vac,
                    "maintenance": maint,
                    "reserved": reserved,
                    "available": avail,
                },
            }
            for name, region, city, n_buildings, occ, vac, maint, reserved, avail in rest
        ]

        john = Partner.search([("name", "=", "John Doe")], limit=1) or Partner.create({
            "name": "John Doe",
            "email": "john.doe@example.com",
        })
        landlord = Partner.search([("name", "=", "Apex Holdings")], limit=1) or Partner.create({
            "name": "Apex Holdings",
            "is_company": True,
        })

        unit_vals = []
        azure = oakwood = meridian = None
        azure_unit = meridian_unit = None

        for spec in specs:
            prop = self.create({
                "name": spec["name"],
                "region": spec["region"],
                "city": spec["city"],
                "location": spec["city"],
                "amenity_notes": "Clubhouse, parking, 24x7 security",
            })
            if spec["name"] == "The Azure Tower":
                azure = prop
            elif spec["name"] == "Oakwood Estates":
                oakwood = prop
            elif spec["name"] == "Meridian Lofts":
                meridian = prop

            Owner.create({
                "property_id": prop.id,
                "partner_id": landlord.id,
                "share_percent": 100,
            })
            Document.create({
                "name": f"{spec['name']} title deed",
                "property_id": prop.id,
                "document_type": "title",
            })

            building_records = []
            for index in range(spec["buildings"]):
                building = Building.create({
                    "name": f"{spec['name']} — Tower {index + 1}",
                    "property_id": prop.id,
                    "region": spec["region"],
                    "tower_code": f"T{index + 1}",
                })
                building_records.append(building)
                for floor_no in range(1, 5):
                    Floor.create({
                        "name": f"Floor {floor_no}",
                        "building_id": building.id,
                        "floor_number": floor_no,
                        "wing": "A" if floor_no % 2 else "B",
                    })

            status_queue = []
            for status, count in spec["counts"].items():
                status_queue.extend([status] * count)

            floors = Floor.search([("building_id", "in", [b.id for b in building_records])])
            floor_list = floors or Floor.browse()
            for seq, status in enumerate(status_queue, start=1):
                building = building_records[seq % len(building_records)]
                floor = floor_list[seq % len(floor_list)] if floor_list else False
                wing = "ABCD"[seq % 4]
                vals = {
                    "name": f"{seq}{wing}",
                    "property_id": prop.id,
                    "building_id": building.id,
                    "floor_id": floor.id if floor else False,
                    "status": status,
                    "unit_type": "2 BHK" if seq % 3 else "3 BHK",
                    "area_sqft": 980 + (seq % 8) * 40,
                }
                if spec["name"] == "The Azure Tower" and status == "occupied" and azure_unit is None:
                    vals["tenant_id"] = john.id
                    vals["name"] = "4B"
                    azure_unit = True
                    unit_vals.append(vals)
                elif spec["name"] == "Meridian Lofts" and status == "occupied" and meridian_unit is None:
                    vals["name"] = "12C"
                    meridian_unit = True
                    unit_vals.append(vals)
                else:
                    unit_vals.append(vals)

        created_units = Unit.create(unit_vals)
        self.search([])._compute_stats()
        azure_4b = created_units.filtered(lambda u: u.name == "4B" and u.property_id == azure)[:1]
        meridian_12c = created_units.filtered(lambda u: u.name == "12C" and u.property_id == meridian)[:1]

        if azure_4b:
            Tenancy.create({
                "unit_id": azure_4b.id,
                "tenant_id": john.id,
                "date_start": fields.Date.today(),
                "state": "active",
            })
            Activity.create({
                "name": "New Lease Signed",
                "description": "Unit 4B at The Azure Tower leased to John Doe",
                "activity_type": "lease",
                "property_id": azure.id,
                "unit_id": azure_4b.id,
                "event_date": fields.Datetime.now() - timedelta(hours=2),
            })
        if meridian_12c:
            Activity.create({
                "name": "Maintenance Request Completed",
                "description": "HVAC repair finished in Unit 12C, Meridian Lofts",
                "activity_type": "maintenance",
                "property_id": meridian.id,
                "unit_id": meridian_12c.id,
                "event_date": fields.Datetime.now() - timedelta(hours=3),
            })
        if oakwood:
            Activity.create({
                "name": "Vacancy Alert",
                "description": "Oakwood Estates vacancy crossed 20%. Review Needed.",
                "activity_type": "alert",
                "property_id": oakwood.id,
                "event_date": fields.Datetime.now(),
            })
        return True
