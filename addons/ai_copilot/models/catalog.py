# -*- coding: utf-8 -*-

"""Optional FMS sources. Missing models are skipped at runtime."""

APP_LINKS = [
    ("community_communication.menu_community_communication_root", "Community", "fa-users"),
    ("fire_safety_management.menu_fire_safety_root", "Fire & Safety", "fa-fire-extinguisher"),
    ("compliance_audit_management.menu_compliance_root", "Compliance", "fa-check-square-o"),
    ("integration_iot_management.menu_iot_root", "IoT Sensors", "fa-rss"),
    ("reports_analytics.menu_analytics_root", "Reports", "fa-bar-chart"),
    ("mobile_application.menu_mobile_root", "Mobile", "fa-mobile"),
]

SUGGESTIONS = {
    "default": [
        "Show overdue maintenance requests",
        "What equipment needs servicing?",
        "Show today's visitor activity",
        "Summarize this month's incidents",
    ],
    "fire_safety_management": [
        "Which fire safety inspections are overdue?",
        "What equipment needs servicing?",
        "Summarize this month's incidents",
        "Which drills are still open?",
    ],
    "compliance_audit_management": [
        "Which compliance activities are overdue?",
        "Summarize compliance performance this month",
        "Which non-compliances are still open?",
        "Which compliance documents are expiring?",
    ],
    "community_communication": [
        "What community events are coming up?",
        "Show open resident feedback",
        "What announcements are published?",
    ],
    "integration_iot_management": [
        "Which IoT alerts are open?",
        "Compare energy consumption between this month and last month",
        "Which devices are offline?",
    ],
    "mobile_application": [
        "Show today's visitor activity",
        "What are my upcoming amenity bookings?",
        "Show open service requests",
    ],
}


def _or_domain(parts):
    parts = [part for part in parts if part]
    if not parts:
        return []
    if len(parts) == 1:
        return [parts[0]]
    domain = ["|"] * (len(parts) - 1)
    domain.extend(parts)
    return domain


def equipment_domain(model, today, flags):
    if not (flags.get("service") or flags.get("overdue")):
        return []
    parts = []
    if "service_due_date" in model._fields:
        parts.append(("service_due_date", "<=", today))
    if "inspection_due_date" in model._fields:
        parts.append(("inspection_due_date", "<=", today))
    if "expiry_date" in model._fields:
        parts.append(("expiry_date", "<=", today))
    if "state" in model._fields:
        parts.append(("state", "in", ["service_due", "inspection_due", "expired", "faulty", "under_maintenance"]))
    return _or_domain(parts)


def inspection_domain(model, today, flags):
    domain = []
    if "state" in model._fields and (flags.get("overdue") or flags.get("open")):
        domain.append(("state", "not in", ["completed", "closed", "cancelled"]))
    if flags.get("overdue") and "scheduled_date" in model._fields:
        domain.append(("scheduled_date", "<", today))
    return domain


def compliance_check_domain(model, today, flags):
    domain = []
    if "state" in model._fields and (flags.get("overdue") or flags.get("open")):
        domain.append(("state", "!=", "completed"))
    if flags.get("overdue") and "due_date" in model._fields:
        domain.append(("due_date", "<", today))
    return domain


def open_state_domain(model, today, flags, closed):
    del today
    if not (flags.get("open") or flags.get("overdue")):
        return []
    if "state" not in model._fields:
        return []
    return [("state", "not in", closed)]


def maintenance_domain(model, today, flags):
    del today
    if not (flags.get("open") or flags.get("overdue")):
        return []
    if "stage_id" in model._fields and "done" in model.env["maintenance.stage"]._fields:
        return [("stage_id.done", "=", False)]
    if "state" in model._fields:
        return [("state", "not in", ["done", "closed", "cancelled", "completed"])]
    return []


SOURCES = [
    {
        "key": "fs_equipment",
        "model": "fire.safety.equipment",
        "module": "fire_safety_management",
        "label": "Fire Safety Equipment",
        "kind": "fms_data",
        "keywords": ("equipment", "extinguisher", "hydrant", "sprinkler", "servicing", "service due"),
        "search_fields": ("name", "code", "location_detail"),
        "list_fields": ("name", "code", "state", "service_due_date", "inspection_due_date"),
        "date_field": "service_due_date",
        "domain": equipment_domain,
        "order": "service_due_date, id desc",
    },
    {
        "key": "fs_inspection",
        "model": "fire.safety.inspection",
        "module": "fire_safety_management",
        "label": "Fire Safety Inspections",
        "kind": "fms_data",
        "keywords": ("inspection", "inspections", "audit"),
        "search_fields": ("name", "location_detail"),
        "list_fields": ("name", "state", "scheduled_date", "inspection_type"),
        "date_field": "scheduled_date",
        "domain": inspection_domain,
        "order": "scheduled_date, id desc",
    },
    {
        "key": "fs_incident",
        "model": "fire.safety.incident",
        "module": "fire_safety_management",
        "label": "Fire Safety Incidents",
        "kind": "fms_data",
        "keywords": ("incident", "incidents"),
        "search_fields": ("name", "location_detail"),
        "list_fields": ("name", "state", "incident_datetime", "priority"),
        "date_field": "incident_datetime",
        "domain": lambda model, today, flags: open_state_domain(
            model, today, flags, ["closed", "cancelled"]
        ) if flags.get("open") else [],
        "order": "incident_datetime desc, id desc",
    },
    {
        "key": "fs_drill",
        "model": "fire.safety.drill",
        "module": "fire_safety_management",
        "label": "Fire Safety Drills",
        "kind": "fms_data",
        "keywords": ("drill", "drills"),
        "search_fields": ("name",),
        "list_fields": ("name", "state", "scheduled_date"),
        "date_field": "scheduled_date",
        "domain": lambda model, today, flags: open_state_domain(
            model, today, flags, ["completed", "closed", "cancelled"]
        ),
        "order": "id desc",
    },
    {
        "key": "cmp_check",
        "model": "compliance.check",
        "module": "compliance_audit_management",
        "label": "Compliance Activities",
        "kind": "fms_data",
        "keywords": ("compliance", "compliant", "checklist"),
        "search_fields": ("name",),
        "list_fields": ("name", "state", "due_date"),
        "date_field": "due_date",
        "domain": compliance_check_domain,
        "order": "due_date, id desc",
    },
    {
        "key": "cmp_nc",
        "model": "compliance.non.compliance",
        "module": "compliance_audit_management",
        "label": "Non-Compliances",
        "kind": "fms_data",
        "keywords": ("non-compliance", "noncompliance", "violation"),
        "search_fields": ("name",),
        "list_fields": ("name", "state", "due_date"),
        "date_field": "due_date",
        "domain": lambda model, today, flags: open_state_domain(
            model, today, flags, ["resolved", "closed", "cancelled"]
        ),
        "order": "id desc",
    },
    {
        "key": "cmp_document",
        "model": "compliance.document",
        "module": "compliance_audit_management",
        "label": "Compliance Documents",
        "kind": "document",
        "keywords": ("certificate", "expiring", "expiry"),
        "search_fields": ("name", "issuing_authority"),
        "list_fields": ("name", "state", "expiry_date", "document_type"),
        "date_field": "expiry_date",
        "domain": lambda model, today, flags: (
            [("expiry_date", "<=", today)] if flags.get("overdue") and "expiry_date" in model._fields else []
        ),
        "order": "expiry_date, id desc",
    },
    {
        "key": "cc_feedback",
        "model": "community.communication.feedback",
        "module": "community_communication",
        "label": "Resident Feedback",
        "kind": "fms_data",
        "keywords": ("feedback", "complaint"),
        "search_fields": ("name",),
        "list_fields": ("name", "state"),
        "date_field": "create_date",
        "domain": lambda model, today, flags: open_state_domain(
            model, today, flags, ["closed", "cancelled", "resolved", "done"]
        ),
        "order": "id desc",
    },
    {
        "key": "cc_event",
        "model": "community.communication.event",
        "module": "community_communication",
        "label": "Community Events",
        "kind": "fms_data",
        "keywords": ("event", "events", "amenity", "amenities"),
        "search_fields": ("name",),
        "list_fields": ("name", "state", "date_start", "category"),
        "date_field": "date_start",
        "domain": lambda model, today, flags: [],
        "order": "date_start, id",
    },
    {
        "key": "cc_announcement",
        "model": "community.communication.announcement",
        "module": "community_communication",
        "label": "Announcements",
        "kind": "fms_data",
        "keywords": ("announcement", "announcements", "notice"),
        "search_fields": ("name",),
        "list_fields": ("name", "state"),
        "date_field": "create_date",
        "domain": lambda model, today, flags: [],
        "order": "id desc",
    },
    {
        "key": "iot_alert",
        "model": "integration.iot.alert",
        "module": "integration_iot_management",
        "label": "IoT Alerts",
        "kind": "fms_data",
        "keywords": ("alert", "alerts", "fault", "offline"),
        "search_fields": ("name",),
        "list_fields": ("name", "state"),
        "date_field": "create_date",
        "domain": lambda model, today, flags: open_state_domain(
            model, today, flags, ["closed", "resolved", "cancelled"]
        ),
        "order": "id desc",
    },
    {
        "key": "iot_energy",
        "model": "integration.iot.energy.reading",
        "module": "integration_iot_management",
        "label": "Energy Readings",
        "kind": "fms_data",
        "keywords": ("energy", "consumption", "kwh"),
        "search_fields": ("name", "note"),
        "list_fields": ("name", "kwh", "captured_at", "is_peak"),
        "date_field": "captured_at",
        "domain": lambda model, today, flags: [],
        "order": "captured_at desc, id desc",
        "measure": "kwh",
    },
    {
        "key": "mobile_visitor",
        "model": "mobile.visitor",
        "module": "mobile_application",
        "label": "Visitors",
        "kind": "fms_data",
        "keywords": ("visitor", "visitors"),
        "search_fields": ("name", "purpose", "building_label", "unit_label"),
        "list_fields": ("name", "state", "expected_start", "purpose", "building_label"),
        "date_field": "expected_start",
        "domain": lambda model, today, flags: [],
        "order": "expected_start desc, id desc",
        "note": "Visitor timing uses the expected visit start. This source has no separate gate-entry timestamp.",
    },
    {
        "key": "mobile_booking",
        "model": "mobile.booking",
        "module": "mobile_application",
        "label": "Amenity Bookings",
        "kind": "fms_data",
        "keywords": ("booking", "bookings", "amenity", "amenities"),
        "search_fields": ("amenity_name", "slot_label"),
        "list_fields": ("amenity_name", "state", "booking_date", "slot_label"),
        "date_field": "booking_date",
        "domain": lambda model, today, flags: [],
        "order": "booking_date, id desc",
    },
    {
        "key": "mobile_request",
        "model": "mobile.service.request",
        "module": "mobile_application",
        "label": "Service Requests",
        "kind": "fms_data",
        "keywords": ("service request", "maintenance", "work order", "requests"),
        "search_fields": ("name", "category", "description"),
        "list_fields": ("name", "category", "state", "assigned_user_id"),
        "date_field": "create_date",
        "domain": lambda model, today, flags: (
            [("state", "not in", ["completed", "closed"])]
            if (flags.get("open") or flags.get("overdue")) and "state" in model._fields
            else []
        ),
        "order": "create_date desc, id desc",
    },
    {
        "key": "maint_request",
        "model": "maintenance.request",
        "module": "maintenance",
        "label": "Maintenance Requests",
        "kind": "fms_data",
        "keywords": ("maintenance", "work order", "requests"),
        "search_fields": ("name", "description"),
        "list_fields": ("name", "stage_id", "schedule_date", "user_id"),
        "date_field": "create_date",
        "domain": maintenance_domain,
        "order": "id desc",
    },
]

PROPOSAL_MODELS = {
    "maintenance.request": {
        "title": "Create Maintenance Request",
        "module": "maintenance",
    },
    "mobile.service.request": {
        "title": "Create Service Request",
        "module": "mobile_application",
    },
}
