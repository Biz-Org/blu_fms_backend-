import base64
import csv
import io
from datetime import timedelta

from odoo import api, fields, models


class OtPortal(models.AbstractModel):
    _name = "ot.portal"
    _description = "Owner Tenant Portal API"

    def _money(self, amount):
        return f"${amount:,.2f}"

    def _date(self, value, fmt="%b %d, %Y"):
        return value.strftime(fmt) if value else "—"

    def _initials(self, name):
        parts = [p for p in (name or "").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "PM"

    def _context_unit(self):
        unit = self.env["property.unit"].search([("status", "=", "occupied")], limit=1)
        return unit or self.env["property.unit"].search([], limit=1)

    def _pref(self):
        Pref = self.env["ot.preference"]
        rec = Pref.search([("user_id", "=", self.env.uid)], limit=1)
        if not rec:
            rec = Pref.create({
                "user_id": self.env.uid,
                "phone": self.env.user.partner_id.phone or "(555) 123-4567",
                "role": "Senior Property Manager",
                "office_address": "123 Corporate Blvd, Suite 400, Business City, CA 90210",
            })
        return rec

    @api.model
    def _seed_demo(self):
        if self.env["ot.lease"].search_count([]):
            return
        unit = self._context_unit()
        tenant = unit.tenant_id if unit else self.env["res.partner"].search([], limit=1)
        owner = unit.owner_id if unit else False
        if not owner and unit and unit.property_id.owner_ids:
            owner = unit.property_id.owner_ids[:1].partner_id
        if not tenant:
            tenant = self.env["res.partner"].create({"name": "Jane Doe", "email": "jane.doe@example.com", "phone": "(555) 123-4567"})
        if not owner:
            owner = self.env["res.partner"].create({"name": "Springfield Management"})
        today = fields.Date.context_today(self)
        start = today.replace(year=today.year - 1) if today.month >= 5 else today - timedelta(days=300)
        end = start + timedelta(days=365)
        lease = self.env["ot.lease"].create({
            "name": "LSE-8492",
            "unit_id": unit.id if unit else False,
            "tenant_id": tenant.id,
            "owner_id": owner.id,
            "date_start": start,
            "date_end": end,
            "rent": 2450,
            "deposit": 2450,
            "term_months": 12,
            "status": "active",
            "document_name": "Residential_Lease_Agreement_v2.pdf",
            "proposed_rent": 2650,
            "proposed_start": end + timedelta(days=1),
            "renewal_state": "awaiting",
            "renewal_note": "The new rent includes all utilities previously covered.",
        })
        self.env["ot.lease"].create([
            {"name": "LSE-23-001", "unit_id": unit.id if unit else False, "tenant_id": tenant.id, "date_start": start, "date_end": end, "rent": 2450, "status": "active", "document_name": "Lease_2023_v1.pdf"},
            {"name": "LSE-22-045", "date_start": start - timedelta(days=400), "date_end": start - timedelta(days=40), "rent": 1800, "status": "expired", "document_name": "Lease_2022_final.pdf", "tenant_id": tenant.id},
            {"name": "LSE-21-089", "date_start": start - timedelta(days=800), "date_end": start - timedelta(days=70), "rent": 4200, "status": "renewed", "document_name": "Lease_2021_renewal.pdf", "tenant_id": tenant.id},
        ])
        self.env["ot.payment"].create([
            {"name": "Monthly Rent", "unit_id": unit.id if unit else False, "tenant_id": tenant.id, "date": today - timedelta(days=22), "amount": 2500, "method": "Visa ending in 4242", "status": "paid", "description": "Monthly Rent - Unit 4B", "receipt_name": "receipt_oct.pdf"},
            {"name": "Monthly Rent", "unit_id": unit.id if unit else False, "date": today - timedelta(days=52), "amount": 2500, "method": "Bank Transfer", "status": "paid", "description": "Monthly Rent - Unit 4B"},
            {"name": "Maintenance Fee", "unit_id": unit.id if unit else False, "date": today - timedelta(days=38), "amount": 150, "method": "Visa ending in 4242", "status": "pending", "description": "Maintenance Fee - AC Repair"},
            {"name": "Monthly Rent", "unit_id": unit.id if unit else False, "date": today - timedelta(days=82), "amount": 2500, "method": "Visa ending in 1122", "status": "failed", "description": "Monthly Rent - Unit 4B"},
        ])
        self.env["ot.ledger"].create([
            {"date": today - timedelta(days=90), "line_type": "opening", "description": "Opening Balance Carried Forward", "credit": 12335, "unit_id": unit.id if unit else False},
            {"date": today - timedelta(days=22), "line_type": "rent", "description": "Monthly Rent Charge", "debit": 2400, "unit_id": unit.id if unit else False},
            {"date": today - timedelta(days=5), "line_type": "payment", "description": "Online Payment", "credit": 2400, "unit_id": unit.id if unit else False},
            {"date": today - timedelta(days=2), "line_type": "maintenance", "description": "Plumbing Repair", "debit": 150, "unit_id": unit.id if unit else False},
            {"date": today - timedelta(days=25), "line_type": "utility", "description": "Water Bill - Q3 Allocation", "debit": 85, "unit_id": unit.id if unit else False},
        ])
        maint = self.env["ot.maintenance"].create({
            "name": "Leaking Kitchen Faucet",
            "unit_id": unit.id if unit else False,
            "category": "Plumbing",
            "priority": "high",
            "state": "progress",
            "description": "Water is leaking from the base of the kitchen faucet and pooling under the sink.",
            "scheduled_date": today + timedelta(days=2),
            "vendor_name": "John Smith",
            "vendor_phone": "(555) 123-4567",
        })
        self.env["ot.maint.message"].create([
            {"request_id": maint.id, "author": "Sarah Jenkins", "body": "I've noticed a significant leak under the kitchen sink.", "mine": False},
            {"request_id": maint.id, "author": "You", "body": "I've assigned City Plumbing to this.", "mine": True},
        ])
        self.env["ot.maintenance"].create([
            {"name": "AC Repair", "category": "HVAC", "priority": "high", "state": "open", "unit_id": unit.id if unit else False},
            {"name": "Leaking Pipe", "category": "Plumbing", "priority": "medium", "state": "scheduled", "scheduled_date": today + timedelta(days=7), "unit_id": unit.id if unit else False},
            {"name": "Light Bulb Replacement", "category": "Electrical", "priority": "low", "state": "done", "unit_id": unit.id if unit else False},
        ])
        html = (
            "<h1>RESIDENTIAL LEASE AGREEMENT</h1>"
            f"<p>This Agreement is entered into between {owner.name} (Landlord) and {tenant.name} (Tenant).</p>"
            f"<p>Premises: {unit.property_id.name if unit and unit.property_id else 'Property'} Unit {unit.name if unit else '4B'}.</p>"
            f"<p>Term: {self._date(lease.date_start)} to {self._date(lease.date_end)}. Monthly rent {self._money(lease.rent)}.</p>"
        )
        self.env["ot.document"].create([
            {"name": "Signed_Lease_Agreement_Unit_4B_2024.pdf", "category": "lease", "property_label": unit.property_id.name if unit and unit.property_id else "Oakwood Estates", "status": "Verified", "uploaded_by": "Sarah Jenkins", "size_label": "1.2 MB", "tags": "Unit 4B,Lease,Active", "body_html": html, "version": "v1.2"},
            {"name": "Property Rules", "category": "property", "property_label": "Oakwood Heights", "status": "Verified", "uploaded_by": "System", "size_label": "420 KB"},
            {"name": "Parking Map", "category": "property", "status": "Verified", "uploaded_by": "System", "size_label": "210 KB"},
            {"name": "Q3_Maintenance_Report_Summary.docx", "category": "maintenance", "status": "Archived", "uploaded_by": "System", "size_label": "850 KB"},
            {"name": "Invoice_INV-2023-089_Plumbing.pdf", "category": "invoice", "status": "Paid", "uploaded_by": "Mike Plumber", "size_label": "210 KB"},
        ])
        self.env["ot.message"].create([
            {"thread": "renew-102", "subject": "Lease Renewal Inquiry - Unit 102", "author": "Sarah Jenkins", "email": "sarah.j@example.com", "body": "Hi Admin team,\n\nI noticed my current lease for Unit 102 is expiring at the end of next month. I wanted to reach out and discuss the renewal terms for the upcoming year.", "tag": "RENEWAL", "unread": True, "unit_label": "Unit 102"},
            {"thread": "maint-4b", "subject": "Maintenance - Unit 4B", "author": "City Plumbing Services", "body": "The invoice for the sink repair has been generated.", "tag": "MAINTENANCE", "unit_label": "Unit 4B"},
            {"thread": "pay-late", "subject": "Late Payment Notice Response", "author": "Marcus Chen", "body": "Apologies for the delay. The transfer was initiated this morning.", "tag": "PAYMENT"},
        ])
        self.env["ot.notification"].create([
            {"name": "Rent payment is due in 5 days.", "body": "Please ensure your payment for Unit 4B is submitted to avoid late fees.", "category": "payments"},
            {"name": "Your lease expires in 60 days.", "body": "Review your renewal options for the upcoming term.", "category": "lease"},
            {"name": "Maintenance request #MR-1024 has been scheduled.", "body": "A certified HVAC technician will arrive tomorrow between 9 AM and 12 PM.", "category": "maintenance", "is_read": True},
            {"name": "New document has been uploaded.", "body": "The updated building policy is now available.", "category": "documents", "is_read": True},
            {"name": "New message from Property Manager.", "body": "Regarding the upcoming parking lot resurfacing project.", "category": "messages", "is_read": True},
        ])

    def _lease_row(self, rec):
        unit = rec.unit_id
        tenant = rec.tenant_id
        owner = rec.owner_id
        return {
            "id": rec.id,
            "name": rec.name,
            "unit": unit.name if unit else "4B",
            "unit_id": unit.id if unit else False,
            "property": unit.property_id.name if unit and unit.property_id else "—",
            "address": unit.property_id.street if unit and unit.property_id else "",
            "tenant": tenant.name if tenant else "—",
            "tenant_email": tenant.email if tenant else "",
            "tenant_phone": tenant.phone if tenant else "",
            "tenant_initials": self._initials(tenant.name if tenant else ""),
            "owner": owner.name if owner else "—",
            "start": self._date(rec.date_start),
            "end": self._date(rec.date_end),
            "start_raw": rec.date_start.isoformat() if rec.date_start else "",
            "end_raw": rec.date_end.isoformat() if rec.date_end else "",
            "rent": rec.rent,
            "rent_label": self._money(rec.rent),
            "deposit_label": self._money(rec.deposit),
            "term": f"{rec.term_months} Months",
            "status": rec.status,
            "status_label": dict(rec._fields["status"].selection).get(rec.status),
            "notice_days": rec.notice_days,
            "auto_renew": rec.auto_renew,
            "payment_day": rec.payment_day,
            "late_fee": rec.late_fee,
            "document": rec.document_name or "",
            "proposed_rent": rec.proposed_rent,
            "proposed_rent_label": self._money(rec.proposed_rent or rec.rent),
            "proposed_start": self._date(rec.proposed_start),
            "renewal_state": rec.renewal_state,
            "renewal_note": rec.renewal_note or "",
        }

    def _running_balance(self, lines):
        ordered = lines.sorted(lambda r: (r.date or fields.Date.today(), r.id))
        bal = 0
        rows = []
        for rec in ordered:
            bal += (rec.debit or 0) - (rec.credit or 0)
            if rec.line_type == "opening":
                bal = (rec.credit or 0) - (rec.debit or 0)
            rows.append({
                "id": rec.id,
                "date": self._date(rec.date),
                "type": rec.line_type,
                "type_label": dict(rec._fields["line_type"].selection).get(rec.line_type),
                "description": rec.description or "",
                "debit": rec.debit,
                "credit": rec.credit,
                "debit_label": self._money(rec.debit) if rec.debit else "—",
                "credit_label": self._money(rec.credit) if rec.credit else "—",
                "balance": bal,
                "balance_label": self._money(bal),
            })
        rows.reverse()
        return rows, bal

    @api.model
    def get_dashboard_data(self):
        self._seed_demo()
        unit = self._context_unit()
        leases = self.env["ot.lease"].search([])
        active = leases.filtered(lambda l: l.status == "active")[:1] or leases[:1]
        lease = active
        payments = self.env["ot.payment"].search([])
        ledger = self.env["ot.ledger"].search([])
        maints = self.env["ot.maintenance"].search([])
        docs = self.env["ot.document"].search([])
        messages = self.env["ot.message"].search([])
        notes = self.env["ot.notification"].search([])
        pref = self._pref()
        ledger_rows, current_bal = self._running_balance(ledger)
        paid = payments.filtered(lambda p: p.status == "paid")[:1]
        due = payments.filtered(lambda p: p.status in ("due", "pending"))
        due_amt = sum(due.mapped("amount")) or (lease.rent if lease else 0)
        threads = {}
        for rec in messages:
            item = threads.setdefault(rec.thread, {
                "id": rec.thread,
                "subject": rec.subject,
                "author": rec.author,
                "email": rec.email or "",
                "preview": rec.body,
                "tag": rec.tag or "",
                "unread": False,
                "when": self._date(rec.date, "%b %d"),
                "unit": rec.unit_label or "",
                "messages": [],
            })
            if rec.unread:
                item["unread"] = True
            item["messages"].insert(0, {
                "id": rec.id,
                "author": rec.author,
                "body": rec.body,
                "mine": rec.mine,
                "when": rec.date.strftime("%I:%M %p") if rec.date else "",
                "attachment": rec.attachment or "",
            })
        kpis_maint = {
            "open": len(maints.filtered(lambda m: m.state == "open")),
            "progress": len(maints.filtered(lambda m: m.state == "progress")),
            "scheduled": len(maints.filtered(lambda m: m.state == "scheduled")),
            "done": len(maints.filtered(lambda m: m.state == "done")),
        }
        charges = sum(ledger.mapped("debit"))
        credits = sum(ledger.filtered(lambda l: l.line_type != "opening").mapped("credit"))
        opening = ledger.filtered(lambda l: l.line_type == "opening")[:1]
        tenant = lease.tenant_id if lease else unit.tenant_id if unit else False
        owner = lease.owner_id if lease else (unit.owner_id if unit else False)
        return {
            "user_name": self.env.user.name,
            "user_role": pref.role or "Manager",
            "profile": {
                "name": self.env.user.name,
                "email": self.env.user.email,
                "phone": pref.phone or "",
                "role": pref.role or "",
                "office": pref.office_address or "",
                "email_on": pref.email_on,
                "sms_on": pref.sms_on,
                "push_on": pref.push_on,
                "two_fa": pref.two_fa,
            },
            "unit": {
                "id": unit.id if unit else False,
                "name": unit.name if unit else "4B",
                "property": unit.property_id.name if unit and unit.property_id else "Sunset Heights",
                "address": ", ".join(p for p in [getattr(unit.property_id, "street", None) if unit and unit.property_id else None, getattr(unit.property_id, "city", None) if unit and unit.property_id else None] if p) or "123 Maple Avenue",
                "status": unit.status if unit else "occupied",
                "floor": str(unit.floor_id.floor_number) if unit and unit.floor_id else "4",
                "area": f"{int(unit.area_sqft or 1150)} sqft",
                "layout": unit.unit_type or "2B/2B",
                "owner": owner.name if owner else "Springfield Management",
            },
            "tenant": {
                "id": tenant.id if tenant else False,
                "name": tenant.name if tenant else "Jane Doe",
                "email": tenant.email if tenant else "jane.doe@example.com",
                "phone": tenant.phone if tenant else "(555) 123-4567",
                "initials": self._initials(tenant.name if tenant else "Jane Doe"),
            },
            "lease": self._lease_row(lease) if lease else {},
            "leases": [self._lease_row(r) for r in leases],
            "payments": [{
                "id": p.id,
                "date": self._date(p.date),
                "description": p.description or p.name,
                "amount": p.amount,
                "amount_label": self._money(p.amount),
                "method": p.method or "",
                "status": p.status,
                "status_label": dict(p._fields["status"].selection).get(p.status),
                "reference": p.reference or "",
                "unit": p.unit_id.name if p.unit_id else "",
                "property": p.unit_id.property_id.name if p.unit_id and p.unit_id.property_id else "",
                "receipt": p.receipt_name or "",
            } for p in payments],
            "pay_kpis": {
                "due": due_amt,
                "due_label": self._money(due_amt),
                "next_due": self._date(lease.date_end) if lease else "—",
                "balance_label": self._money(0 if not due else due_amt),
                "last_label": self._money(paid.amount) if paid else "$0.00",
                "last_date": self._date(paid.date) if paid else "—",
            },
            "ledger": ledger_rows,
            "ledger_kpis": {
                "opening_label": self._money(opening.credit if opening else 0),
                "charges_label": self._money(charges),
                "payments_label": self._money(credits),
                "current_label": self._money(current_bal),
            },
            "maints": [{
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "category": m.category or "",
                "priority": m.priority,
                "state": m.state,
                "state_label": dict(m._fields["state"].selection).get(m.state),
                "submitted": self._date(m.create_date),
                "scheduled": self._date(m.scheduled_date),
                "description": m.description or "",
                "vendor": m.vendor_name or "",
                "vendor_phone": m.vendor_phone or "",
                "unit": m.unit_id.name if m.unit_id else "",
                "messages": [{
                    "id": msg.id, "author": msg.author, "body": msg.body, "mine": msg.mine,
                    "when": msg.date.strftime("%I:%M %p") if msg.date else "",
                } for msg in m.message_ids],
            } for m in maints],
            "maint_kpis": kpis_maint,
            "docs": [{
                "id": d.id,
                "name": d.name,
                "category": d.category,
                "category_label": dict(d._fields["category"].selection).get(d.category),
                "property": d.property_label or "",
                "status": d.status or "",
                "date": self._date(d.date, "%b %d, %Y"),
                "uploaded_by": d.uploaded_by or "",
                "size": d.size_label or "—",
                "tags": [t.strip() for t in (d.tags or "").split(",") if t.strip()],
                "version": d.version or "v1.0",
                "has_file": bool(d.file_data or d.body_html),
                "html": d.body_html or "",
            } for d in docs],
            "threads": list(threads.values()),
            "unread_messages": len([t for t in threads.values() if t["unread"]]),
            "notifications": [{
                "id": n.id,
                "name": n.name,
                "body": n.body or "",
                "category": n.category,
                "read": n.is_read,
                "when": n.date.strftime("%b %d, %Y") if n.date else "",
            } for n in notes],
            "units": [{"id": u.id, "label": f"{u.property_id.name} · {u.name}" if u.property_id else u.name} for u in self.env["property.unit"].search([], limit=40)],
        }

    @api.model
    def pay_now(self):
        unit = self._context_unit()
        lease = self.env["ot.lease"].search([("status", "=", "active")], limit=1)
        amount = lease.rent if lease else 2450
        self.env["ot.payment"].create({
            "name": "Monthly Rent",
            "unit_id": unit.id if unit else False,
            "amount": amount,
            "status": "paid",
            "method": "Online Card",
            "description": f"Monthly Rent - Unit {unit.name if unit else ''}",
            "date": fields.Date.context_today(self),
        })
        self.env["ot.ledger"].create({
            "date": fields.Date.context_today(self),
            "line_type": "payment",
            "description": "Online Payment",
            "credit": amount,
            "unit_id": unit.id if unit else False,
        })
        return self.get_dashboard_data()

    @api.model
    def add_payment(self, values):
        values = values or {}
        self.env["ot.payment"].create({
            "name": values.get("name") or "Payment",
            "amount": float(values.get("amount") or 0),
            "method": values.get("method") or "Bank ACH",
            "status": values.get("status") or "paid",
            "description": values.get("description") or values.get("name") or "Payment",
            "unit_id": int(values.get("unit_id") or 0) or False,
        })
        return self.get_dashboard_data()

    @api.model
    def export_csv(self, kind):
        output = io.StringIO()
        writer = csv.writer(output)
        if kind == "ledger":
            writer.writerow(["date", "type", "description", "debit", "credit"])
            for rec in self.env["ot.ledger"].search([]):
                writer.writerow([rec.date or "", rec.line_type, rec.description or "", rec.debit, rec.credit])
            name = "ledger.csv"
        else:
            writer.writerow(["date", "reference", "description", "amount", "method", "status"])
            for rec in self.env["ot.payment"].search([]):
                writer.writerow([rec.date or "", rec.reference or "", rec.description or rec.name, rec.amount, rec.method or "", rec.status])
            name = "payments.csv"
        return {"filename": name, "csv": output.getvalue()}

    @api.model
    def renew_lease(self, lease_id, action):
        rec = self.env["ot.lease"].browse(int(lease_id or 0))
        if rec.exists():
            if action == "accept":
                rec.write({
                    "renewal_state": "accepted",
                    "rent": rec.proposed_rent or rec.rent,
                    "date_start": rec.proposed_start or rec.date_start,
                    "date_end": (rec.proposed_start or fields.Date.context_today(self)) + timedelta(days=365),
                    "status": "active",
                })
            elif action == "decline":
                rec.write({"renewal_state": "declined"})
            elif action == "start":
                rec.write({"renewal_state": "awaiting"})
        return self.get_dashboard_data()

    @api.model
    def create_lease(self, values):
        values = values or {}
        self.env["ot.lease"].create({
            "name": values.get("name") or "NEW-LEASE",
            "tenant_id": int(values.get("tenant_id") or 0) or False,
            "unit_id": int(values.get("unit_id") or 0) or False,
            "date_start": values.get("start") or False,
            "date_end": values.get("end") or False,
            "rent": float(values.get("rent") or 0),
            "status": "active",
            "document_name": values.get("document") or False,
        })
        return self.get_dashboard_data()

    @api.model
    def create_maintenance(self, values):
        values = values or {}
        rec = self.env["ot.maintenance"].create({
            "name": values.get("title") or "Maintenance Request",
            "unit_id": int(values.get("unit_id") or 0) or False,
            "category": values.get("category") or False,
            "priority": values.get("priority") or "medium",
            "description": values.get("description") or False,
            "access_date": values.get("access_date") or False,
            "access_slot": values.get("access_slot") or False,
            "notes": values.get("notes") or False,
            "attachment_name": values.get("attachment") or False,
            "file_data": values.get("file_data") or False,
            "state": "open",
        })
        self.env["ot.notification"].create({
            "name": f"Maintenance request {rec.code} created.",
            "body": rec.name,
            "category": "maintenance",
        })
        return self.get_dashboard_data()

    @api.model
    def update_maintenance(self, maint_id, state):
        rec = self.env["ot.maintenance"].browse(int(maint_id or 0))
        if rec.exists() and state:
            rec.state = state
        return self.get_dashboard_data()

    @api.model
    def send_maint_message(self, maint_id, body):
        rec = self.env["ot.maintenance"].browse(int(maint_id or 0))
        if rec.exists() and body:
            self.env["ot.maint.message"].create({"request_id": rec.id, "author": "You", "body": body, "mine": True})
        return self.get_dashboard_data()

    @api.model
    def send_message(self, thread, body, attachment=False):
        last = self.env["ot.message"].search([("thread", "=", thread)], limit=1)
        self.env["ot.message"].create({
            "thread": thread,
            "subject": last.subject if last else "New message",
            "author": "You",
            "body": body or (f"Attached {attachment}" if attachment else ""),
            "tag": last.tag if last else "GENERAL",
            "mine": True,
            "unread": False,
            "attachment": attachment or False,
            "email": self.env.user.email,
        })
        return self.get_dashboard_data()

    @api.model
    def start_thread(self, subject, body):
        key = f"new-{fields.Datetime.now().strftime('%H%M%S')}"
        self.env["ot.message"].create({
            "thread": key,
            "subject": subject or "New message",
            "author": self.env.user.name,
            "body": body or "Hello",
            "tag": "GENERAL",
            "mine": True,
        })
        return self.get_dashboard_data()

    @api.model
    def delete_thread(self, thread):
        self.env["ot.message"].search([("thread", "=", thread)]).unlink()
        return self.get_dashboard_data()

    @api.model
    def upload_document(self, values):
        values = values or {}
        self.env["ot.document"].create({
            "name": values.get("name") or "Document",
            "category": values.get("category") or "property",
            "property_label": values.get("property") or False,
            "status": "Pending Review",
            "uploaded_by": self.env.user.name,
            "size_label": values.get("size") or "—",
            "file_data": values.get("file_data") or False,
            "mimetype": values.get("mimetype") or False,
            "body_html": values.get("html") or False,
        })
        return self.get_dashboard_data()

    @api.model
    def get_document_file(self, doc_id):
        rec = self.env["ot.document"].browse(int(doc_id or 0))
        if not rec.exists():
            return False
        data = rec.file_data
        if isinstance(data, bytes):
            data = data.decode()
        return {"filename": rec.name, "mimetype": rec.mimetype or "application/pdf", "data": data or False, "html": rec.body_html or ""}

    @api.model
    def mark_notifications(self, action, note_id=False):
        if action == "all":
            self.env["ot.notification"].search([("is_read", "=", False)]).write({"is_read": True})
        elif action == "read":
            rec = self.env["ot.notification"].browse(int(note_id or 0))
            if rec.exists():
                rec.is_read = True
        elif action == "delete":
            rec = self.env["ot.notification"].browse(int(note_id or 0))
            if rec.exists():
                rec.unlink()
        return self.get_dashboard_data()

    @api.model
    def update_profile(self, values):
        values = values or {}
        pref = self._pref()
        pref.write({
            "phone": values.get("phone") or pref.phone,
            "role": values.get("role") or pref.role,
            "office_address": values.get("office") or pref.office_address,
            "email_on": bool(values.get("email_on")) if "email_on" in values else pref.email_on,
            "sms_on": bool(values.get("sms_on")) if "sms_on" in values else pref.sms_on,
            "push_on": bool(values.get("push_on")) if "push_on" in values else pref.push_on,
            "two_fa": bool(values.get("two_fa")) if "two_fa" in values else pref.two_fa,
        })
        partner = self.env.user.partner_id
        partner.write({
            "name": values.get("name") or partner.name,
            "email": values.get("email") or partner.email,
            "phone": values.get("phone") or partner.phone,
        })
        return self.get_dashboard_data()

    @api.model
    def update_unit(self, values):
        values = values or {}
        unit = self.env["property.unit"].browse(int(values.get("id") or 0))
        if unit.exists():
            unit.write({"unit_type": values.get("layout") or unit.unit_type})
        return self.get_dashboard_data()
