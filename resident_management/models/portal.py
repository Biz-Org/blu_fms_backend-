import base64
import csv
import io
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

MOVE_IN_ITEMS = [
    ("Resident verification", "System verified"),
    ("KYC completed", "Documents approved"),
    ("Agreement completed", "Signed electronically"),
    ("Unit assigned", "Unit confirmed"),
    ("Keys prepared", "Ready at front desk"),
    ("Access card issued", "Card programmed"),
    ("Parking assigned", "Awaiting vehicle details"),
    ("Move-in inspection completed", "Required prior to handover"),
]
MOVE_OUT_ITEMS = [
    ("Notice verified", ""),
    ("Outstanding balance checked", ""),
    ("Maintenance inspection", ""),
    ("Property inspection", ""),
    ("Keys returned", ""),
    ("Access card returned", ""),
    ("Final meter reading", ""),
    ("Unit handover", ""),
    ("Documents completed", ""),
    ("Resident status updated", ""),
]


class ResidentPortal(models.AbstractModel):
    _name = "resident.portal"
    _description = "Resident Management Portal API"

    def _initials(self, name):
        parts = [p for p in (name or "").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "R"

    def _unit_label(self, unit):
        if not unit:
            return "—"
        return unit.name

    def _building_label(self, rec):
        if rec.building_id:
            return rec.building_id.name
        if rec.unit_id and rec.unit_id.building_id:
            return rec.unit_id.building_id.name
        if rec.property_id:
            return rec.property_id.name
        return "—"

    @api.model
    def _seed_demo(self):
        leftovers = self.env["resident.resident"].search(["|", ("first_name", "=", False), ("first_name", "=", "")])
        if leftovers:
            leftovers.unlink()
        if self.env["resident.resident"].search_count([]):
            return
        Unit = self.env["property.unit"]
        units = Unit.search([], limit=12, order="id")
        today = fields.Date.context_today(self)
        people = [
            ("Sarah", "Jenkins", "active", "verified", "submitted", "Apt 4B", "sarah.j@example.com", "(555) 123-4567"),
            ("Marcus", "Rodriguez", "pending", "review", "docs", "Suite 12C", "m.rodriguez@email.net", "(555) 987-6543"),
            ("Emily", "Chen", "notice", "verified", "approved", "Apt 2A", "emily.chen@work.org", "(555) 333-2222"),
            ("David", "Johnson", "moved_out", "none", "approved", "Apt 7G", "david.j@mail.com", "(555) 444-5555"),
            ("Michael", "Chang", "verification", "pending", "docs", "12A", "m.chang@example.com", "(555) 123-4567"),
            ("Robert", "Taylor", "notice", "review", "kyc", "809", "robert.t@mail.com", "(555) 111-2222"),
            ("John", "Doe", "active", "verified", "approved", "A-101", "john.doe@example.com", "(555) 019-2834"),
            ("Elena", "Rodriguez", "active", "verified", "approved", "Apt 4B", "elena@mail.com", "(555) 012-3456"),
        ]
        records = []
        for index, (first, last, status, kyc, stage, unit_name, email, phone) in enumerate(people):
            unit = units[index] if index < len(units) else False
            rec = self.env["resident.resident"].create({
                "first_name": first,
                "last_name": last,
                "email": email,
                "mobile": phone,
                "unit_id": unit.id if unit else False,
                "building_id": unit.building_id.id if unit and unit.building_id else False,
                "floor_id": unit.floor_id.id if unit and unit.floor_id else False,
                "status": status,
                "kyc_state": kyc,
                "onboarding_stage": stage,
                "onboarding_progress": 15 if stage == "submitted" else 40 if stage == "docs" else 80,
                "move_in_date": today - timedelta(days=30 + index * 40),
                "id_type": "Passport",
                "id_number": f"A{100000 + index}",
                "gender": "female" if first in ("Sarah", "Emily", "Elena") else "male",
                "dob": fields.Date.from_string("1985-04-12"),
                "resident_type": "Primary Tenant",
                "lease_term": "12 Months",
                "city": "Chicago",
                "state_name": "Illinois",
                "country": "United States",
                "street": "1440 Lakeshore Drive",
                "status_since": today - timedelta(days=index + 3),
                "status_reason": "Standard Lease",
            })
            records.append(rec)
            self.env["resident.emergency.contact"].create({
                "resident_id": rec.id,
                "name": "Jane Doe" if first != "Jane" else "John Doe",
                "relation": "Spouse",
                "phone": "(555) 987-6543",
                "email": "jane.doe@example.com",
                "priority": "primary",
            })
            if first in ("John", "Sarah"):
                self.env["resident.household.member"].create([
                    {"resident_id": rec.id, "name": "Jane Doe", "relation": "Spouse", "email": "jane.doe@example.com", "phone": "(555) 019-2835", "member_status": "active", "kyc_state": "Verified", "dob": fields.Date.from_string("1982-01-10")},
                    {"resident_id": rec.id, "name": "Jimmy Doe", "relation": "Child", "member_status": "dependent", "kyc_state": "N/A (Minor)", "dob": fields.Date.from_string("2012-06-01")},
                ])
            kyc_status = {"verified": "verified", "pending": "pending", "review": "review", "none": "pending"}.get(kyc, "pending")
            self.env["resident.kyc.document"].create({
                "name": "Passport (ID)",
                "resident_id": rec.id,
                "document_type": "Passport",
                "document_number": rec.id_number,
                "file_name": f"Passport_Scan_{first}.pdf",
                "file_size": "2.4 MB",
                "status": kyc_status,
                "reviewer": "Admin User" if kyc_status != "pending" else "Unassigned",
                "submitted": today - timedelta(days=index + 1),
            })
            if status in ("pending", "verification", "active"):
                move = self.env["resident.move.request"].create({
                    "name": f"Move-In {rec.name}",
                    "move_type": "in",
                    "resident_id": rec.id,
                    "unit_id": rec.unit_id.id,
                    "planned_date": today + timedelta(days=index),
                    "state": "scheduled" if status == "active" else "pending",
                    "approved": status == "active",
                    "agent": "Sarah Jenkins",
                })
                for seq, (title, note) in enumerate(MOVE_IN_ITEMS):
                    self.env["resident.checklist.item"].create({
                        "request_id": move.id,
                        "name": title,
                        "note": note,
                        "sequence": seq * 10,
                        "done": seq < (6 if status == "active" else 2),
                    })
            if status in ("notice", "moved_out"):
                move = self.env["resident.move.request"].create({
                    "name": f"Move-Out {rec.name}",
                    "move_type": "out",
                    "resident_id": rec.id,
                    "unit_id": rec.unit_id.id,
                    "planned_date": today + timedelta(days=7),
                    "notice_date": today - timedelta(days=20),
                    "request_date": today - timedelta(days=5),
                    "final_date": today + timedelta(days=10),
                    "state": "progress",
                    "agent": "Leasing Coordinator",
                })
                for seq, (title, note) in enumerate(MOVE_OUT_ITEMS):
                    self.env["resident.checklist.item"].create({
                        "request_id": move.id,
                        "name": title,
                        "note": note,
                        "sequence": seq * 10,
                        "done": seq < 4,
                    })
        if records:
            comm = self.env["resident.communication"].create({
                "name": "Q3 Maintenance Schedule Update",
                "body": "Dear Residents,\n\nPlease be advised that our quarterly preventative maintenance for Building A will commence next week.",
                "audience": "Building A Residents",
                "channel_email": True,
                "channel_push": True,
                "sent_by": "Sarah Jenkins",
                "state": "delivered",
                "attachment_name": "Maintenance_Notice_Q3.pdf",
            })
            for rec in records[:4]:
                self.env["resident.comm.recipient"].create({
                    "comm_id": comm.id,
                    "resident_id": rec.id,
                    "delivery": "delivered" if rec.id % 3 else "failed",
                    "read": rec.id % 2 == 0,
                })
            self.env["resident.communication"].create({
                "name": "Upcoming Holiday Office Hours",
                "body": "Office hours will change for the holiday.",
                "audience": "All Residents",
                "channel_sms": True,
                "sent_by": "Sarah Jenkins",
                "state": "scheduled",
            })

    def _resident_row(self, rec):
        unit = rec.unit_id
        return {
            "id": rec.id,
            "name": rec.name,
            "first_name": rec.first_name,
            "last_name": rec.last_name,
            "preferred_name": rec.preferred_name or rec.first_name,
            "code": rec.code,
            "initials": self._initials(rec.name),
            "email": rec.email or "",
            "mobile": rec.mobile or "",
            "alt_phone": rec.alt_phone or "",
            "unit": self._unit_label(unit),
            "unit_id": unit.id if unit else False,
            "building": self._building_label(rec),
            "building_id": rec.building_id.id if rec.building_id else False,
            "floor": rec.floor_id.name if rec.floor_id else "",
            "property": rec.property_id.name if rec.property_id else "",
            "status": rec.status,
            "status_label": dict(rec._fields["status"].selection).get(rec.status),
            "kyc_state": rec.kyc_state,
            "kyc_label": dict(rec._fields["kyc_state"].selection).get(rec.kyc_state) or rec.kyc_state,
            "household": len(rec.household_ids),
            "dependents": len(rec.household_ids.filtered(lambda m: m.member_status == "dependent")),
            "move_in": rec.move_in_date.strftime("%b %d, %Y") if rec.move_in_date else "—",
            "move_in_raw": rec.move_in_date.isoformat() if rec.move_in_date else "",
            "dob": rec.dob.isoformat() if rec.dob else "",
            "dob_label": rec.dob.strftime("%Y-%m-%d") if rec.dob else "",
            "gender": rec.gender or "",
            "resident_type": rec.resident_type or "Primary Tenant",
            "lease_term": rec.lease_term or "12 Months",
            "id_type": rec.id_type or "",
            "id_number": rec.id_number or "",
            "onboarding_stage": rec.onboarding_stage,
            "progress": rec.onboarding_progress or 0,
            "street": rec.street or "",
            "city": rec.city or "",
            "state_name": rec.state_name or "",
            "zip": rec.zip or "",
            "country": rec.country or "",
            "nationality": rec.nationality or "United States",
            "marital_status": rec.marital_status or "",
            "status_since": rec.status_since.strftime("%b %d, %Y") if rec.status_since else "",
            "status_reason": rec.status_reason or "",
            "emergency": [{
                "id": em.id, "name": em.name, "relation": em.relation, "phone": em.phone,
                "email": em.email, "priority": em.priority,
            } for em in rec.emergency_ids],
            "members": [self._member_row(m) for m in rec.household_ids],
        }

    def _member_row(self, rec):
        age = ""
        if rec.dob:
            today = fields.Date.context_today(self)
            age = today.year - rec.dob.year - ((today.month, today.day) < (rec.dob.month, rec.dob.day))
        return {
            "id": rec.id,
            "resident_id": rec.resident_id.id,
            "resident": rec.resident_id.name,
            "name": rec.name,
            "relation": rec.relation or "",
            "age": age,
            "email": rec.email or "",
            "phone": rec.phone or "",
            "unit": self._unit_label(rec.resident_id.unit_id),
            "status": rec.member_status,
            "kyc_state": rec.kyc_state or "",
            "initials": self._initials(rec.name),
        }

    def _kyc_row(self, rec):
        return {
            "id": rec.id,
            "resident_id": rec.resident_id.id,
            "resident": rec.resident_id.name,
            "initials": self._initials(rec.resident_id.name),
            "name": rec.name,
            "type": rec.document_type or rec.name,
            "number": rec.document_number or "",
            "file_name": rec.file_name or rec.name,
            "file_size": rec.file_size or "—",
            "has_file": bool(rec.file_data),
            "mimetype": rec.mimetype or "",
            "status": rec.status,
            "status_label": dict(rec._fields["status"].selection).get(rec.status),
            "expiry": rec.expiry_date.strftime("%b %d, %Y") if rec.expiry_date else "—",
            "reviewer": rec.reviewer or "Unassigned",
            "submitted": rec.submitted.strftime("%b %d, %Y") if rec.submitted else "",
            "code": f"KYC-{rec.id:04d}",
            "phone": rec.resident_id.mobile or "",
            "unit": self._unit_label(rec.resident_id.unit_id),
            "resident_code": rec.resident_id.code,
            "identity_match": rec.identity_match,
            "document_readable": rec.document_readable,
            "document_valid": rec.document_valid,
            "not_expired": rec.not_expired,
            "information_match": rec.information_match,
            "reject_reason": rec.reject_reason or "",
        }

    def _move_row(self, rec):
        items = [{"id": i.id, "name": i.name, "note": i.note or "", "done": i.done} for i in rec.checklist_ids]
        done = len([i for i in items if i["done"]])
        return {
            "id": rec.id,
            "name": rec.name,
            "move_type": rec.move_type,
            "resident_id": rec.resident_id.id,
            "resident": rec.resident_id.name,
            "initials": self._initials(rec.resident_id.name),
            "unit": self._unit_label(rec.unit_id or rec.resident_id.unit_id),
            "date": rec.planned_date.strftime("%b %d, %Y") if rec.planned_date else "—",
            "request_date": rec.request_date.strftime("%b %d, %Y") if rec.request_date else "",
            "notice_date": rec.notice_date.strftime("%b %d, %Y") if rec.notice_date else "",
            "final_date": rec.final_date.strftime("%b %d, %Y") if rec.final_date else "",
            "approved": rec.approved,
            "checklist": f"{done}/{len(items) or 1}",
            "done_n": done,
            "total_n": len(items) or 1,
            "state": rec.state,
            "state_label": dict(rec._fields["state"].selection).get(rec.state),
            "readiness": rec.readiness_score,
            "agent": rec.agent or "Sarah Jenkins",
            "items": items,
            "clearance_name": rec.clearance_name or "",
            "has_clearance": bool(rec.clearance_file),
        }

    def _comm_row(self, rec):
        recips = rec.recipient_ids
        delivered = len(recips.filtered(lambda r: r.delivery == "delivered"))
        failed = len(recips.filtered(lambda r: r.delivery == "failed"))
        read_n = len(recips.filtered("read"))
        total = len(recips) or 1
        channels = []
        if rec.channel_email:
            channels.append("email")
        if rec.channel_push:
            channels.append("push")
        if rec.channel_sms:
            channels.append("sms")
        return {
            "id": rec.id,
            "name": rec.name,
            "body": rec.body or "",
            "audience": rec.audience or "All Residents",
            "channels": channels,
            "sent_by": rec.sent_by or self.env.user.name,
            "date": rec.date.strftime("%b %d, %H:%M") if rec.date else "",
            "state": rec.state,
            "state_label": dict(rec._fields["state"].selection).get(rec.state),
            "attachment": rec.attachment_name or "",
            "total": len(recips),
            "delivered": delivered,
            "failed": failed,
            "read_pct": int(100 * read_n / total),
            "read_n": read_n,
            "recipients": [{
                "id": r.id,
                "resident": r.resident_id.name,
                "initials": self._initials(r.resident_id.name),
                "unit": self._unit_label(r.resident_id.unit_id),
                "delivery": r.delivery,
                "read": r.read,
                "when": r.timestamp.strftime("%b %d, %H:%M") if r.timestamp else "",
            } for r in recips],
        }

    def _history_row(self, rec):
        return {
            "id": rec.id,
            "resident_id": rec.resident_id.id,
            "resident": rec.resident_id.name,
            "code": rec.resident_id.code,
            "unit": self._unit_label(rec.resident_id.unit_id),
            "status": rec.resident_id.status,
            "activity_type": rec.activity_type or "status",
            "title": rec.title,
            "body": rec.body or "",
            "date": rec.date.strftime("%b %d") if rec.date else "",
            "time": rec.date.strftime("%I:%M %p") if rec.date else "",
            "datetime": rec.date.strftime("%b %d, %Y · %I:%M %p") if rec.date else "",
            "iso": rec.date.isoformat() if rec.date else "",
            "old_status": rec.old_status or "",
            "new_status": rec.new_status or "",
            "performed_by": rec.performed_by or "",
            "reason": rec.reason or "",
            "notes": rec.notes or "",
            "category": rec.category or "Lifecycle Management",
            "hist_code": rec.code or f"RH-{rec.id:04d}",
        }

    @api.model
    def get_dashboard_data(self):
        self._seed_demo()
        residents = self.env["resident.resident"].search([])
        kycs = self.env["resident.kyc.document"].search([])
        members = self.env["resident.household.member"].search([])
        emergencies = self.env["resident.emergency.contact"].search([])
        moves = self.env["resident.move.request"].search([])
        comms = self.env["resident.communication"].search([])
        history = self.env["resident.status.history"].search([], limit=40)
        today = fields.Date.context_today(self)
        total = len(residents)
        active = len(residents.filtered(lambda r: r.status == "active"))
        pending_on = len(residents.filtered(lambda r: r.status in ("pending", "verification")))
        pending_kyc = len(kycs.filtered(lambda d: d.status in ("pending", "review")))
        move_in_soon = len(moves.filtered(lambda m: m.move_type == "in" and m.state != "done"))
        move_out_soon = len(moves.filtered(lambda m: m.move_type == "out" and m.state != "done"))
        units = self.env["property.unit"].search([], limit=40)
        buildings = self.env["property.building"].search([], limit=40)
        pipeline = {
            "onboarding": len(residents.filtered(lambda r: r.status in ("pending", "verification"))),
            "kyc": pending_kyc,
            "approved": len(residents.filtered(lambda r: r.onboarding_stage == "approved")),
            "move_in": move_in_soon,
            "active": active,
            "notice": len(residents.filtered(lambda r: r.status == "notice")),
            "move_out": move_out_soon,
        }
        activity = []
        for rec in residents[:6]:
            activity.append({
                "id": rec.id,
                "resident": rec.name,
                "initials": self._initials(rec.name),
                "unit": self._unit_label(rec.unit_id),
                "activity": "KYC Submitted" if rec.kyc_state == "pending" else "Move-In Approved" if rec.status == "active" else "Status Updated",
                "date": "Today" if rec.id % 3 == 0 else "Yesterday",
                "status": rec.status,
                "status_label": dict(rec._fields["status"].selection).get(rec.status),
            })
        return {
            "user_name": self.env.user.name,
            "user_role": "Manager",
            "kpis": {
                "total": total,
                "active": active,
                "occupancy": int(100 * active / total) if total else 0,
                "pending_onboarding": pending_on,
                "pending_kyc": pending_kyc,
                "move_ins": move_in_soon,
                "move_outs": move_out_soon,
            },
            "pipeline": pipeline,
            "pending": {
                "kyc": pending_kyc,
                "onboarding": pending_on,
                "move_in": len(moves.filtered(lambda m: m.move_type == "in" and m.state == "pending")),
                "move_out": len(moves.filtered(lambda m: m.move_type == "out" and m.state in ("pending", "progress"))),
            },
            "activity": activity,
            "residents": [self._resident_row(r) for r in residents],
            "kycs": [self._kyc_row(d) for d in kycs],
            "members": [self._member_row(m) for m in members],
            "emergencies": [{
                "id": e.id,
                "resident_id": e.resident_id.id,
                "resident": e.resident_id.name,
                "unit": self._unit_label(e.resident_id.unit_id),
                "name": e.name,
                "relation": e.relation or "",
                "phone": e.phone or "",
                "priority": e.priority,
                "updated": e.create_date.strftime("%b %d, %Y") if e.create_date else "",
            } for e in emergencies],
            "moves": [self._move_row(m) for m in moves],
            "comms": [self._comm_row(c) for c in comms],
            "history": [self._history_row(h) for h in history],
            "units": [{"id": u.id, "label": f"{u.property_id.name} · {u.name}" if u.property_id else u.name} for u in units],
            "buildings": [{"id": b.id, "label": b.name} for b in buildings],
            "kyc_stats": {
                "total": len(kycs),
                "pending": len(kycs.filtered(lambda d: d.status in ("pending", "review"))),
                "verified": len(kycs.filtered(lambda d: d.status == "verified")),
                "rejected": len(kycs.filtered(lambda d: d.status == "rejected")),
                "expiring": len(kycs.filtered(lambda d: d.status == "expiring")),
            },
            "onboard_stats": {
                "new": len(residents.filtered(lambda r: r.onboarding_stage == "submitted")),
                "progress": len(residents.filtered(lambda r: r.onboarding_stage in ("docs", "kyc", "review"))),
                "docs": len(residents.filtered(lambda r: r.onboarding_stage == "docs")),
                "kyc": len(residents.filtered(lambda r: r.onboarding_stage == "kyc")),
                "approved": len(residents.filtered(lambda r: r.onboarding_stage == "approved")),
                "rejected": len(residents.filtered(lambda r: r.onboarding_stage == "rejected")),
            },
            "household_stats": {
                "households": len(residents),
                "avg": round((len(members) / len(residents)), 1) if residents else 0,
                "members": len(members) + len(residents),
                "dependents": len(members.filtered(lambda m: m.member_status == "dependent")),
            },
            "emergency_stats": {
                "total": len(emergencies),
                "with_contact": len(residents.filtered("emergency_ids")),
                "missing": len(residents.filtered(lambda r: not r.emergency_ids)),
                "recent": min(len(emergencies), 28),
            },
            "comm_stats": self._comm_stats(comms),
            "status_stats": {
                "active": len(residents.filtered(lambda r: r.status == "active")),
                "pending": len(residents.filtered(lambda r: r.status == "pending")),
                "verification": len(residents.filtered(lambda r: r.status == "verification")),
                "notice": len(residents.filtered(lambda r: r.status == "notice")),
                "inactive": len(residents.filtered(lambda r: r.status == "inactive")),
                "moved_out": len(residents.filtered(lambda r: r.status == "moved_out")),
                "suspended": len(residents.filtered(lambda r: r.status == "suspended")),
            },
        }

    def _comm_stats(self, comms):
        recips = comms.mapped("recipient_ids")
        total = len(recips)
        read_n = len(recips.filtered("read"))
        sent = len(comms.filtered(lambda c: c.state in ("delivered", "partial", "failed")))
        return {
            "sent": sent,
            "scheduled": len(comms.filtered(lambda c: c.state in ("scheduled", "draft"))),
            "delivered": len(comms.filtered(lambda c: c.state == "delivered")),
            "read": int(100 * read_n / total) if total else 0,
            "failed": len(comms.filtered(lambda c: c.state in ("failed", "partial"))),
        }

    def _unit_from_values(self, values):
        return self.env["property.unit"].browse(int(values.get("unit_id") or 0)).exists()

    def _resident_vals(self, values, create=False):
        values = values or {}
        unit = self._unit_from_values(values)
        building_id = unit.building_id.id if unit and unit.building_id else (int(values.get("building_id") or 0) or False)
        vals = {
            "first_name": values.get("first_name") or "New",
            "last_name": values.get("last_name") or "Resident",
            "preferred_name": values.get("preferred_name") or False,
            "dob": values.get("dob") or False,
            "gender": values.get("gender") or False,
            "marital_status": values.get("marital_status") or False,
            "nationality": values.get("nationality") or False,
            "resident_type": values.get("resident_type") or "Primary Tenant",
            "mobile": values.get("mobile") or False,
            "email": values.get("email") or False,
            "alt_phone": values.get("alt_phone") or False,
            "street": values.get("street") or False,
            "city": values.get("city") or False,
            "state_name": values.get("state_name") or False,
            "zip": values.get("zip") or False,
            "country": values.get("country") or False,
            "unit_id": unit.id if unit else False,
            "building_id": building_id or False,
            "move_in_date": values.get("move_in") or False,
            "lease_term": values.get("lease_term") or False,
            "id_type": values.get("id_type") or False,
            "id_number": values.get("id_number") or False,
        }
        if create:
            vals.update({
                "status": "pending",
                "onboarding_stage": "submitted",
                "onboarding_progress": 10 if values.get("draft") else 15,
            })
        return vals

    @api.model
    def create_resident(self, values):
        values = values or {}
        rec = self.env["resident.resident"].create(self._resident_vals(values, create=True))
        if values.get("em_name"):
            self.env["resident.emergency.contact"].create({
                "resident_id": rec.id,
                "name": values.get("em_name"),
                "relation": values.get("em_relation") or False,
                "phone": values.get("em_phone") or False,
                "email": values.get("em_email") or False,
            })
        return self.get_dashboard_data()

    @api.model
    def update_resident(self, values):
        values = values or {}
        rec = self.env["resident.resident"].browse(int(values.get("id") or 0))
        if rec.exists():
            rec.write(self._resident_vals(values))
            if rec.partner_id:
                rec.partner_id.write({
                    "name": rec.name,
                    "email": rec.email,
                    "phone": rec.mobile,
                    "street": rec.street,
                    "city": rec.city,
                    "zip": rec.zip,
                })
            self.env["resident.status.history"].create({
                "resident_id": rec.id,
                "activity_type": "profile",
                "title": "Profile Updated",
                "body": "Resident profile details were saved.",
                "new_status": rec.status,
                "performed_by": self.env.user.name,
            })
        return self.get_dashboard_data()

    @api.model
    def delete_resident(self, resident_id):
        rec = self.env["resident.resident"].browse(int(resident_id or 0))
        if not rec.exists():
            raise UserError("Resident was not found.")
        rec.unlink()
        return self.get_dashboard_data()

    @api.model
    def update_resident_status(self, resident_id, status, reason=False, notes=False):
        rec = self.env["resident.resident"].browse(int(resident_id or 0))
        if rec.exists() and status:
            old = rec.status
            rec.write({"status": status, "status_reason": reason or rec.status_reason, "status_since": fields.Date.context_today(self)})
            self.env["resident.status.history"].create({
                "resident_id": rec.id,
                "activity_type": "status",
                "title": "Status Changed",
                "body": notes or f"Status updated from {old} to {status}.",
                "old_status": old,
                "new_status": status,
                "performed_by": self.env.user.name,
                "reason": reason or False,
                "notes": notes or False,
            })
        return self.get_dashboard_data()

    @api.model
    def review_kyc(self, kyc_id, action, checks=None):
        rec = self.env["resident.kyc.document"].browse(int(kyc_id or 0))
        if not rec.exists():
            return self.get_dashboard_data()
        checks = checks or {}
        vals = {key: bool(checks.get(key)) for key in ("identity_match", "document_readable", "document_valid", "not_expired", "information_match")}
        if action == "approve":
            vals.update({"status": "verified", "reviewer": self.env.user.name})
            rec.resident_id.kyc_state = "verified"
        elif action == "reject":
            vals.update({"status": "rejected", "reviewer": self.env.user.name, "reject_reason": checks.get("reason") or "Rejected"})
            rec.resident_id.kyc_state = "rejected"
        elif action == "resubmit":
            vals.update({"status": "pending"})
        else:
            vals.update({"status": "review", "reviewer": self.env.user.name})
        rec.write(vals)
        return self.get_dashboard_data()

    @api.model
    def onboard_action(self, resident_id, action):
        rec = self.env["resident.resident"].browse(int(resident_id or 0))
        if rec.exists():
            if action == "approve":
                rec.write({"onboarding_stage": "approved", "status": "active", "onboarding_progress": 100, "kyc_state": "verified"})
            elif action == "reject":
                rec.write({"onboarding_stage": "rejected", "status": "pending"})
            elif action == "changes":
                rec.write({"onboarding_stage": "docs", "onboarding_progress": 40})
            elif action == "start":
                rec.write({"onboarding_stage": "submitted", "status": "pending", "onboarding_progress": 15})
        return self.get_dashboard_data()

    @api.model
    def add_household_member(self, values):
        values = values or {}
        member = self.env["resident.household.member"].browse(int(values.get("id") or 0))
        payload = {
            "name": values.get("name") or "Member",
            "relation": values.get("relation") or "Other",
            "email": values.get("email") or False,
            "phone": values.get("phone") or False,
            "member_status": values.get("status") or "active",
        }
        if member.exists():
            member.write(payload)
            return self.get_dashboard_data()
        resident = self.env["resident.resident"].browse(int(values.get("resident_id") or 0))
        if resident.exists():
            payload["resident_id"] = resident.id
            self.env["resident.household.member"].create(payload)
        return self.get_dashboard_data()

    @api.model
    def add_emergency_contact(self, values):
        values = values or {}
        resident = self.env["resident.resident"].browse(int(values.get("resident_id") or 0))
        if resident.exists():
            self.env["resident.emergency.contact"].create({
                "resident_id": resident.id,
                "name": values.get("name") or "Contact",
                "relation": values.get("relation") or False,
                "phone": values.get("phone") or False,
                "email": values.get("email") or False,
                "priority": values.get("priority") or "primary",
            })
        return self.get_dashboard_data()

    @api.model
    def toggle_checklist(self, item_id):
        rec = self.env["resident.checklist.item"].browse(int(item_id or 0))
        if rec.exists():
            rec.done = not rec.done
        return self.get_dashboard_data()

    @api.model
    def move_action(self, move_id, action):
        rec = self.env["resident.move.request"].browse(int(move_id or 0))
        if rec.exists():
            if action == "approve":
                rec.write({"approved": True, "state": "scheduled"})
            elif action == "schedule":
                rec.write({"state": "scheduled"})
            elif action == "complete":
                rec.write({"state": "done"})
                if rec.move_type == "in":
                    rec.resident_id.write({"status": "active"})
                else:
                    rec.resident_id.write({"status": "moved_out"})
            elif action == "clearance":
                html = self._clearance_html(rec)
                rec.write({
                    "state": "progress",
                    "clearance_name": f"Clearance_{rec.resident_id.code or rec.id}.html",
                    "clearance_mimetype": "text/html",
                    "clearance_file": base64.b64encode(html.encode("utf-8")),
                })
                self.env["resident.status.history"].create({
                    "resident_id": rec.resident_id.id,
                    "activity_type": "move",
                    "title": "Clearance Certificate Generated",
                    "body": rec.clearance_name,
                    "new_status": rec.resident_id.status,
                    "performed_by": self.env.user.name,
                })
        return self.get_dashboard_data()

    def _clearance_html(self, rec):
        today = fields.Date.context_today(self)
        return (
            "<html><body style='font-family:Arial;padding:32px'>"
            "<h1>Unit Clearance Certificate</h1>"
            f"<p>Resident: <b>{rec.resident_id.name}</b> ({rec.resident_id.code})</p>"
            f"<p>Unit: <b>{rec.unit_id.name if rec.unit_id else rec.resident_id.unit_id.name}</b></p>"
            f"<p>Move-out date: <b>{rec.planned_date or today}</b></p>"
            f"<p>Issued by: {self.env.user.name} on {today}</p>"
            "<p>This certifies that the move-out clearance process has been recorded in Resident Management.</p>"
            "</body></html>"
        )

    @api.model
    def get_clearance_file(self, move_id):
        rec = self.env["resident.move.request"].browse(int(move_id or 0))
        if not rec.exists() or not rec.clearance_file:
            return False
        return {
            "filename": rec.clearance_name or "clearance.html",
            "mimetype": rec.clearance_mimetype or "text/html",
            "data": rec.clearance_file.decode() if isinstance(rec.clearance_file, bytes) else rec.clearance_file,
        }

    @api.model
    def get_kyc_file(self, kyc_id):
        rec = self.env["resident.kyc.document"].browse(int(kyc_id or 0))
        if not rec.exists() or not rec.file_data:
            return False
        return {
            "filename": rec.file_name or rec.name,
            "mimetype": rec.mimetype or "application/octet-stream",
            "data": rec.file_data.decode() if isinstance(rec.file_data, bytes) else rec.file_data,
        }

    @api.model
    def upload_kyc_document(self, values):
        values = values or {}
        resident = self.env["resident.resident"].browse(int(values.get("resident_id") or 0))
        if not resident.exists():
            return self.get_dashboard_data()
        size = int(values.get("size") or 0)
        size_label = f"{round(size / 1024, 1)} KB" if size else "—"
        self.env["resident.kyc.document"].create({
            "name": values.get("name") or values.get("file_name") or "Document",
            "resident_id": resident.id,
            "document_type": values.get("document_type") or "ID",
            "document_number": values.get("document_number") or False,
            "file_name": values.get("file_name") or values.get("name"),
            "file_size": size_label,
            "file_data": values.get("file_data") or False,
            "mimetype": values.get("mimetype") or False,
            "status": "pending",
            "reviewer": "Unassigned",
        })
        resident.write({"kyc_state": "pending", "onboarding_stage": "docs"})
        return self.get_dashboard_data()

    def _audience_residents(self, values):
        Residents = self.env["resident.resident"]
        kind = values.get("audience_type") or "all"
        if kind == "resident":
            rec = Residents.browse(int(values.get("audience_id") or 0))
            return rec if rec.exists() else Residents
        if kind == "building":
            return Residents.search([("building_id", "=", int(values.get("audience_id") or 0))])
        if kind == "unit":
            return Residents.search([("unit_id", "=", int(values.get("audience_id") or 0))])
        return Residents.search([])

    @api.model
    def send_communication(self, values):
        values = values or {}
        targets = self._audience_residents(values)
        audience = values.get("audience") or "All Residents"
        if values.get("audience_type") == "resident" and targets:
            audience = targets[:1].name
        comm = self.env["resident.communication"].create({
            "name": values.get("subject") or "Announcement",
            "body": values.get("body") or "",
            "audience": audience,
            "channel_push": bool(values.get("push")),
            "channel_email": bool(values.get("email")),
            "channel_sms": bool(values.get("sms")),
            "sent_by": self.env.user.name,
            "state": "scheduled" if values.get("schedule") else "delivered",
            "attachment_name": values.get("attachment") or False,
            "attachment_file": values.get("attachment_data") or False,
            "attachment_mimetype": values.get("attachment_mimetype") or False,
        })
        for resident in targets:
            self.env["resident.comm.recipient"].create({
                "comm_id": comm.id,
                "resident_id": resident.id,
                "delivery": "delivered" if not values.get("schedule") else "unread",
                "read": False,
            })
        return self.get_dashboard_data()

    @api.model
    def export_residents(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["code", "first_name", "last_name", "email", "mobile", "unit", "status", "kyc_state"])
        for rec in self.env["resident.resident"].search([]):
            writer.writerow([
                rec.code or "",
                rec.first_name or "",
                rec.last_name or "",
                rec.email or "",
                rec.mobile or "",
                rec.unit_id.name or "",
                rec.status or "",
                rec.kyc_state or "",
            ])
        return {"filename": "residents.csv", "csv": output.getvalue()}

    @api.model
    def import_residents(self, csv_text):
        text = (csv_text or "").strip()
        if not text:
            return self.get_dashboard_data()
        reader = csv.DictReader(io.StringIO(text))
        units = {u.name.lower(): u for u in self.env["property.unit"].search([])}
        for row in reader:
            first = (row.get("first_name") or row.get("First Name") or "").strip()
            last = (row.get("last_name") or row.get("Last Name") or "").strip()
            if not first and not last:
                name = (row.get("name") or "").strip()
                parts = name.split(" ", 1)
                first = parts[0] if parts else "Imported"
                last = parts[1] if len(parts) > 1 else "Resident"
            unit_name = (row.get("unit") or "").strip().lower()
            unit = units.get(unit_name)
            status = (row.get("status") or "pending").strip() or "pending"
            if status not in dict(self.env["resident.resident"]._fields["status"].selection):
                status = "pending"
            self.env["resident.resident"].create({
                "first_name": first or "Imported",
                "last_name": last or "Resident",
                "email": row.get("email") or False,
                "mobile": row.get("mobile") or row.get("phone") or False,
                "unit_id": unit.id if unit else False,
                "building_id": unit.building_id.id if unit and unit.building_id else False,
                "status": status,
                "onboarding_stage": "submitted",
            })
        return self.get_dashboard_data()
