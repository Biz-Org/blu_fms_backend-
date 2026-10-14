from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class ApartmentPortal(models.AbstractModel):
    _name = "apartment.portal"
    _description = "Apartment Tenant Portal API"

    def _money(self, amount):
        return f"${amount:,.2f}"

    def _fmt(self, value, with_year=True):
        if not value:
            return "—"
        return value.strftime("%b %d, %Y") if with_year else value.strftime("%b %d")

    def _next_first(self, today):
        return today.replace(day=1) + relativedelta(months=1)

    def _is_manager(self):
        if self.env.user._is_internal():
            return True
        group = self.env.ref("apartment_management.group_apartment_manager", raise_if_not_found=False)
        return bool(group and group in self.env.user.groups_id)

    def _partner(self):
        return self.env.user.partner_id

    def _resolve_unit(self):
        Unit = self.env["property.unit"]
        partner = self._partner()
        unit = Unit.search([("tenant_id", "=", partner.id)], limit=1)
        if unit:
            return unit
        tenancy = self.env["property.tenancy"].search(
            [("tenant_id", "=", partner.id), ("state", "=", "active")],
            limit=1,
        )
        if tenancy:
            return tenancy.unit_id
        unit = Unit.search([("status", "=", "occupied")], limit=1) or Unit.search([], limit=1)
        if unit and self.env.user._is_internal() and not unit.tenant_id:
            unit.tenant_id = partner
        return unit

    def _active_tenancy(self, unit):
        if not unit:
            return self.env["property.tenancy"]
        return self.env["property.tenancy"].search(
            [("unit_id", "=", unit.id), ("state", "=", "active")],
            limit=1,
        )

    def _rent_for(self, unit):
        tenancy = self._active_tenancy(unit)
        if tenancy and tenancy.monthly_rent:
            return tenancy.monthly_rent
        return 1800 + (unit.id % 12) * 50 if unit else 2400

    def _ensure_tenancy_rent(self, unit, rent):
        tenancy = self._active_tenancy(unit)
        if tenancy and not tenancy.monthly_rent:
            tenancy.write({
                "monthly_rent": rent,
                "security_deposit": tenancy.security_deposit or rent * 3,
            })
        return tenancy

    @api.model
    def _seed_demo(self):
        unit = self._resolve_unit()
        if not unit:
            return
        rent = self._rent_for(unit)
        tenancy = self._ensure_tenancy_rent(unit, rent)
        Payment = self.env["apartment.payment"]
        Ticket = self.env["apartment.maintenance"]
        today = fields.Date.context_today(self)
        if not Payment.search_count([("unit_id", "=", unit.id)]):
            Payment.create({
                "name": f"Monthly Rent - Unit {unit.name}",
                "unit_id": unit.id,
                "tenancy_id": tenancy.id if tenancy else False,
                "amount": rent,
                "date": today.replace(day=1),
                "state": "paid",
                "payment_type": "rent",
                "method": "Bank ACH",
            })
            Payment.create({
                "name": f"Monthly Rent - Unit {unit.name}",
                "unit_id": unit.id,
                "tenancy_id": tenancy.id if tenancy else False,
                "amount": rent,
                "date": self._next_first(today),
                "state": "due",
                "payment_type": "rent",
                "method": "Bank ACH",
            })
        if Payment.search_count([("unit_id", "=", unit.id)]) < 8:
            extras = [
                (5, "paid", f"Monthly Rent - Unit {unit.name}", rent, "rent"),
                (4, "paid", f"Monthly Rent - Unit {unit.name}", rent, "rent"),
                (3, "failed", f"Monthly Rent - Unit {unit.name}", rent, "rent"),
                (2, "pending", "Maintenance Fee - AC Repair", 150, "maintenance"),
                (2, "paid", f"Monthly Rent - Unit {unit.name}", rent, "rent"),
                (1, "paid", f"Monthly Rent - Unit {unit.name}", rent, "rent"),
            ]
            for months_ago, state, name, amount, ptype in extras:
                date = today.replace(day=1) - relativedelta(months=months_ago)
                if not Payment.search([("unit_id", "=", unit.id), ("date", "=", date), ("name", "=", name)], limit=1):
                    Payment.create({
                        "name": name,
                        "unit_id": unit.id,
                        "tenancy_id": tenancy.id if tenancy else False,
                        "amount": amount,
                        "date": date,
                        "state": state,
                        "payment_type": ptype,
                    })
        if not Ticket.search_count([("unit_id", "=", unit.id)]):
            Ticket.create({
                "name": "AC Repair",
                "unit_id": unit.id,
                "state": "open",
                "category": "HVAC",
                "priority": "high",
            })
            Ticket.create({
                "name": "Leaking Toilet",
                "unit_id": unit.id,
                "state": "scheduled",
                "category": "Plumbing",
                "scheduled_date": today + timedelta(days=2),
            })
            Ticket.create({
                "name": "Kitchen Faucet",
                "unit_id": unit.id,
                "state": "progress",
                "category": "Plumbing",
            })
            Ticket.create({
                "name": "HVAC Filter Change",
                "unit_id": unit.id,
                "state": "scheduled",
                "category": "HVAC",
                "scheduled_date": today + timedelta(days=5),
            })
            for index in range(4):
                Ticket.create({
                    "name": f"Completed request {index + 1}",
                    "unit_id": unit.id,
                    "state": "done",
                    "category": "General",
                })
        Message = self.env["apartment.message"]
        now = fields.Datetime.now()
        if not Message.search_count([("unit_id", "=", unit.id)]):
            Message.create([
                {
                    "thread": "renewal",
                    "unit_id": unit.id,
                    "tenant_id": unit.tenant_id.id,
                    "author": unit.tenant_id.name or self.env.user.name,
                    "email": unit.tenant_id.email or self.env.user.login,
                    "subject": f"Lease Renewal Inquiry - Unit {unit.name}",
                    "tag": "RENEWAL",
                    "body": "I wanted to discuss renewal terms for the upcoming year.",
                    "date": now - timedelta(hours=2, minutes=3),
                    "unread": True,
                },
                {
                    "thread": "renewal",
                    "unit_id": unit.id,
                    "tenant_id": unit.tenant_id.id,
                    "author": "You",
                    "subject": f"Lease Renewal Inquiry - Unit {unit.name}",
                    "tag": "RENEWAL",
                    "body": "Happy to help with renewal. The addendum is attached for review.",
                    "date": now - timedelta(hours=2),
                    "mine": True,
                    "attachment": "Pet_Policy_2024.pdf",
                },
                {
                    "thread": "plumber",
                    "unit_id": unit.id,
                    "author": "City Plumbing Services",
                    "email": "billing@cityplumbing.example",
                    "subject": f"Maintenance - Unit {unit.name}",
                    "tag": "MAINTENANCE",
                    "body": "The invoice for the sink repair has been generated.",
                    "date": now - timedelta(days=1),
                    "unread": True,
                },
            ])
        Library = self.env["apartment.document"]
        if not Library.search_count([("unit_id", "=", unit.id)]):
            Library.create([
                {
                    "name": f"Signed_Lease_Agreement_Unit_{unit.name}.pdf",
                    "unit_id": unit.id,
                    "category": "lease",
                    "status": "verified",
                    "size_label": "1.2 MB",
                    "uploaded_by": "System",
                    "kind": "pdf",
                    "tags": "Lease,Active",
                },
                {
                    "name": f"Invoice_Rent_{today.strftime('%b_%Y')}.pdf",
                    "unit_id": unit.id,
                    "category": "invoice",
                    "status": "paid",
                    "size_label": "210 KB",
                    "uploaded_by": "System",
                    "kind": "pdf",
                    "tags": "Rent,Invoice",
                },
            ])
        Notice = self.env["apartment.notice"]
        if not Notice.search_count([("unit_id", "=", unit.id)]):
            Notice.create([
                {
                    "title": "Rent payment is due soon.",
                    "body": f"Please submit payment for Unit {unit.name} to avoid late fees.",
                    "category": "payments",
                    "unit_id": unit.id,
                    "tenant_id": unit.tenant_id.id,
                    "unread": True,
                },
                {
                    "title": "Your lease is approaching renewal.",
                    "body": "Review your renewal options in the lease section.",
                    "category": "lease",
                    "unit_id": unit.id,
                    "tenant_id": unit.tenant_id.id,
                    "unread": True,
                },
            ])
        Pref = self.env["apartment.preference"]
        if not Pref.search([("user_id", "=", self.env.uid)], limit=1):
            Pref.create({"user_id": self.env.uid})

    @api.model
    def get_dashboard_data(self):
        unit = self._resolve_unit()
        if unit:
            self._seed_demo()
        today = fields.Date.context_today(self)
        unit = self._resolve_unit()
        if not unit:
            return {"empty": True}
        prop = unit.property_id
        tenancy = self._active_tenancy(unit)
        start = tenancy.date_start if tenancy else today - relativedelta(months=5)
        end = tenancy.date_end if tenancy and tenancy.date_end else start + relativedelta(months=12) - timedelta(days=1)
        months = max(1, (end.year - start.year) * 12 + end.month - start.month)
        rent = self._rent_for(unit)
        payments = self.env["apartment.payment"].search([("unit_id", "=", unit.id)])
        last_paid = payments.filtered(lambda rec: rec.state == "paid")[:1]
        next_due = payments.filtered(lambda rec: rec.state == "due")[:1]
        last_amount = last_paid.amount if last_paid else rent
        next_amount = next_due.amount if next_due else rent
        next_date = next_due.date if next_due else self._next_first(today)
        last_date = last_paid.date if last_paid else today.replace(day=1)
        balance = sum(payments.filtered(lambda rec: rec.state == "due" and rec.date <= today).mapped("amount"))
        tickets = self.env["apartment.maintenance"].search([("unit_id", "=", unit.id)])
        days_to_due = (next_date - today).days if next_date else 0
        days_to_end = (end - today).days if end else 0
        alerts = []
        if days_to_due <= 7:
            alerts.append({
                "id": "rent",
                "tone": "warn",
                "icon": "fa-file-text-o",
                "title": "Rent Due",
                "note": f"Due in {max(days_to_due, 0)} days.",
            })
        if 0 <= days_to_end <= 90:
            alerts.append({
                "id": "renew",
                "tone": "info",
                "icon": "fa-refresh",
                "title": "Renewal",
                "note": "Review options.",
            })
        if not alerts:
            alerts.append({
                "id": "ok",
                "tone": "info",
                "icon": "fa-check",
                "title": "All clear",
                "note": "No urgent items.",
            })
        activity = []
        if last_paid:
            activity.append({
                "id": f"pay-{last_paid.id}",
                "tone": "ok",
                "icon": "fa-check-circle",
                "title": "Payment Received",
                "note": last_paid.date.strftime("%b %d, %Y") if last_paid.date else self._fmt(last_date),
            })
        open_ticket = tickets.filtered(lambda rec: rec.state == "open")[:1]
        if open_ticket:
            activity.append({
                "id": f"mnt-{open_ticket.id}",
                "tone": "warn",
                "icon": "fa-wrench",
                "title": "Maintenance Open",
                "note": open_ticket.name,
            })
        user = self.env.user
        tenant = unit.tenant_id or (tenancy.tenant_id if tenancy else False) or user.partner_id
        tenant_name = tenant.name if tenant else user.name
        floor = unit.floor_id
        floor_no = floor.floor_number if floor else (unit.id % 12) or 1
        layout = unit.unit_type or "2B/2B"
        area = int(unit.area_sqft or 900 + (unit.id % 8) * 50)
        type_label = dict(prop._fields["property_type"].selection).get(prop.property_type) or "Residential"
        if prop.property_type == "residential":
            type_label = "Multi-Family"
        address_parts = [prop.street or prop.location, prop.city, prop.state_name, prop.zip]
        address = ", ".join(part for part in address_parts if part) or (prop.city or "—")
        manager = prop.manager_id.name if prop.manager_id else "Property Manager"
        paid_total = sum(payments.filtered(lambda rec: rec.state == "paid").mapped("amount"))
        deposit = tenancy.security_deposit if tenancy and tenancy.security_deposit else rent * 3
        real_docs = [{
            "id": f"d-{doc.id}",
            "record_id": doc.id,
            "name": doc.name,
            "size_label": doc.size_label or "—",
            "has_file": bool(doc.file),
        } for doc in self.env["apartment.document"].search([("unit_id", "=", unit.id)], limit=6)]
        if not real_docs:
            real_docs = [
                {"id": "rules", "record_id": False, "name": "Property Rules", "size_label": "", "has_file": False},
            ]
        lease_docs = [
            {"id": "lease-pdf", "name": "Signed Lease Agreement", "meta": "PDF", "ok": True},
            {"id": "insure", "name": "Property Insurance", "meta": "PDF", "ok": True},
            {"id": "tenant-id", "name": "Tenant ID", "meta": "Verified", "ok": True},
        ]
        open_issues = [{
            "id": ticket.id,
            "name": ticket.name,
            "state": ticket.state,
            "note": ticket.description or ticket.name,
        } for ticket in tickets.filtered(lambda rec: rec.state in ("open", "progress"))[:3]]
        image_url = (
            f"/web/image/property.property/{prop.id}/image_128"
            if prop.image_128
            else "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1400&q=80"
        )
        phone = tenant.phone or tenant.mobile or ""
        email = tenant.email or user.login or ""
        initials = "".join(part[:1] for part in tenant_name.split()[:2]).upper() or "TD"
        return {
            "empty": False,
            "user_name": user.name,
            "user_role": "Manager" if self._is_manager() else "Tenant",
            "property_name": prop.name,
            "unit_name": f"Apt {unit.name}",
            "unit_short": unit.name,
            "lease_status": "Active" if (not tenancy or tenancy.state == "active") else "Ended",
            "lease_standing": "In Good Standing" if balance <= 0 else "Balance due",
            "balance": balance,
            "balance_label": self._money(balance),
            "balance_hint": "Paid in full" if balance <= 0 else "Outstanding",
            "next_due_label": next_date.strftime("%b %d, %Y") if next_date else "—",
            "next_due_short": next_date.strftime("%b %d") if next_date else "—",
            "next_amount_label": self._money(next_amount),
            "last_amount_label": self._money(last_amount),
            "last_date_label": self._fmt(last_date, with_year=False),
            "last_date_full": self._fmt(last_date),
            "lease_start": self._fmt(start),
            "lease_end": self._fmt(end),
            "monthly_rent": self._money(rent),
            "lease_term": f"{months} Months",
            "eligible": True,
            "maintenance": {
                "open": len(tickets.filtered(lambda rec: rec.state == "open")),
                "progress": len(tickets.filtered(lambda rec: rec.state == "progress")),
                "scheduled": len(tickets.filtered(lambda rec: rec.state == "scheduled")),
                "done": len(tickets.filtered(lambda rec: rec.state == "done")),
                "total": len(tickets),
            },
            "alerts": alerts,
            "activity": activity[:4],
            "unit_id": unit.id,
            "next_due_id": next_due.id if next_due else False,
            "address": address,
            "type_label": type_label,
            "occupied": unit.status == "occupied",
            "image_url": image_url,
            "manager": manager,
            "floor_label": f"{floor_no}th" if floor_no not in (1, 2, 3) else {1: "1st", 2: "2nd", 3: "3rd"}[floor_no],
            "layout": layout,
            "area_sqft": area,
            "area_label": f"{area:,} sqft",
            "amenities": ["Internet", "Laundry", "Balcony"],
            "docs": real_docs,
            "library": self._library_page(unit),
            "lease_docs": lease_docs,
            "insurance_expires": f"Expires {today.replace(month=12, day=31).strftime('%b %Y')}",
            "area_plain": f"{area:,} sq ft",
            "lease_id": f"LSE-{unit.id:04d}",
            "security_deposit": self._money(deposit),
            "move_in": self._fmt(start),
            "auto_renew": "On" if tenancy and tenancy.auto_renew else "Off",
            "paid_total_label": self._money(paid_total),
            "payment_method": (tenancy.payment_method if tenancy else False) or "ACH Auto pay",
            "tenant_name": tenant_name,
            "tenant_initials": initials,
            "tenant_role": "Primary Tenant",
            "tenant_phone": phone,
            "tenant_email": email,
            "open_issues": open_issues,
            "lease": self._lease_page(unit, prop, tenancy, tenant, tenant_name, initials, phone, email, start, end, months, rent, deposit, manager, address, layout, today, days_to_end),
            "payments": self._payment_page(unit, prop, payments, rent, today, last_date, last_amount, next_date, next_amount, balance, days_to_due),
            "ledger": self._ledger_page(unit, payments, tickets, rent, today, start),
            "maint_page": self._maint_page(unit, tickets, today),
            "units": self._unit_options(unit),
            "inbox": self._inbox_page(unit),
            "notices": self._notice_page(unit),
            "prefs": self._prefs_page(),
            "profile": self._profile_page(tenant, user, tenant_name, initials, phone, email),
        }

    def _unit_options(self, current):
        rows = []
        if self._is_manager():
            units = self.env["property.unit"].search([], limit=40, order="property_id, name")
        else:
            units = current
        if current and current not in units:
            units = current | units
        seen = set()
        for rec in units:
            if rec.id in seen or not rec.property_id:
                continue
            seen.add(rec.id)
            rows.append({
                "id": rec.id,
                "label": f"{rec.property_id.name} · Unit {rec.name}",
            })
        return rows

    def _msg_when(self, value):
        if not value:
            return ""
        now = fields.Datetime.now()
        if value.date() == now.date():
            return value.strftime("%I:%M %p").lstrip("0")
        if (now.date() - value.date()).days == 1:
            return "Yesterday"
        return value.strftime("%b %d")

    def _inbox_page(self, unit):
        domain = [("unit_id", "=", unit.id)] if unit else [("id", "=", 0)]
        if self._is_manager() and not unit:
            domain = []
        records = self.env["apartment.message"].search(domain)
        grouped = {}
        for rec in records:
            thread = grouped.setdefault(rec.thread, {
                "id": rec.thread,
                "author": rec.author,
                "email": rec.email,
                "subject": rec.subject,
                "tag": rec.tag,
                "tag_key": (rec.tag or "general").lower(),
                "unread": False,
                "preview": rec.body,
                "when": self._msg_when(rec.date),
                "messages": [],
            })
            grouped[rec.thread]["author"] = rec.author if not rec.mine else grouped[rec.thread]["author"]
            grouped[rec.thread]["email"] = rec.email or grouped[rec.thread]["email"]
            grouped[rec.thread]["subject"] = rec.subject or grouped[rec.thread]["subject"]
            grouped[rec.thread]["tag"] = rec.tag or grouped[rec.thread]["tag"]
            grouped[rec.thread]["tag_key"] = (grouped[rec.thread]["tag"] or "general").lower()
            if not grouped[rec.thread]["messages"]:
                grouped[rec.thread]["preview"] = rec.body
            grouped[rec.thread]["when"] = self._msg_when(rec.date)
            grouped[rec.thread]["sort"] = rec.date.isoformat() if rec.date else ""
            if rec.unread and not rec.mine:
                grouped[rec.thread]["unread"] = True
            initials = "".join(part[:1] for part in (rec.author or "AM").split()[:2]).upper()
            grouped[rec.thread]["messages"].append({
                "id": rec.id,
                "author": rec.author,
                "initials": initials,
                "mine": rec.mine,
                "body": rec.body,
                "when": self._msg_when(rec.date),
                "attachment": rec.attachment or "",
            })
        threads = list(grouped.values())
        threads.sort(key=lambda item: item.get("sort") or "", reverse=True)
        unread = len([item for item in threads if item["unread"]])
        return {"threads": threads, "unread": unread}

    @api.model
    def send_message(self, thread, body, attachment=False):
        text = (body or "").strip()
        file_name = (attachment or "").strip() if attachment else ""
        if (not text and not file_name) or not thread:
            return self.get_dashboard_data()
        unit = self._resolve_unit()
        last = self.env["apartment.message"].search([("thread", "=", thread)], limit=1, order="id desc")
        self.env["apartment.message"].search([("thread", "=", thread), ("unread", "=", True)]).write({"unread": False})
        self.env["apartment.message"].create({
            "thread": thread,
            "unit_id": unit.id if unit else (last.unit_id.id if last else False),
            "tenant_id": unit.tenant_id.id if unit and unit.tenant_id else False,
            "author": "You",
            "email": self.env.user.login,
            "subject": last.subject if last else "New message",
            "tag": last.tag if last else "GENERAL",
            "body": text or f"Attached {file_name}",
            "mine": True,
            "unread": False,
            "attachment": file_name or False,
        })
        return self.get_dashboard_data()

    @api.model
    def delete_thread(self, thread):
        if thread:
            domain = [("thread", "=", thread)]
            unit = self._resolve_unit()
            if unit and not self._is_manager():
                domain.append(("unit_id", "=", unit.id))
            self.env["apartment.message"].search(domain).unlink()
        return self.get_dashboard_data()

    @api.model
    def start_thread(self, subject, body):
        text = (body or "").strip() or "Hello, I have a question."
        subject = (subject or "").strip() or "New message"
        unit = self._resolve_unit()
        key = f"new-{int(datetime.now().timestamp())}"
        self.env["apartment.message"].create({
            "thread": key,
            "unit_id": unit.id if unit else False,
            "tenant_id": unit.tenant_id.id if unit and unit.tenant_id else False,
            "author": self.env.user.name,
            "email": self.env.user.login,
            "subject": subject,
            "tag": "GENERAL",
            "body": text,
            "mine": True,
        })
        return self.get_dashboard_data()

    def _library_kind(self, name, kind=None):
        lower = (name or "").lower()
        if kind:
            return kind
        if lower.endswith(".pdf"):
            return "pdf"
        if lower.endswith((".jpg", ".jpeg", ".png")):
            return "jpg"
        if lower.endswith((".doc", ".docx")):
            return "docx"
        return "file"

    def _library_page(self, unit=None):
        status_label = dict(self.env["apartment.document"]._fields["status"].selection)
        category_label = dict(self.env["apartment.document"]._fields["category"].selection)
        kind_icon = {"pdf": "fa-file-pdf-o", "jpg": "fa-file-image-o", "docx": "fa-file-word-o"}
        domain = [("unit_id", "=", unit.id)] if unit else []
        rows = []
        for rec in self.env["apartment.document"].search(domain, order="id"):
            kind = self._library_kind(rec.name, rec.kind)
            date = rec.date
            rows.append({
                "id": rec.id,
                "name": rec.name,
                "size": rec.size_label or "—",
                "uploaded_by": rec.uploaded_by or "System",
                "property": rec.property_name or (rec.property_id.name if rec.property_id else "—"),
                "category": rec.category,
                "category_label": category_label.get(rec.category) or rec.category,
                "date_month": date.strftime("%b") if date else "—",
                "date_rest": date.strftime("%d, %Y") if date else "",
                "date_label": self._fmt(date),
                "status": status_label.get(rec.status) or rec.status,
                "status_key": rec.status,
                "kind": kind,
                "icon": kind_icon.get(kind, "fa-file-o"),
                "version": rec.version or "v1.0",
                "tags": [tag.strip() for tag in (rec.tags or "").split(",") if tag.strip()],
                "pages": rec.pages or 12,
                "type_label": "Lease Agreement" if rec.category == "lease" else (category_label.get(rec.category) or "Document"),
            })
        return rows

    @api.model
    def upload_library_doc(self, name, category=False):
        file_name = (name or "Uploaded_Document.pdf").strip()
        unit = self._resolve_unit()
        self.env["apartment.document"].create({
            "name": file_name,
            "unit_id": unit.id if unit else False,
            "property_name": unit.property_id.name if unit and unit.property_id else "Portfolio",
            "category": category or "property",
            "status": "pending",
            "size_label": "—",
            "uploaded_by": self.env.user.name,
            "kind": self._library_kind(file_name),
            "version": "v1.0",
            "tags": "New",
            "pages": 1,
            "date": fields.Date.context_today(self),
        })
        return self.get_dashboard_data()

    def _notice_when(self, value):
        if not value:
            return ""
        now = fields.Datetime.now()
        delta = now - value
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            minutes = max(1, int(delta.total_seconds() // 60))
            return f"{minutes} minutes ago"
        if hours < 24:
            return f"{hours} hours ago"
        if (now.date() - value.date()).days == 1:
            return "Yesterday"
        return value.strftime("%b %d, %Y")

    def _notice_page(self, unit=None):
        icon = {
            "payments": "fa-file-text-o",
            "lease": "fa-file-o",
            "maintenance": "fa-wrench",
            "documents": "fa-cloud-upload",
            "messages": "fa-commenting-o",
        }
        domain = [("archived", "=", False)]
        if unit:
            domain += ["|", ("unit_id", "=", unit.id), ("unit_id", "=", False)]
        rows = []
        for rec in self.env["apartment.notice"].search(domain):
            rows.append({
                "id": rec.id,
                "title": rec.title,
                "body": rec.body,
                "category": rec.category,
                "when": self._notice_when(rec.date),
                "unread": rec.unread,
                "icon": icon.get(rec.category, "fa-bell-o"),
            })
        unread = len([row for row in rows if row["unread"]])
        return {"rows": rows, "unread": unread}

    def _prefs_page(self):
        pref = self.env["apartment.preference"].search([("user_id", "=", self.env.uid)], limit=1)
        if not pref:
            pref = self.env["apartment.preference"].create({"user_id": self.env.uid})
        return {
            "email_on": pref.email_on,
            "sms_on": pref.sms_on,
            "push_on": pref.push_on,
            "two_factor": pref.two_factor,
            "password_changed": pref.password_changed or "Last changed 30 days ago",
        }

    def _profile_page(self, tenant, user, tenant_name, initials, phone, email):
        partner = tenant or user.partner_id
        address_parts = [partner.street, partner.street2, partner.city, partner.state_id.name if partner.state_id else False, partner.zip]
        address = ", ".join(part for part in address_parts if part) or ""
        created = user.create_date.strftime("%b %Y") if user.create_date else ""
        return {
            "name": tenant_name,
            "email": email,
            "phone": phone,
            "role": partner.function or ("Manager" if self._is_manager() else "Tenant"),
            "address": address,
            "initials": initials,
            "member_since": created,
        }

    @api.model
    def mark_notices_read(self):
        unit = self._resolve_unit()
        domain = [("unread", "=", True)]
        if unit and not self._is_manager():
            domain += ["|", ("unit_id", "=", unit.id), ("tenant_id", "=", self._partner().id)]
        self.env["apartment.notice"].search(domain).write({"unread": False})
        return self.get_dashboard_data()

    @api.model
    def archive_notice(self, notice_id):
        rec = self.env["apartment.notice"].browse(int(notice_id or 0))
        if rec.exists():
            rec.write({"archived": True, "unread": False})
        return self.get_dashboard_data()

    @api.model
    def dismiss_notice(self, notice_id):
        rec = self.env["apartment.notice"].browse(int(notice_id or 0))
        if rec.exists():
            rec.unlink()
        return self.get_dashboard_data()

    @api.model
    def update_unit(self, values):
        values = values or {}
        unit = self._resolve_unit()
        if not unit:
            raise UserError("No unit is selected.")
        payload = {}
        name = (values.get("name") or "").strip()
        if not name:
            raise UserError("Unit name is required.")
        payload["name"] = name
        layout = (values.get("layout") or "").strip()
        if layout:
            payload["unit_type"] = layout
        area = values.get("area")
        if area not in (None, ""):
            payload["area_sqft"] = float(area)
        unit.write(payload)
        return self.get_dashboard_data()

    @api.model
    def update_profile(self, values):
        values = values or {}
        partner = self.env.user.partner_id
        payload = {}
        if values.get("name"):
            payload["name"] = values["name"]
        if "email" in values:
            payload["email"] = values.get("email") or False
        if "phone" in values:
            payload["phone"] = values.get("phone") or False
        if "role" in values:
            payload["function"] = values.get("role") or False
        if "address" in values:
            payload["street"] = values.get("address") or False
        if payload:
            partner.write(payload)
        return self.get_dashboard_data()

    @api.model
    def update_pref(self, field_name, value):
        allowed = {"email_on", "sms_on", "push_on", "two_factor"}
        if field_name not in allowed:
            return self.get_dashboard_data()
        pref = self.env["apartment.preference"].search([("user_id", "=", self.env.uid)], limit=1)
        if not pref:
            pref = self.env["apartment.preference"].create({"user_id": self.env.uid})
        pref.write({field_name: bool(value)})
        return self.get_dashboard_data()

    def _lease_history(self, unit, prop, rent):
        rows = []
        seen = set()
        domain = [("property_id", "=", prop.id)]
        if not self._is_manager() and unit:
            domain = [("unit_id", "=", unit.id)]
        for rec in self.env["property.tenancy"].search(domain, limit=16):
            start = rec.date_start
            end = rec.date_end or (start + relativedelta(months=12) - timedelta(days=1) if start else False)
            amount = rec.monthly_rent or self._rent_for(rec.unit_id)
            if rec.state == "active":
                status = "Active"
            elif rec.renewal_state == "declined":
                status = "Terminated"
            else:
                status = "Expired"
            key = (rec.tenant_id.name, start)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "id": rec.id,
                "code": f"L-{rec.id:03d}",
                "tenant": rec.tenant_id.name,
                "start": self._fmt(start, with_year=False),
                "end": self._fmt(end, with_year=False),
                "rent": self._money(amount),
                "status": status,
                "file": f"Lease_{start.year if start else 'file'}.pdf",
            })
        return rows

    def _lease_page(self, unit, prop, tenancy, tenant, tenant_name, initials, phone, email, start, end, months, rent, deposit, manager, address, layout, today, days_to_end):
        proposed_rent = round(rent * 1.06, 2)
        proposed_start = (end + timedelta(days=1)) if end else today
        proposed_end = proposed_start + relativedelta(months=12) - timedelta(days=1)
        months_left = max(0, (end.year - today.year) * 12 + end.month - today.month) if end else 0
        owner = manager
        year_managed = prop.year_built or (start.year if start else today.year)
        beds = layout or unit.unit_type or "Unit"
        renewal_state = tenancy.renewal_state if tenancy else "pending"
        code = f"NL-{start.year if start else today.year}-{unit.id:04d}"
        late_fee = tenancy.late_fee if tenancy else 50
        pages = [
            {
                "id": 1,
                "title": "RESIDENTIAL LEASE AGREEMENT",
                "lines": [
                    f"This Residential Lease Agreement is made between {owner} (“Landlord”) and {tenant_name} (“Tenant”).",
                    f"PREMISES. Landlord leases to Tenant Unit {unit.name} at {prop.name}, {address}.",
                    f"TERM. The lease begins on {self._fmt(start)} and ends on {self._fmt(end)}, unless renewed in writing.",
                    f"RENT. Tenant shall pay {self._money(rent)} on the first day of each month. A late fee of {self._money(late_fee)} applies after the fifth day of the month.",
                    f"DEPOSIT. Tenant has deposited {self._money(deposit)} as security, refundable subject to the condition of the premises at move-out.",
                    "USE. The premises shall be used only as a private residence. Tenant shall comply with building rules and applicable law.",
                ],
            },
            {
                "id": 2,
                "title": "ADDITIONAL TERMS",
                "lines": [
                    "UTILITIES. Tenant is responsible for electricity, internet, and other services billed to the unit unless listed as included.",
                    "MAINTENANCE. Tenant shall keep the unit clean and promptly report damage. Landlord shall maintain structural and building systems.",
                    "ENTRY. Landlord may enter with reasonable notice except in an emergency.",
                    "RENEWAL. Either party may propose renewal before the term ends. A signed writing is required to extend the lease.",
                    f"NOTICES. Notices may be sent to Tenant at the premises and to Landlord at {owner}.",
                    "SIGNATURES. By occupying the unit, Tenant acknowledges receipt of this agreement and building rules.",
                ],
            },
        ]
        return {
            "code": code,
            "file_name": "RESIDENTIAL_LEASE_AGREEMENT_V2.PDF",
            "doc_type": "Lease Agreement",
            "version": "V2.0 (Final)",
            "uploaded": self._fmt(start),
            "uploaded_by": tenant_name,
            "signed": True,
            "owner": owner,
            "managed_since": f"Managed Since {year_managed}",
            "unit_type": beds,
            "notice": f"{tenancy.notice_days if tenancy else 60} Days",
            "lease_type": "Fixed Term",
            "move_in_score": f"{4 + (unit.id % 2)} / 5",
            "rent_review": "Annual",
            "payment_due": "1st of Month",
            "late_fee": f"{self._money(late_fee)} after 5th",
            "months_left": months_left,
            "months_total": months,
            "days_to_end": max(days_to_end, 0),
            "show_banner": renewal_state == "pending",
            "renewal_state": renewal_state,
            "deadline_days": min(14, max(days_to_end, 1)),
            "deadline_label": (today + timedelta(days=min(14, max(days_to_end, 1)))).strftime("%b %d, %Y"),
            "proposed_rent": self._money(proposed_rent),
            "proposed_rent_change": "+6%",
            "proposed_start": self._fmt(proposed_start),
            "proposed_end": self._fmt(proposed_end),
            "history": self._lease_history(unit, prop, rent),
            "files": [
                {"id": "original", "name": "Original_Lease_Agreement.pdf", "kind": "pdf"},
                {"id": "addendum", "name": "Pet_Addendum_Signed.pdf", "kind": "pdf"},
            ],
            "pages": pages,
        }

    def _payment_page(self, unit, prop, payments, rent, today, last_date, last_amount, next_date, next_amount, balance, days_to_due):
        status_map = {"paid": "Paid", "due": "Pending", "pending": "Pending", "failed": "Failed"}
        rows = []
        for rec in payments:
            rows.append({
                "id": rec.id,
                "date": rec.date.isoformat() if rec.date else "",
                "date_label": rec.date.strftime("%b %d, %Y") if rec.date else "—",
                "description": rec.name,
                "amount": rec.amount,
                "amount_label": self._money(rec.amount),
                "method": rec.method or "Bank ACH",
                "status": status_map.get(rec.state, "Paid"),
                "reference": rec.reference or f"RTX-{rec.id:04d}",
                "property": prop.name,
                "unit": unit.name,
                "receipt": rec.state == "paid",
            })
        rows.sort(key=lambda row: row.get("date") or "", reverse=True)
        due_amount = next_amount if next_amount else balance
        if balance > 0:
            due_amount = balance
        return {
            "due_label": self._money(due_amount),
            "due_hint": "Payment required" if due_amount > 0 else "No amount due",
            "next_due_label": next_date.strftime("%b %d, %Y") if next_date else "—",
            "days_left": f"{max(days_to_due, 0)} days remaining",
            "balance_label": self._money(balance),
            "balance_hint": "All caught up" if balance <= 0 else "Outstanding",
            "last_label": self._money(last_amount),
            "last_date": self._fmt(last_date),
            "rows": rows,
        }

    def _ledger_page(self, unit, payments, tickets, rent, today, start):
        opening = 0.0
        opening_date = start or today.replace(day=1)
        events = [{
            "date": opening_date,
            "type": "Opening",
            "tone": "muted",
            "description": "Opening Balance",
            "debit": 0.0,
            "credit": 0.0,
        }]
        for rec in payments:
            if rec.state == "paid":
                events.append({
                    "date": rec.date,
                    "type": "Payment",
                    "tone": "ok",
                    "description": rec.name or f"Payment - Unit {unit.name}",
                    "debit": 0.0,
                    "credit": rec.amount,
                })
            else:
                kind = dict(rec._fields["payment_type"].selection).get(rec.payment_type) or "Rent"
                events.append({
                    "date": rec.date,
                    "type": kind,
                    "tone": "maint" if rec.payment_type == "maintenance" else "rent",
                    "description": rec.name or f"Charge - Unit {unit.name}",
                    "debit": rec.amount,
                    "credit": 0.0,
                })
        events.sort(key=lambda item: (item["date"] or today, item["type"]))
        running = opening
        charges = 0.0
        credits = 0.0
        rows = []
        for index, item in enumerate(events):
            if item["type"] != "Opening":
                running = running - item["debit"] + item["credit"]
                charges += item["debit"]
                credits += item["credit"]
            rows.append({
                "id": f"l-{index}",
                "date": item["date"].isoformat() if item["date"] else "",
                "date_label": item["date"].strftime("%b %d, %Y") if item["date"] else "—",
                "type": item["type"],
                "tone": item["tone"],
                "description": item["description"],
                "debit_label": self._money(item["debit"]) if item["debit"] else "—",
                "credit_label": self._money(item["credit"]) if item["credit"] else "—",
                "balance_label": self._money(running if item["type"] != "Opening" else opening),
                "is_debit": bool(item["debit"]),
                "is_credit": bool(item["credit"]),
            })
        rows.reverse()
        return {
            "opening_label": self._money(opening),
            "opening_as": f"As of {opening_date.strftime('%b %d, %Y')}",
            "charges_label": self._money(charges),
            "payments_label": self._money(credits),
            "current_label": self._money(running),
            "period": "This Period",
            "today_as": "As of Today",
            "rows": rows,
        }

    def _maint_page(self, unit, tickets, today):
        rows = []
        for rec in tickets:
            raw = rec.name or "Request"
            category = rec.category or "General"
            issue = raw.split(":", 1)[-1].strip() if ":" in raw else raw
            pmap = {
                "low": ("Low", "low"),
                "medium": ("Medium", "medium"),
                "high": ("High", "high"),
                "emergency": ("Emergency", "high"),
            }
            priority, ptone = pmap.get(rec.priority, ("Medium", "medium"))
            status_map = {
                "open": ("Open", "stop"),
                "progress": ("In Progress", "warn"),
                "scheduled": ("Scheduled", "info"),
                "done": ("Completed", "ok"),
            }
            status, stone = status_map.get(rec.state, ("Open", "stop"))
            submitted = rec.create_date.date() if rec.create_date else today
            scheduled = rec.scheduled_date or rec.access_date
            rows.append({
                "id": rec.id,
                "code": f"#REQ-{rec.id}",
                "issue": issue,
                "category": category,
                "priority": priority,
                "ptone": ptone,
                "submitted": submitted.strftime("%b %d, %Y"),
                "status": status,
                "stone": stone,
                "scheduled": scheduled.strftime("%b %d, %Y") if scheduled else "—",
            })
        open_n = len(tickets.filtered(lambda rec: rec.state == "open"))
        progress_n = len(tickets.filtered(lambda rec: rec.state == "progress"))
        scheduled_n = len(tickets.filtered(lambda rec: rec.state == "scheduled"))
        done_n = len(tickets.filtered(lambda rec: rec.state == "done"))
        return {
            "open": open_n,
            "open_hint": f"+{min(open_n, 2)} this week",
            "progress": progress_n,
            "scheduled": scheduled_n,
            "done": done_n,
            "done_hint": f"+{min(done_n, 5)} this month",
            "rows": rows,
        }

    @api.model
    def create_maintenance_request(self, issue, category=None):
        vals = issue if isinstance(issue, dict) else {"title": issue, "category": category}
        unit = self._resolve_unit()
        if not unit:
            return self.get_dashboard_data()
        title = (vals.get("title") or vals.get("issue") or "").strip() or "New maintenance request"
        category = (vals.get("category") or "").strip()
        name = f"{category}: {title}" if category else title
        chosen = self.env["property.unit"].browse(int(vals.get("unit_id") or 0)).exists() or unit
        if not self._is_manager() and chosen != unit:
            chosen = unit
        create_vals = {
            "name": name,
            "unit_id": chosen.id,
            "state": "open",
            "category": category or False,
            "description": vals.get("description") or False,
            "priority": vals.get("priority") or "medium",
            "access_slot": vals.get("access_slot") or False,
            "notes": vals.get("notes") or False,
        }
        access_date = vals.get("access_date")
        if access_date:
            create_vals["access_date"] = access_date
        ticket = self.env["apartment.maintenance"].create(create_vals)
        self.env["apartment.notice"].create({
            "title": f"Maintenance request #{ticket.id} submitted.",
            "body": title,
            "category": "maintenance",
            "unit_id": chosen.id,
            "tenant_id": chosen.tenant_id.id if chosen.tenant_id else False,
        })
        return self.get_dashboard_data()

    @api.model
    def add_payment_record(self):
        unit = self._resolve_unit()
        if not unit:
            return self.get_dashboard_data()
        today = fields.Date.context_today(self)
        tenancy = self._active_tenancy(unit)
        self.env["apartment.payment"].create({
            "name": f"Manual payment - Unit {unit.name}",
            "unit_id": unit.id,
            "tenancy_id": tenancy.id if tenancy else False,
            "amount": self._rent_for(unit),
            "date": today,
            "state": "pending",
            "payment_type": "rent",
        })
        return self.get_dashboard_data()

    @api.model
    def set_lease_renewal(self, decision):
        unit = self._resolve_unit()
        if not unit or decision not in ("accepted", "declined"):
            return self.get_dashboard_data()
        tenancy = self._active_tenancy(unit)
        if tenancy:
            tenancy.renewal_state = decision
            if decision == "accepted" and tenancy.date_end:
                tenancy.date_end = tenancy.date_end + relativedelta(months=12)
                if tenancy.monthly_rent:
                    tenancy.monthly_rent = round(tenancy.monthly_rent * 1.06, 2)
        self.env["apartment.notice"].create({
            "title": "Lease renewal " + ("accepted." if decision == "accepted" else "declined."),
            "body": f"Unit {unit.name} renewal was {decision}.",
            "category": "lease",
            "unit_id": unit.id,
            "tenant_id": unit.tenant_id.id if unit.tenant_id else False,
        })
        return self.get_dashboard_data()

    @api.model
    def pay_next_rent(self):
        unit = self._resolve_unit()
        today = fields.Date.context_today(self)
        payment = self.env["apartment.payment"].search([
            ("unit_id", "=", unit.id if unit else 0),
            ("state", "=", "due"),
        ], limit=1)
        if payment:
            payment.write({"state": "paid", "date": today})
        if unit:
            tenancy = self._active_tenancy(unit)
            self.env["apartment.payment"].create({
                "name": f"Monthly Rent - Unit {unit.name}",
                "unit_id": unit.id,
                "tenancy_id": tenancy.id if tenancy else False,
                "amount": self._rent_for(unit),
                "date": self._next_first(today),
                "state": "due",
                "payment_type": "rent",
            })
            self.env["apartment.notice"].create({
                "title": "Rent payment received.",
                "body": f"Payment for Unit {unit.name} was recorded.",
                "category": "payments",
                "unit_id": unit.id,
                "tenant_id": unit.tenant_id.id if unit.tenant_id else False,
                "unread": False,
            })
        return self.get_dashboard_data()
