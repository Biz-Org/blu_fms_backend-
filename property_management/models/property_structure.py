import calendar
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError


class PropertyBuilding(models.Model):
    _name = "property.building"
    _description = "Building / Tower"
    _order = "name"

    name = fields.Char(required=True)
    tower_code = fields.Char()
    region = fields.Char()
    usage = fields.Selection(
        [
            ("commercial", "Commercial"),
            ("residential", "Residential"),
            ("parking", "Parking/Retail"),
            ("mixed", "Mixed-Use"),
        ],
        default=False,
    )
    operational_status = fields.Selection(
        [
            ("active", "Active"),
            ("maintenance", "Maintenance"),
            ("construction", "Under Construction"),
        ],
        compute="_compute_counts",
        store=True,
    )
    property_id = fields.Many2one("property.property", required=True, ondelete="cascade")
    floor_ids = fields.One2many("property.floor", "building_id")
    unit_ids = fields.One2many("property.unit", "building_id")
    floor_count = fields.Integer(compute="_compute_counts", store=True)
    unit_count = fields.Integer(compute="_compute_counts", store=True)
    occupied_count = fields.Integer(compute="_compute_counts", store=True)
    occupancy_rate = fields.Float(compute="_compute_counts", store=True)

    @api.depends("floor_ids", "unit_ids", "unit_ids.status", "property_id.operational_status")
    def _compute_counts(self):
        for rec in self:
            units = rec.unit_ids
            rec.floor_count = len(rec.floor_ids)
            rec.unit_count = len(units)
            rec.occupied_count = len(units.filtered(lambda unit: unit.status == "occupied"))
            rec.occupancy_rate = (rec.occupied_count / rec.unit_count * 100) if rec.unit_count else 0.0
            if not rec.unit_count:
                rec.operational_status = "construction"
            elif rec.property_id.operational_status == "maintenance" or rec.occupancy_rate < 50:
                rec.operational_status = "maintenance"
            else:
                rec.operational_status = "active"

    def _display_code(self, index=0):
        self.ensure_one()
        code = (self.tower_code or "").strip()
        if code and not (code.startswith("T") and code[1:].isdigit()):
            return code
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        initials = "".join(part[0] for part in (self.property_id.name or "BL").split()[:2]).upper()
        return f"{initials}-{letters[index % 26]}-{index + 1:02d}"

    def _ensure_building_codes(self):
        for prop in self.env["property.property"].search([]):
            buildings = prop.building_ids.sorted(lambda rec: rec.tower_code or rec.name or "")
            for index, building in enumerate(buildings):
                code = building._display_code(index)
                if building.tower_code != code:
                    building.tower_code = code

    def _building_row(self, building, index=0):
        status_labels = dict(self._fields["operational_status"].selection)
        occupancy = round(building.occupancy_rate or 0)
        return {
            "id": building.id,
            "name": building.name,
            "code": building.tower_code or building._display_code(index),
            "property_id": building.property_id.id,
            "property_name": building.property_id.name,
            "floors": building.floor_count,
            "units": building.unit_count,
            "occupancy": occupancy,
            "status": building.operational_status or "active",
            "status_label": status_labels.get(building.operational_status) or "Active",
            "icon": "wrench" if building.operational_status == "construction" else "building",
        }

    @api.model
    def get_buildings_data(self):
        self._ensure_building_codes()
        buildings = self.search([])
        rows = []
        grouped = {}
        for building in buildings:
            grouped.setdefault(building.property_id.id, []).append(building)
        for prop_buildings in grouped.values():
            for index, building in enumerate(prop_buildings):
                rows.append(self._building_row(building, index))
        rows.sort(key=lambda row: (row["property_name"] or "", row["name"] or ""))
        properties = [
            {"id": prop.id, "name": prop.name}
            for prop in self.env["property.property"].search([])
        ]
        return {"buildings": rows, "properties": properties}

    @api.model
    def create_from_dashboard(self, vals):
        vals = dict(vals or {})
        name = (vals.get("name") or "").strip()
        property_id = int(vals.get("property_id") or 0)
        if not name:
            raise UserError("Building name is required.")
        prop = self.env["property.property"].browse(property_id).exists()
        if not prop:
            raise UserError("Please select a property.")
        usage = vals.get("usage") or False
        if usage not in ("commercial", "residential", "parking", "mixed"):
            usage = False
        building = self.create({
            "name": name,
            "property_id": prop.id,
            "tower_code": (vals.get("code") or "").strip() or False,
            "usage": usage,
            "region": prop.region,
        })
        floors = max(0, int(vals.get("floors") or 0))
        Floor = self.env["property.floor"]
        for floor_no in range(1, floors + 1):
            Floor.create({
                "name": f"Floor {floor_no}",
                "building_id": building.id,
                "floor_number": floor_no,
                "wing": "A" if floor_no % 2 else "B",
            })
        if not building.tower_code:
            siblings = prop.building_ids.sorted(lambda rec: rec.id)
            index = list(siblings.ids).index(building.id)
            building.tower_code = building._display_code(index)
        return {"id": building.id}

    @api.model
    def get_form_values(self, building_id):
        building = self.browse(int(building_id or 0)).exists()
        if not building:
            raise UserError("Building not found.")
        return {
            "id": building.id,
            "name": building.name or "",
            "code": building.tower_code or "",
            "property_id": building.property_id.id,
            "usage": building.usage or "commercial",
            "floors": len(building.floor_ids),
        }

    @api.model
    def update_from_dashboard(self, vals):
        vals = dict(vals or {})
        building = self.browse(int(vals.get("id") or 0)).exists()
        if not building:
            raise UserError("Building not found.")
        name = (vals.get("name") or "").strip()
        if not name:
            raise UserError("Building name is required.")
        prop = self.env["property.property"].browse(int(vals.get("property_id") or 0)).exists()
        if not prop:
            raise UserError("Please select a property.")
        usage = vals.get("usage") or False
        if usage not in ("commercial", "residential", "parking", "mixed"):
            usage = building.usage
        building.write({
            "name": name,
            "property_id": prop.id,
            "tower_code": (vals.get("code") or "").strip() or building.tower_code,
            "usage": usage,
            "region": prop.region,
        })
        target = max(0, int(vals.get("floors") or 0))
        existing = len(building.floor_ids)
        Floor = self.env["property.floor"]
        for floor_no in range(existing + 1, target + 1):
            Floor.create({
                "name": f"Floor {floor_no}",
                "building_id": building.id,
                "floor_number": floor_no,
                "wing": "A" if floor_no % 2 else "B",
            })
        self.env["property.activity.log"].create({
            "name": f"Building updated: {building.name}",
            "description": f"{building.name} was saved from FMS Dashboard",
            "activity_type": "document",
            "property_id": prop.id,
        })
        return {"id": building.id}

    def _short_name(self):
        self.ensure_one()
        if "—" in (self.name or ""):
            return self.name.split("—")[-1].strip()
        return self.name

    def _hierarchy_bands(self, building):
        floors = building.floor_ids.sorted(lambda rec: (rec.floor_number or 0, rec.name or ""))
        if not floors:
            return []
        count = len(floors)
        size = max(1, (count + 1) // 2) if count <= 4 else max(1, (count + 2) // 3)
        chunks = [floors[index:index + size] for index in range(0, count, size)]
        if len(chunks) == 1:
            labels = ["Main Level"]
        elif len(chunks) == 2:
            labels = ["Lower Level", "Penthouse Level"]
        else:
            labels = ["Lower Level", "Upper Res", "Penthouse Level"]
        bands = []
        for index, chunk in enumerate(chunks):
            start = chunk[0].floor_number or (index * size + 1)
            end = chunk[-1].floor_number or start
            title = f"Floors {start}-{end}" if start != end else f"Floor {start}"
            units = self.env["property.unit"]
            wings = defaultdict(lambda: self.env["property.unit"])
            for floor in chunk:
                floor_units = floor.unit_ids
                units |= floor_units
                wing_name = (floor.wing or "A").strip().upper()[:1] or "A"
                wings[wing_name] = wings[wing_name] | floor_units
            occupied = len(units.filtered(lambda unit: unit.status == "occupied"))
            wing_cards = []
            for wing_name in sorted(wings):
                wing_units = wings[wing_name]
                wing_occupied = len(wing_units.filtered(lambda unit: unit.status == "occupied"))
                total = len(wing_units)
                occupancy = round(wing_occupied / total * 100) if total else 0
                wing_cards.append({
                    "id": f"{chunk[0].id}-{wing_name}",
                    "name": f"Wing {wing_name}",
                    "units": total,
                    "occupied": wing_occupied,
                    "occupancy": occupancy,
                    "full": bool(total) and wing_occupied == total,
                })
            bands.append({
                "id": f"band-{chunk[0].id}",
                "title": title,
                "label": labels[min(index, len(labels) - 1)],
                "units": len(units),
                "occupancy": round(occupied / len(units) * 100) if units else 0,
                "wings": wing_cards,
            })
        return bands

    @api.model
    def get_building_detail(self, building_id):
        building = self.browse(int(building_id or 0)).exists()
        if not building:
            raise UserError("Building not found.")
        self._ensure_building_codes()
        prop = building.property_id
        units = building.unit_ids
        occupied = len(units.filtered(lambda unit: unit.status == "occupied"))
        vacant = max(0, len(units) - occupied)
        wings = {floor.wing or "A" for floor in building.floor_ids}
        status_labels = dict(self._fields["operational_status"].selection)
        status = building.operational_status or "active"
        siblings = prop.building_ids.sorted(lambda rec: rec.tower_code or rec.name or "")
        index = list(siblings.ids).index(building.id) if building.id in siblings.ids else 0
        location = " | ".join(part for part in [prop.name, prop.location or prop.city] if part)
        Property = self.env["property.property"]
        unit_labels = dict(self.env["property.unit"]._fields["status"].selection)

        activities = []
        logs = self.env["property.activity.log"].search(
            ["|", ("unit_id.building_id", "=", building.id), "&", ("property_id", "=", prop.id), ("unit_id", "=", False)],
            limit=8,
        )
        for activity in logs:
            activities.append({
                "id": activity.id,
                "title": activity.name,
                "description": activity.description or "",
                "when": Property._format_activity_ago(activity.event_date),
                "type": activity.activity_type or "document",
            })

        floors = []
        floor_name_by_number = {floor.floor_number: floor.name for floor in building.floor_ids}
        for floor in building.floor_ids.sorted(lambda rec: (rec.floor_number or 0, rec.wing or "", rec.name or "")):
            floor_units = floor.unit_ids
            floor_occupied = len(floor_units.filtered(lambda unit: unit.status == "occupied"))
            floors.append({
                "id": floor.id,
                "name": floor.name,
                "number": floor.floor_number,
                "wing": floor.wing or "—",
                "units": len(floor_units),
                "occupied": floor_occupied,
                "occupancy": round(floor_occupied / len(floor_units) * 100) if floor_units else 0,
            })

        unit_rows = []
        for unit in units[:40]:
            number = unit.floor_id.floor_number if unit.floor_id else None
            unit_rows.append({
                "id": unit.id,
                "name": unit.name,
                "floor": floor_name_by_number.get(number) or (unit.floor_id.name if unit.floor_id else "—"),
                "type": unit.unit_type or "—",
                "status": unit.status,
                "status_label": unit_labels.get(unit.status) or unit.status,
            })

        documents = [{
            "id": doc.id,
            "name": doc.name,
            "type": dict(doc._fields["document_type"].selection).get(doc.document_type) or doc.document_type,
        } for doc in prop.document_ids]

        return {
            "building": {
                "id": building.id,
                "name": building._short_name(),
                "full_name": building.name,
                "code": building.tower_code or building._display_code(index),
                "status": status,
                "status_label": status_labels.get(status) or "Active",
                "property_id": prop.id,
                "property_name": prop.name,
                "location": location,
            },
            "kpis": {
                "floors": len(building.floor_ids),
                "wings": len(wings) or 0,
                "units": len(units),
                "occupied": occupied,
                "vacant": vacant,
                "occupancy_pct": round(occupied / len(units) * 100) if units else 0,
                "vacant_pct": round(vacant / len(units) * 100) if units else 0,
            },
            "bands": self._hierarchy_bands(building),
            "activities": activities,
            "floors": floors,
            "units": unit_rows,
            "unit_total": len(units),
            "documents": documents,
        }


class PropertyFloor(models.Model):
    _name = "property.floor"
    _description = "Floor / Wing"
    _order = "floor_number, name"

    name = fields.Char(required=True)
    floor_number = fields.Integer()
    wing = fields.Char()
    building_id = fields.Many2one("property.building", required=True, ondelete="cascade")
    property_id = fields.Many2one(related="building_id.property_id", store=True)
    unit_ids = fields.One2many("property.unit", "floor_id")
    unit_count = fields.Integer(compute="_compute_unit_count")

    @api.depends("unit_ids")
    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)

    def _unit_stats(self, units):
        occupied = len(units.filtered(lambda unit: unit.status == "occupied"))
        total = len(units)
        return {
            "units": total,
            "occupied": occupied,
            "vacant": max(0, total - occupied),
        }

    def _units_by_floor_number(self, building):
        units_by_number = defaultdict(lambda: self.env["property.unit"])
        for unit in building.unit_ids:
            number = unit.floor_id.floor_number if unit.floor_id else 0
            units_by_number[number] |= unit
        return units_by_number

    def _wing_rows(self, records, units=None):
        rows = []
        for rec in records.sorted(lambda item: ((item.wing or "A").strip().upper(), item.id)):
            wing_name = (rec.wing or "A").strip().upper()[:1] or "A"
            stats = self._unit_stats(rec.unit_ids)
            rows.append({
                "id": rec.id,
                "name": f"Wing {wing_name}",
                "status": "active" if stats["units"] else "empty",
                "status_label": "Active" if stats["units"] else "Empty",
                **stats,
            })
        return rows

    @api.model
    def get_floors_workspace(self, building_id=None):
        Building = self.env["property.building"]
        Building._ensure_building_codes()
        buildings = Building.search([])
        building_rows = []
        for building in buildings:
            building_rows.append({
                "id": building.id,
                "name": building._short_name(),
                "full_name": building.name,
                "property_name": building.property_id.name,
                "units": building.unit_count,
                "floors": building.floor_count,
            })
        building_rows.sort(key=lambda row: (row["property_name"] or "", row["name"] or ""))
        selected_id = int(building_id or 0)
        if selected_id not in {row["id"] for row in building_rows}:
            selected_id = building_rows[0]["id"] if building_rows else 0
        selected = Building.browse(selected_id).exists()
        floor_rows = []
        if selected:
            units_by_number = self._units_by_floor_number(selected)
            grouped = defaultdict(lambda: self.browse())
            for floor in selected.floor_ids.sorted(lambda rec: (rec.floor_number or 0, rec.wing or "", rec.id)):
                grouped[floor.floor_number or 0] |= floor
            for number in sorted(grouped):
                records = grouped[number]
                units = units_by_number[number]
                stats = self._unit_stats(units)
                primary = records[:1]
                unique_wings = list(dict.fromkeys((rec.wing or "A") for rec in records))
                floor_rows.append({
                    "id": f"floor-{selected.id}-{number}",
                    "floor_id": primary.id,
                    "number": number,
                    "name": primary.name or f"Floor {number}",
                    "record_wings": unique_wings,
                    "wings": self._wing_rows(records, units),
                    **stats,
                })
        return {
            "buildings": building_rows,
            "selected_id": selected_id,
            "building": {
                "id": selected.id if selected else None,
                "name": selected._short_name() if selected else "",
                "full_name": selected.name if selected else "",
            },
            "floors": floor_rows,
        }

    @api.model
    def create_from_dashboard(self, vals):
        vals = dict(vals or {})
        building = self.env["property.building"].browse(int(vals.get("building_id") or 0)).exists()
        if not building:
            raise UserError("Please select a building.")
        existing_numbers = building.floor_ids.mapped("floor_number")
        number = int(vals.get("floor_number") or 0)
        if not number:
            number = (max(existing_numbers) if existing_numbers else 0) + 1
        wing = (vals.get("wing") or "A").strip().upper()[:1] or "A"
        name = (vals.get("name") or f"Floor {number}").strip()
        duplicate = self.search([
            ("building_id", "=", building.id),
            ("floor_number", "=", number),
            ("wing", "=", wing),
        ], limit=1)
        if duplicate:
            raise UserError(f"Wing {wing} already exists on Floor {number}.")
        return self.create({
            "name": name,
            "floor_number": number,
            "wing": wing,
            "building_id": building.id,
        }).id

    @api.model
    def update_from_dashboard(self, floor_id, vals):
        floor = self.browse(int(floor_id or 0)).exists()
        if not floor:
            raise UserError("Floor not found.")
        vals = dict(vals or {})
        name = (vals.get("name") or "").strip()
        number = int(vals.get("floor_number") or 0) or floor.floor_number
        updates = {"floor_number": number}
        if name:
            updates["name"] = name
        same_number = floor.building_id.floor_ids.filtered(lambda rec: rec.floor_number == floor.floor_number)
        same_number.write(updates)
        return True

    @api.model
    def delete_floor_group(self, building_id, floor_number):
        floors = self.search([
            ("building_id", "=", int(building_id or 0)),
            ("floor_number", "=", int(floor_number or 0)),
        ])
        if not floors:
            raise UserError("Floor not found.")
        floors.unlink()
        return True


class PropertyUnit(models.Model):
    _name = "property.unit"
    _description = "Unit"
    _order = "name"

    name = fields.Char(required=True)
    unit_type = fields.Char()
    area_sqft = fields.Float(string="Area (sqft)")
    status = fields.Selection(
        [
            ("occupied", "Occupied"),
            ("vacant", "Vacant"),
            ("maintenance", "Maintenance"),
            ("reserved", "Reserved"),
            ("available", "Available"),
        ],
        default="available",
        required=True,
        index=True,
    )
    property_id = fields.Many2one("property.property", required=True, ondelete="cascade")
    building_id = fields.Many2one("property.building", ondelete="cascade")
    floor_id = fields.Many2one("property.floor", ondelete="set null")
    tenant_id = fields.Many2one("res.partner", string="Tenant")
    owner_id = fields.Many2one("res.partner", string="Owner")
    tenancy_ids = fields.One2many("property.tenancy", "unit_id")

    def _initials(self, name):
        parts = [part for part in (name or "").split() if part]
        if not parts:
            return "—"
        return "".join(part[0] for part in parts[:2]).upper()

    def _occupancy_fields(self, status):
        if status == "reserved":
            return "reserved", "Reserved", "active", "Active"
        if status == "maintenance":
            return "occupied", "Occupied", "maintenance", "Maintenance"
        if status in ("vacant", "available"):
            return "vacant", "Vacant", "turnover", "Turnover"
        return "occupied", "Occupied", "active", "Active"

    def _directory_status(self, status):
        if status == "maintenance":
            return "maintenance", "Maintenance"
        if status == "reserved":
            return "reserved", "Reserved"
        if status in ("vacant", "available"):
            return "vacant", "Vacant"
        return "occupied", "Occupied"

    def _wing_label(self, wing):
        return {
            "A": "East",
            "B": "West",
            "C": "North",
            "D": "South",
        }.get((wing or "").strip().upper(), wing or "—")

    def _unit_row(self, unit):
        occupancy, occupancy_label, op_status, op_label = self._occupancy_fields(unit.status)
        owner = unit.owner_id
        if not owner and unit.property_id.owner_ids:
            owner = unit.property_id.owner_ids[:1].partner_id
        floor = unit.floor_id
        number = floor.floor_number if floor else False
        wing = floor.wing if floor else False
        building = unit.building_id
        return {
            "id": unit.id,
            "name": unit.name,
            "property_id": unit.property_id.id,
            "property_name": unit.property_id.name,
            "building_id": building.id if building else False,
            "building_name": building._short_name() if building else "—",
            "floor_id": floor.id if floor else False,
            "floor_number": number or "",
            "wing": wing or "",
            "floor_wing": f"Fl {number} / {self._wing_label(wing)}" if number else "—",
            "config": unit.unit_type or "—",
            "area_sqft": unit.area_sqft or 0,
            "owner_name": owner.name if owner else "Unassigned",
            "owner_initials": self._initials(owner.name) if owner else "—",
            "occupancy": occupancy,
            "occupancy_label": occupancy_label,
            "op_status": op_status,
            "op_status_label": op_label,
            "status": unit.status,
        }

    @api.model
    def get_units_data(self):
        self.env["property.building"]._ensure_building_codes()
        units = self.search([])
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        buildings = [{
            "id": building.id,
            "name": building._short_name(),
            "property_id": building.property_id.id,
        } for building in self.env["property.building"].search([])]
        floors = [{
            "id": floor.id,
            "name": floor.name,
            "number": floor.floor_number,
            "wing": floor.wing or "",
            "building_id": floor.building_id.id,
        } for floor in self.env["property.floor"].search([])]
        types = sorted({unit.unit_type for unit in units if unit.unit_type})
        return {
            "units": [self._unit_row(unit) for unit in units],
            "properties": properties,
            "buildings": buildings,
            "floors": floors,
            "types": types,
        }

    @api.model
    def get_occupancy_data(self):
        self.env["property.building"]._ensure_building_codes()
        units = self.search([])
        units.mapped("tenant_id")
        units.mapped("tenancy_ids.tenant_id")
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        buildings = [{
            "id": building.id,
            "name": building._short_name(),
            "property_id": building.property_id.id,
        } for building in self.env["property.building"].search([])]
        floors = [{
            "id": floor.id,
            "name": floor.name,
            "number": floor.floor_number,
            "building_id": floor.building_id.id,
        } for floor in self.env["property.floor"].search([])]
        tenancy_by_unit = defaultdict(list)
        for tenancy in self.env["property.tenancy"].search([("unit_id", "in", units.ids)]):
            tenancy_by_unit[tenancy.unit_id.id].append({
                "start": tenancy.date_start.isoformat() if tenancy.date_start else False,
                "end": tenancy.date_end.isoformat() if tenancy.date_end else False,
            })
        rows = []
        for unit in units:
            tenant = unit.tenant_id
            if not tenant:
                active = unit.tenancy_ids.filtered(lambda rec: rec.state == "active")[:1]
                tenant = active.tenant_id
            tenant_name = tenant.name if tenant else ""
            directory_status, directory_label = self._directory_status(unit.status)
            rows.append({
                "id": unit.id,
                "name": unit.name,
                "property_id": unit.property_id.id,
                "property_name": unit.property_id.name,
                "building_id": unit.building_id.id if unit.building_id else False,
                "floor_id": unit.floor_id.id if unit.floor_id else False,
                "floor_number": unit.floor_id.floor_number if unit.floor_id else False,
                "tenant": tenant_name or "Empty",
                "tenant_empty": not bool(tenant_name),
                "directory_status": directory_status,
                "directory_label": directory_label,
                "tenancies": tenancy_by_unit.get(unit.id, []),
            })
        today = fields.Date.context_today(self)
        months = []
        for offset in range(5, -1, -1):
            month = today.month - offset
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            months.append(calendar.month_abbr[month])
        return {
            "units": rows,
            "properties": properties,
            "buildings": buildings,
            "floors": floors,
            "months": months,
            "target": 95,
        }

    @api.model
    def create_from_dashboard(self, vals):
        vals = dict(vals or {})
        name = (vals.get("name") or "").strip()
        property_id = int(vals.get("property_id") or 0)
        if not name:
            raise UserError("Unit name is required.")
        prop = self.env["property.property"].browse(property_id).exists()
        if not prop:
            raise UserError("Please select a property.")
        building = self.env["property.building"].browse(int(vals.get("building_id") or 0)).exists()
        floor = self.env["property.floor"].browse(int(vals.get("floor_id") or 0)).exists()
        if floor and not building:
            building = floor.building_id
        status = vals.get("status") or "available"
        if status not in dict(self._fields["status"].selection):
            status = "available"
        unit = self.create({
            "name": name,
            "property_id": prop.id,
            "building_id": building.id if building else False,
            "floor_id": floor.id if floor else False,
            "unit_type": (vals.get("unit_type") or "").strip() or False,
            "status": status,
            "area_sqft": float(vals.get("area_sqft") or 0),
        })
        return {"id": unit.id}

    def _unit_write_vals(self, vals):
        vals = dict(vals or {})
        name = (vals.get("name") or "").strip()
        if not name:
            raise UserError("Unit name is required.")
        prop = self.env["property.property"].browse(int(vals.get("property_id") or 0)).exists()
        if not prop:
            raise UserError("Please select a property.")
        building = self.env["property.building"].browse(int(vals.get("building_id") or 0)).exists()
        floor = self.env["property.floor"].browse(int(vals.get("floor_id") or 0)).exists()
        if floor and not building:
            building = floor.building_id
        if building and building.property_id and building.property_id.id != prop.id:
            raise UserError("The building does not belong to the selected property.")
        if floor and building and floor.building_id and floor.building_id.id != building.id:
            raise UserError("The floor does not belong to the selected building.")
        status = vals.get("status") or "available"
        if status not in dict(self._fields["status"].selection):
            status = "available"
        return {
            "name": name,
            "property_id": prop.id,
            "building_id": building.id if building else False,
            "floor_id": floor.id if floor else False,
            "unit_type": (vals.get("unit_type") or "").strip() or False,
            "status": status,
            "area_sqft": float(vals.get("area_sqft") or 0),
        }

    @api.model
    def update_from_dashboard(self, vals):
        unit = self.browse(int((vals or {}).get("id") or 0)).exists()
        if not unit:
            raise UserError("Unit not found.")
        payload = self._unit_write_vals(vals)
        unit.write(payload)
        self.env["property.activity.log"].create({
            "name": f"Unit updated: {unit.name}",
            "description": f"{unit.name} details were saved.",
            "activity_type": "document",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return {"id": unit.id}

    def _property_address(self, prop):
        parts = [prop.street, prop.location, prop.city, prop.state_name, prop.zip, prop.country]
        return ", ".join(part for part in parts if part) or prop.name or "Location unavailable"

    def _property_coords(self, prop):
        city_coords = {
            "Mumbai": (19.0760, 72.8777),
            "Delhi": (28.6139, 77.2090),
            "Pune": (18.5204, 73.8567),
            "Bengaluru": (12.9716, 77.5946),
            "Hyderabad": (17.3850, 78.4867),
            "Kolkata": (22.5726, 88.3639),
            "Chennai": (13.0827, 80.2707),
            "Jaipur": (26.9124, 75.7873),
            "Ahmedabad": (23.0225, 72.5714),
            "Kochi": (9.9312, 76.2673),
            "Bhubaneswar": (20.2961, 85.8245),
            "Downtown Metro": (19.0760, 72.8777),
            "North Ridge": (28.6139, 77.2090),
            "Central Quarter": (18.5204, 73.8567),
            "Tech Park": (12.9716, 77.5946),
            "Financial District": (17.3850, 78.4867),
            "Riverside": (22.5726, 88.3639),
            "Marina Bay": (13.0827, 80.2707),
            "Heritage District": (26.9124, 75.7873),
            "Westside Arts": (23.0225, 72.5714),
            "Harbor Line": (9.9312, 76.2673),
            "East Campus": (20.2961, 85.8245),
        }
        return city_coords.get(prop.city) or city_coords.get(prop.location) or (20.5937, 78.9629)

    def _property_map_query(self, prop):
        return ", ".join(part for part in [prop.name, prop.street, prop.location, prop.city, prop.state_name, prop.country] if part)

    def _property_map_url(self, prop):
        from urllib.parse import quote
        lat, lon = self._property_coords(prop)
        delta = 0.03
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
        return (
            "https://www.openstreetmap.org/export/embed.html?"
            f"bbox={quote(bbox)}&layer=mapnik&marker={lat}%2C{lon}"
        )

    def _property_map_open_url(self, prop):
        from urllib.parse import quote
        lat, lon = self._property_coords(prop)
        query = quote(self._property_map_query(prop))
        return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}&query={query}"

    def _partner_by_name(self, name):
        name = (name or "").strip()
        if not name:
            raise UserError("Name is required.")
        Partner = self.env["res.partner"]
        return Partner.search([("name", "=", name)], limit=1) or Partner.create({"name": name})

    @api.model
    def get_unit_detail(self, unit_id):
        unit = self.browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("Unit not found.")
        occupancy, occupancy_label, op_status, op_label = self._occupancy_fields(unit.status)
        owner = unit.owner_id
        if not owner and unit.property_id.owner_ids:
            owner = unit.property_id.owner_ids[:1].partner_id
        tenant = unit.tenant_id
        if not tenant:
            active = unit.tenancy_ids.filtered(lambda rec: rec.state == "active")[:1]
            tenant = active.tenant_id
        floor = unit.floor_id
        building = unit.building_id
        prop = unit.property_id
        number = floor.floor_number if floor else False
        wing = (floor.wing if floor else "") or ""
        area = unit.area_sqft or 0
        carpet = round(area * 0.88) if area else 0
        type_labels = dict(prop._fields["property_type"].selection)
        Property = self.env["property.property"]
        owners = []
        if unit.owner_id:
            owners.append({"id": f"u-{unit.owner_id.id}", "name": unit.owner_id.name, "share": 100, "source": "Unit"})
        for rec in prop.owner_ids:
            owners.append({
                "id": rec.id,
                "name": rec.partner_id.name,
                "share": rec.share_percent,
                "source": "Property",
            })
        tenants = []
        for rec in unit.tenancy_ids:
            tenants.append({
                "id": rec.id,
                "name": rec.tenant_id.name,
                "start": rec.date_start.isoformat() if rec.date_start else "",
                "end": rec.date_end.isoformat() if rec.date_end else "—",
                "state": rec.state,
                "state_label": dict(rec._fields["state"].selection).get(rec.state) or rec.state,
            })
        documents = [{
            "id": doc.id,
            "name": doc.name,
            "type": dict(doc._fields["document_type"].selection).get(doc.document_type) or doc.document_type,
        } for doc in prop.document_ids]
        history = []
        logs = self.env["property.activity.log"].search([("unit_id", "=", unit.id)], limit=12)
        for activity in logs:
            history.append({
                "id": f"a-{activity.id}",
                "title": activity.name,
                "description": activity.description or "",
                "when": Property._format_activity_ago(activity.event_date),
                "type": activity.activity_type or "document",
            })
        if not history:
            for rec in unit.tenancy_ids[:6]:
                history.append({
                    "id": f"t-{rec.id}",
                    "title": "Tenancy " + (dict(rec._fields["state"].selection).get(rec.state) or rec.state),
                    "description": rec.tenant_id.name or "",
                    "when": rec.date_start.strftime("%b %d, %Y") if rec.date_start else "",
                    "type": "lease",
                })
        return {
            "unit": {
                "id": unit.id,
                "name": unit.name,
                "property_id": prop.id,
                "property_name": prop.name,
                "building_id": building.id if building else False,
                "building_name": building._short_name() if building else "—",
                "floor_id": floor.id if floor else False,
                "floor_label": f"Floor {number}" if number else (floor.name if floor else "—"),
                "wing": wing,
                "wing_label": f"Wing {wing}" if wing else "—",
                "location": prop.location or prop.city or "",
                "address": self._property_address(prop),
                "map_url": self._property_map_url(prop),
                "map_open_url": self._property_map_open_url(prop),
                "op_status": op_status,
                "op_status_label": op_label,
                "occupancy": occupancy,
                "occupancy_label": occupancy_label,
                "status": unit.status,
            },
            "kpis": {
                "area": f"{int(area):,}" if area else "—",
                "config": unit.unit_type or "—",
                "owner": owner.name if owner else "Unassigned",
                "tenant": tenant.name if tenant else "Unassigned",
                "occupancy": occupancy,
                "occupancy_label": occupancy_label,
            },
            "info": {
                "number": unit.name,
                "unit_type": type_labels.get(prop.property_type) or "Residential",
                "config": unit.unit_type or "—",
                "carpet": f"{carpet:,}" if carpet else "—",
                "built": f"{int(area):,}" if area else "—",
                "floor": str(number) if number else "—",
                "wing": wing or "—",
                "parking": f"P-{(unit.id % 80) + 10}",
            },
            "owners": owners,
            "tenants": tenants,
            "documents": documents,
            "history": history,
        }

    STATUS_BOARD_UPLOADERS = [
        ("Jane Doe", "JD"),
        ("Michael Chen", "MC"),
        ("Priya Shah", "PS"),
        ("Elena Rossi", "ER"),
        ("David Cole", "DC"),
        ("Amina Rahman", "AR"),
    ]

    def _board_status(self, status):
        if status == "maintenance":
            return "unoccupied", "Unoccupied"
        if status in ("vacant", "available"):
            return "available", "Available"
        return "occupied", "Occupied"

    def _status_has_lease(self, unit):
        if unit.tenant_id:
            return True
        if unit.status in ("occupied", "reserved"):
            return True
        return bool(unit.tenancy_ids.filtered(lambda rec: rec.state == "active"))

    def _status_row(self, unit, log=None):
        board, board_label = self._board_status(unit.status)
        labels = dict(self._fields["status"].selection)
        if log:
            updater = log.create_uid.name if log.create_uid else "System"
            initials = self._initials(updater)
            updated = log.event_date or unit.write_date
        else:
            updater, initials = self.STATUS_BOARD_UPLOADERS[unit.id % len(self.STATUS_BOARD_UPLOADERS)]
            updated = unit.write_date
        updated_date = updated.date() if updated and hasattr(updated, "date") else updated
        return {
            "id": unit.id,
            "name": unit.name,
            "property_id": unit.property_id.id,
            "property_name": unit.property_id.name,
            "building_name": unit.building_id._short_name() if unit.building_id else unit.property_id.name,
            "place": f"{unit.name} • {unit.property_id.name}",
            "status": unit.status,
            "status_label": labels.get(unit.status) or unit.status,
            "board": board,
            "board_label": board_label,
            "has_lease": self._status_has_lease(unit),
            "tenant_name": unit.tenant_id.name if unit.tenant_id else "",
            "updated_by": updater,
            "updated_initials": initials,
            "updated_on": updated_date.isoformat() if updated_date else "",
            "updated_label": updated_date.strftime("%b %d, %Y") if updated_date else "—",
        }

    @api.model
    def get_unit_status_data(self):
        units = self.search([])
        units.mapped("tenant_id")
        units.mapped("building_id")
        logs = self.env["property.activity.log"].search([("unit_id", "!=", False)])
        last_log = {}
        for log in logs:
            if log.unit_id.id not in last_log:
                last_log[log.unit_id.id] = log
        rows = [self._status_row(unit, last_log.get(unit.id)) for unit in units]
        available = sum(1 for row in rows if row["board"] == "available")
        occupied = sum(1 for row in rows if row["board"] == "occupied")
        unoccupied = sum(1 for row in rows if row["board"] == "unoccupied")
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        return {
            "records": rows,
            "properties": properties,
            "kpis": {
                "available": available,
                "occupied": occupied,
                "unoccupied": unoccupied,
            },
        }

    def _apply_status_change(self, unit, status, extra=None):
        extra = extra or {}
        unit.status = status
        occupancy, occupancy_label, _op, op_label = self._occupancy_fields(status)
        reason = extra.get("reason") or ""
        notes = extra.get("notes") or ""
        effective = extra.get("effective_date") or ""
        parts = [f"{unit.name} is now {op_label.lower()} / {occupancy_label.lower()}."]
        if reason:
            parts.append(f"Reason: {reason}.")
        if effective:
            parts.append(f"Effective: {effective}.")
        if notes:
            parts.append(notes)
        self.env["property.activity.log"].create({
            "name": f"Status changed to {occupancy_label}",
            "description": " ".join(parts),
            "activity_type": "alert" if status in ("vacant", "maintenance") else "document",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })

    @api.model
    def update_status(self, unit_id, status, extra=None):
        unit = self.browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("Unit not found.")
        if status not in dict(self._fields["status"].selection):
            raise UserError("Invalid status.")
        self._apply_status_change(unit, status, extra)
        return True

    @api.model
    def bulk_update_status(self, unit_ids, status, extra=None):
        if status not in dict(self._fields["status"].selection):
            raise UserError("Invalid status.")
        units = self.browse([int(uid) for uid in (unit_ids or [])]).exists()
        if not units:
            raise UserError("Select at least one unit.")
        for unit in units:
            self._apply_status_change(unit, status, extra)
        return {"count": len(units)}

    @api.model
    def add_tenant(self, unit_id, vals):
        unit = self.browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("Unit not found.")
        vals = dict(vals or {})
        partner = self._partner_by_name(vals.get("name"))
        start = vals.get("date_start") or fields.Date.today()
        unit.tenancy_ids.filtered(lambda rec: rec.state == "active").write({
            "state": "ended",
            "date_end": fields.Date.today(),
        })
        self.env["property.tenancy"].create({
            "unit_id": unit.id,
            "tenant_id": partner.id,
            "date_start": start,
            "state": "active",
        })
        unit.tenant_id = partner.id
        if unit.status in ("vacant", "available"):
            unit.status = "occupied"
        self.env["property.activity.log"].create({
            "name": f"Tenant added: {partner.name}",
            "description": f"{partner.name} assigned to {unit.name}.",
            "activity_type": "lease",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return True

    @api.model
    def add_owner(self, unit_id, vals):
        unit = self.browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("Unit not found.")
        vals = dict(vals or {})
        partner = self._partner_by_name(vals.get("name"))
        unit.owner_id = partner.id
        Owner = self.env["property.owner"]
        existing = Owner.search([("property_id", "=", unit.property_id.id), ("partner_id", "=", partner.id)], limit=1)
        if not existing:
            Owner.create({
                "property_id": unit.property_id.id,
                "unit_id": unit.id,
                "partner_id": partner.id,
                "share_percent": float(vals.get("share") or 100),
                "owner_type": "primary",
                "status": "active",
            })
        self.env["property.activity.log"].create({
            "name": f"Owner assigned: {partner.name}",
            "description": f"{partner.name} is now owner of {unit.name}.",
            "activity_type": "document",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return True
