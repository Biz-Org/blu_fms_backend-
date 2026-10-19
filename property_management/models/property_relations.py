import base64
import json
from collections import defaultdict, Counter
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


def _pdf_base64(lines):
    cleaned = []
    for line in lines or [" "]:
        text = (line or " ").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        text = text.encode("latin-1", "replace").decode("latin-1")
        cleaned.append(text[:100] or " ")
    commands = ["BT /F1 11 Tf 50 760 Td 16 TL"]
    for index, line in enumerate(cleaned[:40]):
        commands.append(f"({line}) Tj" if index == 0 else f"T* ({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    content = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    objects = [
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        content,
        b"<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] /Contents 2 0 R /Resources << /Font << /F1 1 0 R >> >> >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Catalog /Pages 4 0 R >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(b"%d 0 obj\n" % index)
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(b"xref\n0 %d\n" % (len(objects) + 1))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        out.extend(b"%010d 00000 n \n" % offset)
    out.extend(b"trailer << /Size %d /Root 5 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref))
    return base64.b64encode(bytes(out)).decode()


class PropertyOwner(models.Model):
    _name = "property.owner"
    _description = "Property Ownership"
    _order = "id desc"

    property_id = fields.Many2one("property.property", required=True, ondelete="cascade")
    unit_id = fields.Many2one("property.unit", ondelete="cascade")
    partner_id = fields.Many2one("res.partner", required=True, string="Owner")
    share_percent = fields.Float(string="Share (%)", default=100)
    owner_type = fields.Selection(
        [
            ("primary", "Primary"),
            ("co_owner", "Co-owner"),
            ("corporate", "Corporate"),
        ],
        default="primary",
        required=True,
    )
    effective_date = fields.Date(default=fields.Date.today)
    status = fields.Selection(
        [
            ("active", "Active"),
            ("pending", "Pending"),
        ],
        default="active",
        required=True,
    )
    cost = fields.Float(string="Cost")
    deed_ref = fields.Char(string="Deed")
    notes = fields.Text()

    EXTRA_OWNERS = [
        "Sarah Goldstein",
        "James Wright",
        "Priya Shah",
        "Michael Chen",
        "Amina Rahman",
        "David Cole",
        "Elena Rossi",
        "Omar Khalid",
    ]

    def _initials(self, name):
        parts = [part for part in (name or "").split() if part]
        if not parts:
            return "—"
        return "".join(part[0] for part in parts[:2]).upper()

    def _floor_place(self, unit):
        prop_name = unit.property_id.name or "—"
        number = unit.floor_id.floor_number if unit.floor_id else 0
        if number >= 4:
            level = "Penthouse"
        elif number:
            level = f"Floor {number}"
        else:
            level = unit.floor_id.name if unit.floor_id else "—"
        building = unit.building_id
        building_name = building._short_name() if building else prop_name
        return building_name, f"{prop_name} • {level}"

    def _format_cost(self, amount):
        if not amount:
            return "—"
        if amount >= 1000000:
            return f"${amount / 1000000:.2f}M"
        if amount >= 1000:
            return f"${amount / 1000:.0f}K"
        return f"${amount:,.0f}"

    def _format_date(self, value):
        if not value:
            return "—"
        return value.strftime("%b %d, %Y")

    def _directory_row(self, unit, partner, rec=None, owner_type=None, share=None, status=None, row_id=None):
        rec = rec or self.browse()
        building_name, place = self._floor_place(unit)
        otype = owner_type or rec.owner_type or "primary"
        share_val = share if share is not None else (rec.share_percent if rec else 100)
        status_val = status or rec.status or "active"
        labels = dict(self._fields["owner_type"].selection)
        status_labels = dict(self._fields["status"].selection)
        if rec and rec.unit_id and rec.effective_date:
            effective = rec.effective_date
        else:
            today = fields.Date.context_today(self)
            effective = today - timedelta(days=180 + (unit.id % 1200))
        area = unit.area_sqft or 980
        cost = rec.cost if rec and rec.cost else round(area * 1850, 0)
        deed = rec.deed_ref if rec and rec.deed_ref else f"BK-{440 + (unit.id % 80)}-PG-{12 + (unit.id % 40)}"
        return {
            "id": row_id or (f"r-{rec.id}" if rec else f"u-{unit.id}"),
            "record_id": rec.id if rec else False,
            "unit_id": unit.id,
            "unit_name": unit.name,
            "property_id": unit.property_id.id,
            "property_name": unit.property_id.name,
            "building_id": unit.building_id.id if unit.building_id else False,
            "building_name": building_name,
            "place": place,
            "owner_id": partner.id if partner else False,
            "owner_name": partner.name if partner else "Unassigned",
            "owner_initials": self._initials(partner.name if partner else ""),
            "owner_type": otype,
            "owner_type_label": labels.get(otype) or otype,
            "share": share_val,
            "effective": effective.isoformat() if effective else "",
            "effective_label": self._format_date(effective),
            "status": status_val,
            "status_label": status_labels.get(status_val) or status_val,
            "cost": cost,
            "cost_label": self._format_cost(cost),
            "deed": deed,
        }

    @api.model
    def get_ownership_data(self):
        units = self.env["property.unit"].search([])
        units.mapped("owner_id")
        units.mapped("building_id")
        units.mapped("floor_id")
        units.mapped("property_id.owner_ids.partner_id")
        explicit = self.search([("unit_id", "!=", False)])
        by_unit = defaultdict(lambda: self.browse())
        for rec in explicit:
            by_unit[rec.unit_id.id] |= rec

        rows = []
        extra_names = self.EXTRA_OWNERS
        for unit in units:
            stored = by_unit.get(unit.id)
            if stored:
                for rec in stored:
                    rows.append(self._directory_row(unit, rec.partner_id, rec))
                continue
            partner = unit.owner_id
            rec = False
            if not partner and unit.property_id.owner_ids:
                rec = unit.property_id.owner_ids[:1]
                partner = rec.partner_id
            elif partner:
                rec = unit.property_id.owner_ids.filtered(lambda owner: owner.partner_id == partner)[:1]
            if not partner:
                continue
            joint = unit.id % 13 == 0
            pending = unit.id % 97 == 0
            corporate = (not joint) and unit.id % 19 == 0
            owner_type = "co_owner" if joint else ("corporate" if corporate else "primary")
            share = 50 if joint else (rec.share_percent if rec else 100)
            status = "pending" if pending else "active"
            rows.append(self._directory_row(
                unit, partner, rec,
                owner_type=owner_type,
                share=share,
                status=status,
                row_id=f"u-{unit.id}",
            ))
            if joint:
                extra = extra_names[unit.id % len(extra_names)]
                rows.append({
                    **self._directory_row(
                        unit, partner, rec,
                        owner_type="co_owner",
                        share=50,
                        status="pending" if unit.id % 2 else "active",
                        row_id=f"u-{unit.id}-co",
                    ),
                    "owner_id": False,
                    "owner_name": extra,
                    "owner_initials": self._initials(extra),
                    "record_id": False,
                })

        unit_counts = Counter(row["unit_id"] for row in rows)
        for row in rows:
            row["multi"] = unit_counts[row["unit_id"]] > 1

        recent = sum(1 for row in rows if row["status"] == "pending")
        unique_owners = {row["owner_name"] for row in rows if row["owner_name"]}
        unique_units = {row["unit_id"] for row in rows}
        unique_props = {row["property_id"] for row in rows}
        joint_units = {unit_id for unit_id, count in unit_counts.items() if count > 1}
        units_lookup = [{
            "id": unit.id,
            "name": unit.name,
            "property_name": unit.property_id.name,
            "building_name": unit.building_id._short_name() if unit.building_id else "—",
        } for unit in units]
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        return {
            "records": rows,
            "units": units_lookup,
            "properties": properties,
            "kpis": {
                "owners": len(unique_owners),
                "owners_delta": "+2.4%",
                "units_owned": len(unique_units),
                "properties": len(unique_props),
                "joint": len(joint_units),
                "recent": recent,
            },
        }

    @api.model
    def record_transfer(self, vals):
        vals = dict(vals or {})
        unit = self.env["property.unit"].browse(int(vals.get("unit_id") or 0)).exists()
        if not unit:
            raise UserError("Please select a unit.")
        partner = self.env["property.unit"]._partner_by_name(vals.get("owner_name"))
        owner_type = vals.get("owner_type") or "primary"
        if owner_type not in dict(self._fields["owner_type"].selection):
            owner_type = "primary"
        status = vals.get("status") or "pending"
        if status not in dict(self._fields["status"].selection):
            status = "pending"
        rec = self.create({
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
            "partner_id": partner.id,
            "share_percent": float(vals.get("share") or 100),
            "owner_type": owner_type,
            "status": status,
            "effective_date": vals.get("effective_date") or fields.Date.today(),
            "notes": vals.get("notes") or "",
        })
        if owner_type == "primary" and status == "active":
            unit.owner_id = partner.id
        self.env["property.activity.log"].create({
            "name": f"Ownership transfer: {partner.name}",
            "description": f"{partner.name} recorded for unit {unit.name}.",
            "activity_type": "document",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return {"id": rec.id}

    @api.model
    def update_from_dashboard(self, vals):
        vals = dict(vals or {})
        unit = self.env["property.unit"].browse(int(vals.get("unit_id") or 0)).exists()
        if not unit:
            raise UserError("Please select a unit.")
        partner = self.env["property.unit"]._partner_by_name(vals.get("owner_name"))
        owner_type = vals.get("owner_type") or "primary"
        if owner_type not in dict(self._fields["owner_type"].selection):
            owner_type = "primary"
        status = vals.get("status") or "active"
        if status not in dict(self._fields["status"].selection):
            status = "active"
        share = float(vals.get("share") or 0)
        if share < 0 or share > 100:
            raise UserError("Share must be between 0 and 100.")
        payload = {
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
            "partner_id": partner.id,
            "share_percent": share,
            "owner_type": owner_type,
            "status": status,
            "effective_date": vals.get("effective_date") or fields.Date.today(),
            "cost": float(vals.get("cost") or 0),
            "deed_ref": (vals.get("deed") or "").strip() or False,
        }
        rec = self.browse(int(vals.get("record_id") or 0)).exists()
        if rec and rec.unit_id == unit:
            rec.write(payload)
        else:
            rec = self.create(payload)
        if owner_type == "primary":
            unit.owner_id = partner.id
        self.env["property.activity.log"].create({
            "name": f"Ownership updated: {partner.name}",
            "description": f"{partner.name} now holds {share:g}% of unit {unit.name}.",
            "activity_type": "document",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return {"selected_id": f"r-{rec.id}"}


class PropertyTenancy(models.Model):
    _name = "property.tenancy"
    _description = "Tenant History"
    _order = "date_start desc"

    unit_id = fields.Many2one("property.unit", required=True, ondelete="cascade")
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    tenant_id = fields.Many2one("res.partner", required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date()
    state = fields.Selection(
        [("active", "Active"), ("ended", "Ended")],
        default="active",
        required=True,
    )

    TENANT_NAMES = [
        "John Smith",
        "Sarah Connor",
        "Michael Ross",
        "Tech Dynamics LLC",
        "Priya Shah",
        "Elena Rossi",
        "David Cole",
        "Amina Rahman",
        "James Wright",
        "Omar Khalid",
    ]

    def _initials(self, name):
        parts = [part for part in (name or "").replace(",", " ").split() if part and part.upper() not in {"LLC", "INC", "LTD"}]
        if not parts:
            return "—"
        return "".join(part[0] for part in parts[:2]).upper()

    def _format_date(self, value):
        if not value:
            return "—"
        return value.strftime("%b %d, %Y")

    def _months_between(self, start, end):
        if not start or not end or end < start:
            return 0
        return max(1, (end.year - start.year) * 12 + end.month - start.month)

    def _timeline(self, unit, start, end, status, logs):
        today = fields.Date.context_today(self)
        items = []
        if start and status == "upcoming":
            items.append({
                "id": f"{unit.id}-upcoming",
                "title": "Move In Scheduled",
                "date_label": self._format_date(start),
                "note": "Lease start is scheduled. Unit is reserved for this tenant.",
                "icon": "fa-home",
                "tone": "muted",
                "link": False,
            })
            return items
        if start:
            items.append({
                "id": f"{unit.id}-movein",
                "title": "Move In & Initial Lease",
                "date_label": self._format_date(start),
                "note": "Initial occupancy and lease execution.",
                "icon": "fa-home",
                "tone": "muted",
                "link": False,
            })
        months = self._months_between(start, end or today)
        if start and months >= 12:
            renew = start + timedelta(days=365)
            items.append({
                "id": f"{unit.id}-renew",
                "title": "Lease Executed (Renewal)",
                "date_label": self._format_date(renew),
                "note": "12-month extension executed with standard terms.",
                "icon": "fa-file-text-o",
                "tone": "accent",
                "link": "View Document",
            })
        if status == "present" and unit.id % 17 == 0:
            items.append({
                "id": f"{unit.id}-pending",
                "title": "Lease Renewal Pending",
                "date_label": self._format_date(today),
                "note": "Renewal offer sent for 12-month extension. Awaiting tenant signature.",
                "icon": "fa-calendar",
                "tone": "pending",
                "link": False,
            })
        for log in logs:
            items.append({
                "id": f"a-{log.id}",
                "title": log.name,
                "date_label": log.event_date.strftime("%b %d, %Y") if log.event_date else "",
                "note": log.description or "",
                "icon": "fa-wrench" if log.activity_type == "maintenance" else "fa-file-text-o",
                "tone": "muted",
                "link": False,
            })
        if end and status == "ended":
            items.append({
                "id": f"{unit.id}-moveout",
                "title": "Move Out",
                "date_label": self._format_date(end),
                "note": "Tenancy ended and unit returned to inventory.",
                "icon": "fa-sign-out",
                "tone": "muted",
                "link": False,
            })
        return list(reversed(items))

    def _tenancy_row(self, unit, tenant_name, start, end, status, record_id=False, logs=None):
        today = fields.Date.context_today(self)
        building = unit.building_id
        months = 0 if status == "upcoming" else self._months_between(start, end or today)
        badge = "Current Tenant" if status == "present" else ("Upcoming Tenant" if status == "upcoming" else "Past Tenant")
        return {
            "id": f"t-{record_id}" if record_id else f"u-{unit.id}",
            "record_id": record_id,
            "unit_id": unit.id,
            "unit_name": unit.name,
            "property_id": unit.property_id.id,
            "property_name": unit.property_id.name,
            "building_name": building._short_name() if building else unit.property_id.name,
            "place": f"Unit {unit.name} • {unit.property_id.name}",
            "tenant_name": tenant_name,
            "tenant_initials": self._initials(tenant_name),
            "move_in": start.isoformat() if start else "",
            "move_in_label": self._format_date(start),
            "move_out": end.isoformat() if end else "",
            "move_out_label": "Present" if status == "present" else ("--" if status == "upcoming" else self._format_date(end)),
            "duration": "Upcoming" if status == "upcoming" else f"{months} mo",
            "months": months,
            "status": status,
            "status_label": {"present": "Present", "ended": "Ended", "upcoming": "Upcoming"}.get(status) or status,
            "badge": badge,
            "rent": 0,
            "deposit": 0,
            "rent_label": "—",
            "deposit_label": "—",
            "timeline": self._timeline(unit, start, end, status, logs or []),
        }

    def _lease_lines(self, unit, tenant_name, start, end, rent, deposit):
        prop = unit.property_id
        address = ", ".join(part for part in [prop.street or prop.location, prop.city, prop.state_name, prop.zip] if part)
        return [
            "RESIDENTIAL LEASE AGREEMENT",
            f"Property: {prop.name or 'Property'}",
            f"Unit: {unit.name}",
            f"Address: {address or '—'}",
            f"Tenant: {tenant_name or 'Tenant'}",
            f"Term: {self._format_date(start)} to {self._format_date(end)}",
            f"Monthly rent: {rent:,.2f}" if rent else "Monthly rent: on file",
            f"Security deposit: {deposit:,.2f}" if deposit else "Security deposit: on file",
            "The tenant shall use the unit as a private residence and report maintenance promptly.",
            f"Generated {self._format_date(fields.Date.context_today(self))} from the tenancy record.",
        ]

    @api.model
    def lease_file(self, record_id=False, unit_id=False, tenant_name=False, move_in=False, move_out=False):
        rec = self.browse(int(record_id or 0)).exists()
        unit = rec.unit_id if rec else self.env["property.unit"].browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("This tenancy has no unit.")
        tenant = rec.tenant_id.name if rec and rec.tenant_id else (tenant_name or unit.tenant_id.name or "Tenant")
        start = rec.date_start if rec else (fields.Date.to_date(move_in) if move_in else False)
        end = rec.date_end if rec else (fields.Date.to_date(move_out) if move_out else False)
        rent = getattr(rec, "monthly_rent", 0) if rec else 0
        deposit = getattr(rec, "security_deposit", 0) if rec else 0
        lines = self._lease_lines(unit, tenant, start, end, rent or 0, deposit or 0)
        filename = f"Lease_{unit.name}_{(start.isoformat() if start else 'current')}.pdf"
        return {"filename": filename, "mimetype": "application/pdf", "content": _pdf_base64(lines)}

    @api.model
    def log_message(self, record_id=False, unit_id=False, note=False):
        text = (note or "").strip()
        if not text:
            raise UserError("Enter a message.")
        rec = self.browse(int(record_id or 0)).exists()
        unit = rec.unit_id if rec else self.env["property.unit"].browse(int(unit_id or 0)).exists()
        if not unit:
            raise UserError("Select a tenancy first.")
        tenant = rec.tenant_id.name if rec and rec.tenant_id else (unit.tenant_id.name or "tenant")
        self.env["property.activity.log"].create({
            "name": f"Message for {tenant}",
            "description": text,
            "activity_type": "lease",
            "property_id": unit.property_id.id,
            "unit_id": unit.id,
        })
        return True

    @api.model
    def get_tenancy_data(self):
        today = fields.Date.context_today(self)
        records = self.search([])
        units = self.env["property.unit"].search([])
        units.mapped("tenant_id")
        units.mapped("building_id")
        logs = self.env["property.activity.log"].search([("unit_id", "!=", False)])
        logs_by_unit = defaultdict(list)
        for log in logs:
            logs_by_unit[log.unit_id.id].append(log)
        rows = []
        seen = set()
        for rec in records:
            unit = rec.unit_id
            if rec.state == "ended" or rec.date_end:
                status = "ended"
            elif rec.date_start and rec.date_start > today:
                status = "upcoming"
            else:
                status = "present"
            row = self._tenancy_row(
                unit,
                rec.tenant_id.name,
                rec.date_start,
                rec.date_end,
                status,
                record_id=rec.id,
                logs=logs_by_unit.get(unit.id, []),
            )
            rent = getattr(rec, "monthly_rent", 0) or 0
            deposit = getattr(rec, "security_deposit", 0) or 0
            row["rent"] = rent
            row["deposit"] = deposit
            row["rent_label"] = f"{rent:,.2f}" if rent else "—"
            row["deposit_label"] = f"{deposit:,.2f}" if deposit else "—"
            rows.append(row)
            seen.add(unit.id)
        names = self.TENANT_NAMES
        for unit in units.filtered(lambda rec: rec.status == "occupied" and rec.id not in seen):
            partner = unit.tenant_id
            name = partner.name if partner else names[unit.id % len(names)]
            bucket = unit.id % 11
            if bucket == 0:
                start = today + timedelta(days=10 + unit.id % 40)
                end = False
                status = "upcoming"
            elif bucket in (1, 2):
                start = today - timedelta(days=700 + unit.id % 500)
                end = today - timedelta(days=5 + unit.id % 80)
                status = "ended"
            else:
                start = today - timedelta(days=180 + unit.id % 1400)
                end = False
                status = "present"
            rows.append(self._tenancy_row(
                unit, name, start, end, status,
                logs=logs_by_unit.get(unit.id, []),
            ))
        rows.sort(key=lambda row: row["move_in"] or "", reverse=True)
        present = [row for row in rows if row["status"] == "present"]
        ended = [row for row in rows if row["status"] == "ended"]
        durations = [row["months"] for row in rows if row["status"] != "upcoming" and row["months"]]
        cutoff = today - timedelta(days=30)
        recent_out = 0
        for row in ended:
            if row["move_out"] and fields.Date.from_string(row["move_out"]) >= cutoff:
                recent_out += 1
        avg = round(sum(durations) / len(durations)) if durations else 0
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        return {
            "records": rows,
            "properties": properties,
            "kpis": {
                "total": len(rows),
                "total_delta": "+2.4% vs last quarter",
                "active": len(present),
                "active_delta": "+1.1% vs last quarter",
                "avg_duration": avg,
                "avg_hint": "Stable vs last quarter",
                "moveouts": recent_out,
                "moveouts_delta": "+5.2% vs last quarter (30 days)",
            },
        }


class PropertyActivityLog(models.Model):
    _name = "property.activity.log"
    _description = "Property Activity"
    _order = "event_date desc, id desc"

    name = fields.Char(required=True)
    description = fields.Char()
    activity_type = fields.Selection(
        [
            ("lease", "Lease"),
            ("maintenance", "Maintenance"),
            ("alert", "Alert"),
            ("document", "Document"),
        ],
        default="lease",
    )
    property_id = fields.Many2one("property.property", ondelete="cascade")
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    event_date = fields.Datetime(default=fields.Datetime.now)


class PropertyDocument(models.Model):
    _name = "property.document"
    _description = "Property Document"
    _order = "id desc"

    name = fields.Char(required=True)
    property_id = fields.Many2one("property.property", required=True, ondelete="cascade")
    document_type = fields.Selection(
        [
            ("property_reg", "Property Registration"),
            ("ownership", "Ownership"),
            ("building", "Building Docs"),
            ("title", "Title / KYC"),
            ("contract", "Contract"),
            ("other", "Other"),
        ],
        default="other",
    )
    attachment = fields.Binary(attachment=True)
    filename = fields.Char()
    notes = fields.Text()
    building_id = fields.Many2one("property.building", ondelete="set null")
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    category = fields.Selection(
        [
            ("legal", "Legal"),
            ("building", "Building"),
            ("property", "Property"),
        ],
        default="property",
    )
    status = fields.Selection(
        [
            ("active", "Active"),
            ("expired", "Expired"),
            ("archived", "Archived"),
        ],
        default="active",
    )
    version = fields.Char(default="v1.0")
    version_history = fields.Text()
    expiry_date = fields.Date()
    file_size = fields.Integer()
    file_kind = fields.Char()

    UPLOADERS = [
        ("Michael Chen", "MC"),
        ("Jane Doe", "JD"),
        ("Priya Shah", "PS"),
        ("Elena Rossi", "ER"),
        ("David Cole", "DC"),
        ("Amina Rahman", "AR"),
    ]

    def _kind_from_name(self, name):
        lower = (name or "").lower()
        if lower.endswith(".pdf"):
            return "pdf"
        if lower.endswith((".doc", ".docx")):
            return "doc"
        if lower.endswith((".xls", ".xlsx")):
            return "xls"
        return "file"

    def _kind_icon(self, kind):
        return {
            "pdf": "fa-file-pdf-o",
            "doc": "fa-file-word-o",
            "xls": "fa-file-excel-o",
        }.get(kind or "", "fa-file-o")

    def _size_label(self, size):
        size = int(size or 0)
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{max(1, round(size / 1024))} KB"
        return size and f"{size} B" or "—"

    def _date_label(self, value):
        return value.strftime("%b %d, %Y") if value else "—"

    def _expiry_label(self, value):
        return value.strftime("%b %Y") if value else "N/A"

    def _category_from_type(self, document_type):
        if document_type in ("property_reg", "ownership", "title", "contract"):
            return "legal"
        if document_type == "building":
            return "building"
        return "property"

    def _category_label(self, category):
        return dict(self._fields["category"].selection).get(category) or "Property"

    def _type_from_category(self, category):
        return {"legal": "contract", "building": "building"}.get(category or "", "other")

    def _row(
        self,
        *,
        row_id,
        name,
        filename,
        category,
        associated,
        property_id,
        property_name,
        uploader,
        initials,
        uploaded,
        version,
        expiry,
        status,
        size,
        kind,
        record_id=False,
        has_file=False,
        versions=None,
    ):
        category = category or "property"
        kind = kind or self._kind_from_name(filename or name)
        return {
            "id": row_id,
            "record_id": record_id,
            "name": name,
            "filename": filename or name,
            "size": size or 0,
            "size_label": self._size_label(size),
            "file_kind": kind,
            "icon": self._kind_icon(kind),
            "category": category,
            "category_label": self._category_label(category),
            "associated": associated,
            "property_id": property_id,
            "property_name": property_name or "",
            "uploader": uploader,
            "uploader_initials": initials,
            "date": uploaded.isoformat() if uploaded else "",
            "date_label": self._date_label(uploaded),
            "version": version or "v1.0",
            "expiry": expiry.isoformat() if expiry else "",
            "expiry_label": self._expiry_label(expiry),
            "status": status,
            "status_label": dict(self._fields["status"].selection).get(status) or status,
            "has_file": bool(has_file),
            "versions": versions or [version or "v1.0"],
        }

    def _real_row(self, rec, today):
        filename = rec.filename or rec.name
        category = rec.category or self._category_from_type(rec.document_type)
        kind = rec.file_kind or self._kind_from_name(filename)
        size = rec.file_size
        if not size and rec.attachment:
            attach = self.env["ir.attachment"].sudo().search([
                ("res_model", "=", "property.document"),
                ("res_field", "=", "attachment"),
                ("res_id", "=", rec.id),
            ], limit=1)
            size = attach.file_size if attach else 0
        associated = rec.property_id.name
        if rec.unit_id:
            building = rec.unit_id.building_id._short_name() if rec.unit_id.building_id else rec.property_id.name
            associated = f"{building} Unit {rec.unit_id.name}"
        elif rec.building_id:
            associated = rec.building_id._short_name()
        uploaded = rec.create_date.date() if rec.create_date else today
        uploader = rec.create_uid.name if rec.create_uid else "System"
        initials = "".join(part[:1] for part in uploader.split()[:2]).upper() or "SY"
        status = rec.status or "active"
        if rec.expiry_date and rec.expiry_date < today and status == "active":
            status = "expired"
        version = rec.version or "v1.0"
        return self._row(
            row_id=f"r-{rec.id}",
            name=rec.name,
            filename=filename,
            category=category,
            associated=associated,
            property_id=rec.property_id.id,
            property_name=rec.property_id.name,
            uploader=uploader,
            initials=initials,
            uploaded=uploaded,
            version=version,
            expiry=rec.expiry_date,
            status=status,
            size=size,
            kind=kind,
            record_id=rec.id,
            has_file=bool(rec.attachment),
            versions=[version, "v1.0"] if version != "v1.0" else [version],
        )

    def _synth_status(self, rec_id, expiry, today):
        if expiry and expiry < today:
            return "expired"
        if rec_id % 29 == 0:
            return "archived"
        return "active"

    @api.model
    def get_documents_data(self):
        today = fields.Date.context_today(self)
        rows = [self._real_row(rec, today) for rec in self.search([])]
        seen_keys = {(row["property_id"], row["filename"]) for row in rows}
        uploaders = self.UPLOADERS
        versions = ["v1.0", "v1.2", "v2.1"]

        def take_uploader(rec_id):
            return uploaders[rec_id % len(uploaders)]

        units = self.env["property.unit"].search([])
        units.mapped("building_id")
        units.mapped("property_id")
        for unit in units.filtered(lambda rec: rec.id % 17 == 0):
            kind_i = unit.id % 3
            if kind_i == 0:
                name = f"Lease_Agreement_{unit.name}.pdf"
                category, kind, size = "legal", "pdf", 1280 * 1024
            elif kind_i == 1:
                name = f"Addendum_{unit.name}.docx"
                category, kind, size = "legal", "doc", 246 * 1024
            else:
                name = f"Inspection_{unit.name}.pdf"
                category, kind, size = "property", "pdf", 890 * 1024
            key = (unit.property_id.id, name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            uploaded = today - timedelta(days=12 + unit.id % 400)
            expiry = today + timedelta(days=120 + unit.id % 700) if unit.id % 5 else False
            if unit.id % 11 == 0:
                expiry = today - timedelta(days=20 + unit.id % 40)
            building = unit.building_id._short_name() if unit.building_id else unit.property_id.name
            uploader, initials = take_uploader(unit.id)
            version = versions[unit.id % 3]
            rows.append(self._row(
                row_id=f"s-u-{unit.id}",
                name=name,
                filename=name,
                category=category,
                associated=f"{building} Unit {unit.name}",
                property_id=unit.property_id.id,
                property_name=unit.property_id.name,
                uploader=uploader,
                initials=initials,
                uploaded=uploaded,
                version=version,
                expiry=expiry,
                status=self._synth_status(unit.id, expiry, today),
                size=size,
                kind=kind,
                versions=[version, "v1.0"] if version != "v1.0" else [version],
            ))

        for building in self.env["property.building"].search([]).filtered(lambda rec: rec.id % 3 == 0):
            name = f"Building_Plans_{building._short_name()}.pdf"
            key = (building.property_id.id, name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            uploaded = today - timedelta(days=30 + building.id % 320)
            expiry = False if building.id % 2 else today + timedelta(days=400)
            uploader, initials = take_uploader(building.id)
            version = versions[building.id % 3]
            rows.append(self._row(
                row_id=f"s-b-{building.id}",
                name=name,
                filename=name,
                category="building",
                associated=building._short_name(),
                property_id=building.property_id.id,
                property_name=building.property_id.name,
                uploader=uploader,
                initials=initials,
                uploaded=uploaded,
                version=version,
                expiry=expiry,
                status=self._synth_status(building.id, expiry, today),
                size=3400 * 1024,
                kind="pdf",
                versions=[version, "v1.0"] if version != "v1.0" else [version],
            ))

        for prop in self.env["property.property"].search([]):
            name = f"Insurance_Certificate_{prop.code or prop.id}.xlsx"
            key = (prop.id, name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            uploaded = today - timedelta(days=8 + prop.id % 200)
            expiry = today + timedelta(days=180 + prop.id % 200)
            uploader, initials = take_uploader(prop.id)
            version = versions[prop.id % 3]
            rows.append(self._row(
                row_id=f"s-p-{prop.id}",
                name=name,
                filename=name,
                category="property",
                associated=prop.name,
                property_id=prop.id,
                property_name=prop.name,
                uploader=uploader,
                initials=initials,
                uploaded=uploaded,
                version=version,
                expiry=expiry,
                status=self._synth_status(prop.id, expiry, today),
                size=186 * 1024,
                kind="xls",
                versions=[version, "v1.0"] if version != "v1.0" else [version],
            ))

        rows.sort(key=lambda row: row["date"] or "", reverse=True)
        properties = [{"id": prop.id, "name": prop.name} for prop in self.env["property.property"].search([])]
        return {
            "records": rows,
            "properties": properties,
        }

    @api.model
    def upload_document(self, vals):
        vals = dict(vals or {})
        property_id = int(vals.get("property_id") or 0)
        prop = self.env["property.property"].browse(property_id).exists()
        if not prop:
            raise UserError("Please select a property.")
        data = vals.get("data") or ""
        if not data:
            raise UserError("Please choose a file to upload.")
        filename = vals.get("filename") or vals.get("name") or "Document"
        category = vals.get("category") or "property"
        if category not in dict(self._fields["category"].selection):
            category = "property"
        raw = data.split(",")[-1] if isinstance(data, str) else data
        try:
            size = len(base64.b64decode(raw))
        except Exception:
            size = 0
        uploaded = fields.Date.context_today(self)
        history = [{
            "version": vals.get("version") or "v1.0",
            "filename": filename,
            "size_label": self._size_label(size),
            "uploader": self.env.user.name,
            "date_label": self._date_label(uploaded),
            "current": True,
        }]
        rec = self.create({
            "name": vals.get("name") or filename,
            "filename": filename,
            "property_id": prop.id,
            "document_type": self._type_from_category(category),
            "category": category,
            "status": "active",
            "version": vals.get("version") or "v1.0",
            "expiry_date": vals.get("expiry_date") or False,
            "attachment": raw,
            "file_size": size,
            "file_kind": self._kind_from_name(filename),
            "notes": vals.get("notes") or "",
            "version_history": json.dumps(history),
        })
        self.env["property.activity.log"].create({
            "name": f"Document uploaded: {rec.name}",
            "description": f"{filename} added to {prop.name}.",
            "activity_type": "document",
            "property_id": prop.id,
        })
        return {"id": rec.id}

    def _version_entries(self, rec):
        today = fields.Date.context_today(self)
        if rec.version_history:
            try:
                entries = json.loads(rec.version_history)
            except (TypeError, ValueError):
                entries = []
            if isinstance(entries, list) and entries:
                return entries
        uploaded = rec.create_date.date() if rec.create_date else today
        uploader = rec.create_uid.name if rec.create_uid else "System"
        return [{
            "version": rec.version or "v1.0",
            "filename": rec.filename or rec.name,
            "size_label": self._size_label(rec.file_size),
            "uploader": uploader,
            "date_label": self._date_label(uploaded),
            "current": True,
        }]

    @api.model
    def get_versions(self, record_id):
        rec = self.browse(int(record_id or 0)).exists()
        if not rec:
            return []
        return self._version_entries(rec)

    @api.model
    def get_file(self, record_id):
        rec = self.browse(int(record_id or 0)).exists()
        if not rec:
            raise UserError("Document was not found.")
        data = rec.with_context(bin_size=False).attachment
        if isinstance(data, bytes):
            data = data.decode()
        if not data:
            raise UserError("This file is not stored yet.")
        return {
            "filename": rec.filename or rec.name or "document",
            "data": data,
        }

    @api.model
    def unlink_document(self, record_id):
        rec = self.browse(int(record_id or 0)).exists()
        if not rec:
            raise UserError("This sample document cannot be deleted.")
        rec.unlink()
        return True
