# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import XMLID_GROUP_RESIDENT, XMLID_GROUP_SECURITY, XMLID_GROUP_STAFF


class MobileApplicationService(models.AbstractModel):
    _name = "mobile.application.service"
    _description = "Mobile Application API Service"

    # ------------------------------------------------------------------ RBAC
    @api.model
    def _ensure_mobile_user(self):
        user = self.env.user
        if user._is_public():
            raise AccessError(_("Authentication required."))
        role = self.env["mobile.application.profile"]._role_for_user(user)
        if role == "none":
            raise AccessError(_("You do not have access to the Mobile Application."))
        return user, role

    @api.model
    def get_capabilities(self):
        user, role = self._ensure_mobile_user()
        community = self.env["mobile.integration.community"]
        external = self.env["mobile.integration.external"]
        modules = {
            "community": community.available and role == "resident",
            "service_requests": role in ("resident", "staff"),
            "helpdesk": role in ("resident", "staff") and external.helpdesk_available(),
            "amenity_booking": role == "resident",
            "visitor_management": role in ("resident", "security", "staff"),
            "payments": role == "resident",
            "digital_id": True,
            "notifications": True,
        }
        if role == "security":
            modules["payments"] = False
        if external.service_requests_available():
            modules["service_requests"] = role in ("resident", "staff")
        if not external.helpdesk_available():
            modules["helpdesk"] = False
        if external.payments_available():
            modules["payments"] = role == "resident"
        return {"role": role, "modules": modules, "push_configured": bool(self.env["mobile.application.profile"].get_or_create_for_user(user).push_provider)}

    @api.model
    def get_profile(self):
        user, role = self._ensure_mobile_user()
        profile = self.env["mobile.application.profile"].get_or_create_for_user(user)
        resident = self.env.get("community.communication.resident")
        building = profile.building_label or ""
        unit = profile.unit_label or ""
        if resident:
            rec = resident.search([("user_id", "=", user.id)], limit=1)
            if rec:
                building = rec.building_id.display_name if rec.building_id else building
                unit = rec.unit_id.display_name if rec.unit_id else unit
        return {
            "name": user.name,
            "email": user.email,
            "phone": user.partner_id.phone or "",
            "role": role,
            "building": building,
            "unit": unit,
            "avatar_url": f"/web/image/res.users/{user.id}/avatar_128",
            "notification_prefs": profile.notification_prefs or {},
        }

    @api.model
    def get_home(self):
        user, role = self._ensure_mobile_user()
        caps = self.get_capabilities()
        community = self.env["mobile.integration.community"].get_updates(user)
        notifications = self._notification_count(user)
        my_requests = self._service_requests_for_user(user, limit=5)
        bookings = self._bookings_for_user(user, upcoming=True, limit=5)
        visitors = self._visitors_for_user(user, scope="upcoming", limit=5)
        pending_approvals = []
        if role in ("security", "staff"):
            pending_approvals = self._visitors_for_user(user, scope="pending_approval", limit=10)
        return {
            "greeting": _("Hello"),
            "profile": self.get_profile(),
            "capabilities": caps,
            "important_updates": community.get("items", []),
            "community_available": community.get("available"),
            "notification_count": notifications,
            "my_requests": my_requests,
            "upcoming_bookings": bookings,
            "upcoming_visitors": visitors,
            "pending_visitor_approvals": pending_approvals,
        }

    @api.model
    def get_notifications(self, limit=50, offset=0):
        user, _role = self._ensure_mobile_user()
        domain = [("user_id", "=", user.id)]
        Model = self.env["mobile.application.notification"]
        total = Model.search_count(domain)
        records = Model.search(domain, limit=limit, offset=offset)
        return {
            "total": total,
            "unread": Model.search_count(domain + [("is_read", "=", False)]),
            "items": [
                {
                    "id": r.id,
                    "title": r.title,
                    "message": r.message,
                    "type": r.notification_type,
                    "priority": r.priority,
                    "is_read": r.is_read,
                    "created_at": fields.Datetime.to_string(r.create_date),
                    "action_route": r.action_route,
                    "res_model": r.res_model,
                    "res_id": r.res_id,
                }
                for r in records
            ],
        }

    @api.model
    def mark_notification_read(self, notification_id):
        self._ensure_mobile_user()
        note = self.env["mobile.application.notification"].browse(notification_id)
        note.check_access("read")
        if note.user_id != self.env.user:
            raise AccessError(_("Not your notification."))
        note.action_mark_read()
        return True

    @api.model
    def mark_all_notifications_read(self):
        user, _role = self._ensure_mobile_user()
        return self.env["mobile.application.notification"].mark_all_read(user)

    @api.model
    def sync(self, last_sync=None, idempotency_key=None):
        user, role = self._ensure_mobile_user()
        if idempotency_key:
            existing = self.env["mobile.sync.log"].search([
                ("user_id", "=", user.id),
                ("idempotency_key", "=", idempotency_key),
            ], limit=1)
            if existing:
                return self._sync_payload(user, role, existing.last_value)
        caps = self.get_capabilities()
        unread = self._notification_count(user)
        now = fields.Datetime.now()
        self.env["mobile.sync.log"].touch("last_sync", fields.Datetime.to_string(now))
        if idempotency_key:
            self.env["mobile.sync.log"].create({
                "user_id": user.id,
                "sync_key": "idempotency",
                "idempotency_key": idempotency_key,
                "last_value": fields.Datetime.to_string(now),
            })
        session = self.env["mobile.application.session"].search([("user_id", "=", user.id)], limit=1)
        vals = {
            "user_id": user.id,
            "last_sync_at": now,
            "unread_count": unread,
            "capabilities_snapshot": caps,
        }
        if session:
            session.write(vals)
        else:
            self.env["mobile.application.session"].create(vals)
        return self._sync_payload(user, role, fields.Datetime.to_string(now), caps, unread)

    def _sync_payload(self, user, role, last_sync, caps=None, unread=None):
        return {
            "last_sync": last_sync,
            "role": role,
            "capabilities": caps or self.get_capabilities(),
            "unread_notifications": unread if unread is not None else self._notification_count(user),
            "home": self.get_home(),
        }

    @api.model
    def _notification_count(self, user):
        return self.env["mobile.application.notification"].search_count([
            ("user_id", "=", user.id),
            ("is_read", "=", False),
        ])

    # ------------------------------------------------------------- Service req
    @api.model
    def list_service_requests(self, state=None, limit=30):
        user, role = self._ensure_mobile_user()
        external = self.env["mobile.integration.external"].list_external_service_requests(user, limit=limit)
        if external.get("available"):
            return external
        domain = []
        if role == "resident":
            domain.append(("user_id", "=", user.id))
        elif role == "staff":
            domain = ["|", ("user_id", "=", user.id), ("assigned_user_id", "=", user.id)]
        if state:
            domain.append(("state", "=", state))
        records = self.env["mobile.service.request"].search(domain, limit=limit)
        return {
            "available": True,
            "items": [self._serialize_service_request(r) for r in records],
        }

    @api.model
    def create_service_request(self, category, description, idempotency_key=None, attachment_ids=None):
        user, role = self._ensure_mobile_user()
        if role != "resident":
            raise AccessError(_("Only residents can create service requests from mobile."))
        if idempotency_key:
            existing = self.env["mobile.service.request"].search([("idempotency_key", "=", idempotency_key)], limit=1)
            if existing:
                return self._serialize_service_request(existing)
        vals = {
            "category": category,
            "description": description,
            "user_id": user.id,
            "idempotency_key": idempotency_key,
        }
        if attachment_ids:
            vals["attachment_ids"] = [(6, 0, attachment_ids)]
        record = self.env["mobile.service.request"].create(vals)
        return self._serialize_service_request(record)

    def _serialize_service_request(self, record):
        return {
            "id": record.id,
            "name": record.name,
            "category": record.category,
            "description": record.description,
            "state": record.state,
            "last_update": fields.Datetime.to_string(record.write_date),
        }

    # ---------------------------------------------------------------- Visitors
    @api.model
    def list_visitors(self, scope="all", limit=30):
        user, role = self._ensure_mobile_user()
        return {"available": True, "items": self._visitors_for_user(user, scope=scope, limit=limit, role=role)}

    def _visitors_for_user(self, user, scope="all", limit=10, role=None):
        role = role or self.env["mobile.application.profile"]._role_for_user(user)
        Visitor = self.env["mobile.visitor"]
        domain = []
        now = fields.Datetime.now()
        if role == "resident":
            domain.append(("resident_user_id", "=", user.id))
        elif role == "security":
            if scope == "pending_approval":
                domain.append(("state", "=", "approved"))
            elif scope == "arrivals":
                domain.append(("state", "in", ("approved", "verified", "checked_in")))
        elif role == "staff":
            domain.append(("state", "!=", "cancelled"))
        if scope == "today":
            domain.extend([
                ("expected_start", ">=", fields.Datetime.to_string(now.replace(hour=0, minute=0, second=0))),
                ("expected_start", "<=", fields.Datetime.to_string(now.replace(hour=23, minute=59, second=59))),
            ])
        elif scope == "upcoming":
            domain.append(("expected_start", ">=", fields.Datetime.to_string(now)))
        elif scope == "past":
            domain.append(("expected_start", "<", fields.Datetime.to_string(now)))
        records = Visitor.search(domain, limit=limit, order="expected_start desc")
        return [self._serialize_visitor(v) for v in records]

    @api.model
    def create_visitor(self, payload, idempotency_key=None):
        user, role = self._ensure_mobile_user()
        if role != "resident":
            raise AccessError(_("Only residents can register visitors."))
        if idempotency_key:
            existing = self.env["mobile.visitor"].search([("idempotency_key", "=", idempotency_key)], limit=1)
            if existing:
                return self._serialize_visitor(existing)
        profile = self.get_profile()
        vals = {
            "name": payload.get("name"),
            "phone": payload.get("phone"),
            "purpose": payload.get("purpose"),
            "notes": payload.get("notes"),
            "expected_start": payload.get("expected_start"),
            "expected_end": payload.get("expected_end"),
            "duration_hours": payload.get("duration_hours"),
            "unit_label": profile.get("unit") or payload.get("unit_label"),
            "building_label": profile.get("building") or payload.get("building_label"),
            "resident_user_id": user.id,
            "state": "submitted",
            "idempotency_key": idempotency_key,
        }
        if not vals["name"] or not vals["purpose"] or not vals["expected_start"]:
            raise UserError(_("Visitor name, purpose, and expected time are required."))
        record = self.env["mobile.visitor"].create(vals)
        return self._serialize_visitor(record)

    @api.model
    def visitor_action(self, visitor_id, action):
        self._ensure_mobile_user()
        visitor = self.env["mobile.visitor"].browse(visitor_id)
        visitor.check_access("read")
        if action == "approve":
            visitor.action_approve()
        elif action == "deny":
            visitor.action_deny()
        elif action == "verify":
            visitor.action_verify()
        elif action == "check_in":
            visitor.action_check_in()
        elif action == "check_out":
            visitor.action_check_out()
        else:
            raise UserError(_("Unknown visitor action."))
        return self._serialize_visitor(visitor)

    def _serialize_visitor(self, record):
        return {
            "id": record.id,
            "name": record.name,
            "phone": record.phone,
            "purpose": record.purpose,
            "state": record.state,
            "expected_start": fields.Datetime.to_string(record.expected_start),
            "expected_end": fields.Datetime.to_string(record.expected_end) if record.expected_end else "",
            "unit": record.unit_label,
            "building": record.building_label,
            "pass_code": record.pass_code,
        }

    # ---------------------------------------------------------------- Bookings
    @api.model
    def list_bookings(self, upcoming=True, limit=30):
        user, role = self._ensure_mobile_user()
        return {"available": True, "items": self._bookings_for_user(user, upcoming=upcoming, limit=limit)}

    def _bookings_for_user(self, user, upcoming=True, limit=10):
        domain = [("user_id", "=", user.id)]
        if upcoming:
            domain.append(("state", "not in", ("cancelled", "completed")))
        records = self.env["mobile.booking"].search(domain, limit=limit, order="booking_date desc")
        return [self._serialize_booking(b) for b in records]

    @api.model
    def create_booking(self, amenity_name, booking_date, slot_label, idempotency_key=None, notes=None):
        user, role = self._ensure_mobile_user()
        if role != "resident":
            raise AccessError(_("Only residents can book amenities."))
        external = self.env["mobile.integration.external"]
        if external.amenity_available():
            return {
                "available": False,
                "message": _("Amenity module is installed; native mobile booking adapter is not configured yet."),
            }
        if idempotency_key:
            existing = self.env["mobile.booking"].search([("idempotency_key", "=", idempotency_key)], limit=1)
            if existing:
                return self._serialize_booking(existing)
        record = self.env["mobile.booking"].create({
            "user_id": user.id,
            "amenity_name": amenity_name,
            "booking_date": booking_date,
            "slot_label": slot_label,
            "notes": notes,
            "idempotency_key": idempotency_key,
            "state": "requested",
        })
        return self._serialize_booking(record)

    @api.model
    def cancel_booking(self, booking_id):
        self._ensure_mobile_user()
        booking = self.env["mobile.booking"].browse(booking_id)
        booking.action_cancel()
        return self._serialize_booking(booking)

    def _serialize_booking(self, record):
        return {
            "id": record.id,
            "amenity_name": record.amenity_name,
            "booking_date": fields.Date.to_string(record.booking_date),
            "slot_label": record.slot_label,
            "state": record.state,
        }

    # ---------------------------------------------------------------- Payments
    @api.model
    def get_payments(self):
        user, role = self._ensure_mobile_user()
        if role != "resident":
            raise AccessError(_("Payments are only available to residents."))
        external = self.env["mobile.integration.external"].payment_summary(user)
        if external.get("available"):
            return external
        records = self.env["mobile.payment.record"].search([("user_id", "=", user.id)], limit=30)
        balance = sum(r.amount for r in records if r.state == "pending")
        return {
            "available": True,
            "provider_configured": False,
            "balance": balance,
            "items": [
                {
                    "id": r.id,
                    "description": r.description,
                    "amount": r.amount,
                    "state": r.state,
                    "currency": r.currency_id.name,
                }
                for r in records
            ],
        }

    # ---------------------------------------------------------------- Community
    @api.model
    def get_community(self, section="home"):
        user, role = self._ensure_mobile_user()
        if role != "resident":
            raise AccessError(_("Community content is for residents."))
        integration = self.env["mobile.integration.community"]
        if section == "announcements":
            return integration.list_announcements(user)
        if section == "events":
            return integration.list_events(user)
        if section == "polls":
            return integration.list_polls(user)
        return integration.get_updates(user)

    # ---------------------------------------------------------------- Digital ID
    @api.model
    def get_digital_id(self):
        self._ensure_mobile_user()
        record = self.env["mobile.digital.id"].get_or_create_for_user()
        return record.get_payload()

    @api.model
    def verify_digital_id(self, token):
        self._ensure_mobile_user()
        return self.env["mobile.digital.id"].verify_token(token)

    # ------------------------------------------------------------- Amenities UI
    @api.model
    def list_amenities(self):
        self._ensure_mobile_user()
        external = self.env["mobile.integration.external"]
        if external.amenity_available():
            return {"available": False, "message": _("Amenity catalog integration pending."), "items": []}
        return {"available": True, "items": [], "slots": [], "message": _("No amenities configured.")}
