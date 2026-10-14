# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import COMPLIANCE_CATEGORIES


class ComplianceDashboard(models.AbstractModel):
    _name = "compliance.dashboard"
    _description = "Compliance Dashboard Aggregator"

    @api.model
    def get_dashboard_kpis(self):
        """Backward-compatible KPI-only payload. """
        return self.get_dashboard_data()["kpis"]

    @api.model
    def get_dashboard_data(self):
        """Full OWL dashboard payload (Phase 2)."""
        Check = self.env["compliance.check"]
        Document = self.env["compliance.document"]
        NC = self.env["compliance.non.compliance"]
        Audit = self.env["compliance.audit"]
        Report = self.env["compliance.regulatory.report"]
        today = fields.Date.context_today(self)
        soon = today + relativedelta(days=30)
        week = today + relativedelta(days=7)

        completed_lines = self.env["compliance.check.line"].search_count(
            [("result", "=", "compliant")]
        )
        scored_lines = self.env["compliance.check.line"].search_count(
            [("result", "in", ["compliant", "non_compliant"])]
        )
        rate = (completed_lines / scored_lines * 100.0) if scored_lines else 0.0

        pending = Check.search_count(
            [("state", "in", ["scheduled", "in_progress", "pending"])]
        )
        due_this_week = Check.search_count(
            [
                ("state", "in", ["scheduled", "in_progress", "pending"]),
                ("due_date", "<=", week),
                ("due_date", ">=", today),
            ]
        )
        overdue = Check.search_count([("is_overdue", "=", True)])
        open_nc = NC.search_count([("state", "not in", ["resolved", "closed"])])
        high_nc = NC.search_count(
            [
                ("state", "not in", ["resolved", "closed"]),
                ("severity", "in", ["high", "critical"]),
            ]
        )

        kpis = {
            "overall_compliance_rate": round(rate, 1),
            "overall_hint": _("Based on checklist line results"),
            "pending_activities": pending,
            "pending_hint": _("%s due this week") % due_this_week if due_this_week else _("No due this week"),
            "overdue_activities": overdue,
            "expiring_documents": Document.search_count(
                [
                    ("state", "in", ["expiring_soon", "renewal_due"]),
                    ("expiry_date", "<=", soon),
                ]
            ),
            "expired_documents": Document.search_count([("state", "=", "expired")]),
            "open_non_compliance": open_nc,
            "nc_hint": _("%s high priority") % high_nc if high_nc else _("No high priority"),
            "overdue_actions": self.env["compliance.action"].search_count(
                [("is_overdue", "=", True)]
            ),
            "audits_completed": Audit.search_count(
                [("kind", "=", "audit"), ("state", "in", ["completed", "closed"])]
            ),
            "inspections_completed": Audit.search_count(
                [("kind", "=", "inspection"), ("state", "in", ["completed", "closed"])]
            ),
            "regulatory_due": Report.search_count(
                [
                    ("state", "!=", "submitted"),
                    ("deadline", ">=", today),
                    ("deadline", "<=", soon),
                ]
            ),
            "regulatory_submitted": Report.search_count([("state", "=", "submitted")]),
        }

        return {
            "kpis": kpis,
            "health_by_category": self._ca_health_by_category(),
            "attention": self._ca_attention_items(today, soon),
            "upcoming_activities": self._ca_upcoming_activities(),
        }

    @api.model
    def _ca_health_by_category(self):
        focus = {"ehs", "fire_life_safety", "hvac", "accessibility"}
        labels = dict(COMPLIANCE_CATEGORIES)
        lines = self.env["compliance.check.line"].search(
            [
                ("result", "in", ["compliant", "non_compliant"]),
                ("check_id.requirement_id.category", "in", list(focus)),
            ]
        )
        buckets = {key: {"compliant": 0, "scored": 0} for key in focus}
        for line in lines:
            category = line.check_id.requirement_id.category
            if category not in buckets:
                continue
            buckets[category]["scored"] += 1
            if line.result == "compliant":
                buckets[category]["compliant"] += 1

        rows = []
        for key in ("ehs", "fire_life_safety", "hvac", "accessibility"):
            scored = buckets[key]["scored"]
            if not scored:
                continue
            rate = buckets[key]["compliant"] / scored * 100.0
            rows.append(
                {
                    "key": key,
                    "label": labels.get(key, key),
                    "rate": round(rate, 1),
                    "scored": scored,
                }
            )
        return rows

    @api.model
    def _ca_attention_items(self, today, soon):
        items = []
        docs = self.env["compliance.document"].search(
            [
                ("state", "in", ["expiring_soon", "renewal_due", "expired"]),
                ("expiry_date", "!=", False),
                ("expiry_date", "<=", soon),
            ],
            order="expiry_date asc",
            limit=3,
        )
        for doc in docs:
            days = (doc.expiry_date - today).days if doc.expiry_date else 0
            if days < 0:
                detail = _("Expired %s days ago") % abs(days)
            else:
                detail = _("Expires in %s days") % days
            items.append(
                {
                    "key": f"doc-{doc.id}",
                    "title": doc.name,
                    "detail": detail,
                    "action_label": _("Open Document"),
                    "res_model": "compliance.document",
                    "res_id": doc.id,
                    "action_xmlid": "compliance_audit_management.action_ca_documents_ui",
                }
            )

        overdue_checks = self.env["compliance.check"].search(
            [("is_overdue", "=", True)],
            order="due_date asc",
            limit=3,
        )
        for check in overdue_checks:
            days = (today - check.due_date).days if check.due_date else 0
            items.append(
                {
                    "key": f"check-{check.id}",
                    "title": check.name,
                    "detail": _("Overdue by %s days") % days,
                    "action_label": _("Open Activity"),
                    "res_model": "compliance.check",
                    "res_id": check.id,
                    "action_xmlid": "compliance_audit_management.action_ca_activities_ui",
                }
            )

        critical_nc = self.env["compliance.non.compliance"].search(
            [
                ("state", "not in", ["resolved", "closed"]),
                ("severity", "in", ["high", "critical"]),
            ],
            order="id desc",
            limit=3,
        )
        for nc in critical_nc:
            items.append(
                {
                    "key": f"nc-{nc.id}",
                    "title": nc.name,
                    "detail": _("%s priority non-compliance") % (nc.severity or "").title(),
                    "action_label": _("View Issue"),
                    "res_model": "compliance.non.compliance",
                    "res_id": nc.id,
                    "action_xmlid": "compliance_audit_management.action_ca_nc_ui",
                }
            )
        return items[:6]

    @api.model
    def _ca_upcoming_activities(self):
        today = fields.Date.context_today(self)
        rows = []
        checks = self.env["compliance.check"].search(
            [("state", "!=", "completed")],
            order="due_date asc, id asc",
            limit=8,
        )
        for check in checks:
            location_parts = [
                check.property_id.name,
                check.building_id.name,
                check.area_id.name,
            ]
            location = " / ".join([part for part in location_parts if part])
            display_state = "overdue" if check.is_overdue else check.state
            rows.append(
                {
                    "key": f"check-{check.id}",
                    "name": check.name,
                    "type_label": _("Compliance Check"),
                    "location": location,
                    "assigned_to": check.assigned_user_id.name,
                    "due_date": fields.Date.to_string(check.due_date) if check.due_date else False,
                    "state": check.state,
                    "display_state": display_state,
                    "status_label": _("Overdue") if check.is_overdue else dict(check._fields["state"].selection).get(check.state),
                }
            )

        audits = self.env["compliance.audit"].search(
            [("state", "not in", ["completed", "closed", "failed"])],
            order="date_planned asc, id asc",
            limit=5,
        )
        for audit in audits:
            location_parts = [
                audit.property_id.name,
                audit.building_id.name,
                audit.area_id.name,
            ]
            location = " / ".join([part for part in location_parts if part])
            overdue = bool(audit.date_planned and audit.date_planned < today)
            rows.append(
                {
                    "key": f"audit-{audit.id}",
                    "name": audit.name,
                    "type_label": _("Inspection") if audit.kind == "inspection" else _("Audit"),
                    "location": location,
                    "assigned_to": audit.assigned_user_id.name,
                    "due_date": fields.Date.to_string(audit.date_planned)
                    if audit.date_planned
                    else False,
                    "state": audit.state,
                    "display_state": "overdue" if overdue else audit.state,
                    "status_label": _("Overdue")
                    if overdue
                    else dict(audit._fields["state"].selection).get(audit.state),
                }
            )

        rows.sort(key=lambda row: row.get("due_date") or "9999-12-31")
        return rows[:8]

    @api.model
    def get_calendar_events(self, date_from, date_to, event_types=None):
        """Month/week calendar payload spanning checks, audits, documents, NC, CA, regulatory."""
        date_from = fields.Date.to_date(date_from) if date_from else fields.Date.context_today(self)
        date_to = fields.Date.to_date(date_to) if date_to else date_from
        if date_to < date_from:
            date_from, date_to = date_to, date_from
        today = fields.Date.context_today(self)
        wanted = set(event_types or ["check", "audit", "document", "nc", "action", "regulatory"])
        events = []

        def location_of(record):
            parts = [
                getattr(record, "property_id", False) and record.property_id.name,
                getattr(record, "building_id", False) and record.building_id.name,
                getattr(record, "area_id", False) and record.area_id.name,
            ]
            return " / ".join([part for part in parts if part])

        def push(event_type, record, date_value, type_label, action_xmlid, open_states=None):
            if not date_value or date_value < date_from or date_value > date_to:
                return
            overdue = bool(
                open_states is not None
                and record.state in open_states
                and date_value < today
            )
            if event_type == "document":
                overdue = record.state == "expired" or (
                    bool(date_value) and date_value < today and record.state != "archived"
                )
            tone = "danger" if overdue else {
                "check": "info",
                "audit": "info",
                "document": "warning" if record.state in ("expiring_soon", "renewal_due", "under_renewal") else "muted",
                "nc": "warning",
                "action": "info",
                "regulatory": "muted",
            }.get(event_type, "muted")
            events.append(
                {
                    "key": f"{event_type}-{record.id}",
                    "id": record.id,
                    "model": record._name,
                    "name": record.name,
                    "date": fields.Date.to_string(date_value),
                    "type": event_type,
                    "type_label": type_label,
                    "state": record.state,
                    "display_state": "overdue" if overdue else record.state,
                    "tone": tone,
                    "action_xmlid": action_xmlid,
                    "location": location_of(record),
                    "assigned_to": record.assigned_user_id.name if getattr(record, "assigned_user_id", False) else "",
                }
            )

        if "check" in wanted:
            open_states = ["scheduled", "in_progress", "pending"]
            for check in self.env["compliance.check"].search(
                [
                    ("state", "in", open_states),
                    ("due_date", ">=", date_from),
                    ("due_date", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "check",
                    check,
                    check.due_date,
                    _("Compliance Check"),
                    "compliance_audit_management.action_ca_activities_ui",
                    open_states,
                )

        if "audit" in wanted:
            open_states = ["scheduled", "in_progress", "pending_review"]
            for audit in self.env["compliance.audit"].search(
                [
                    ("state", "in", open_states),
                    ("date_planned", ">=", date_from),
                    ("date_planned", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "audit",
                    audit,
                    audit.date_planned,
                    _("Inspection") if audit.kind == "inspection" else _("Audit"),
                    "compliance_audit_management.action_ca_audits_ui",
                    open_states,
                )

        if "document" in wanted:
            for doc in self.env["compliance.document"].search(
                [
                    ("state", "!=", "archived"),
                    ("expiry_date", ">=", date_from),
                    ("expiry_date", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "document",
                    doc,
                    doc.expiry_date,
                    _("Document Expiry"),
                    "compliance_audit_management.action_ca_documents_ui",
                )

        if "nc" in wanted:
            open_states = ["open", "assigned", "in_progress", "pending_verification"]
            for nc in self.env["compliance.non.compliance"].search(
                [
                    ("state", "in", open_states),
                    ("due_date", ">=", date_from),
                    ("due_date", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "nc",
                    nc,
                    nc.due_date,
                    _("Non-Compliance"),
                    "compliance_audit_management.action_ca_nc_ui",
                    open_states,
                )

        if "action" in wanted:
            open_states = ["open", "in_progress", "pending_verification"]
            for action in self.env["compliance.action"].search(
                [
                    ("state", "in", open_states),
                    ("deadline", ">=", date_from),
                    ("deadline", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "action",
                    action,
                    action.deadline,
                    _("Corrective Action"),
                    "compliance_audit_management.action_ca_nc_ui",
                    open_states,
                )

        if "regulatory" in wanted:
            open_states = ["draft", "in_preparation"]
            for report in self.env["compliance.regulatory.report"].search(
                [
                    ("state", "in", open_states),
                    ("deadline", ">=", date_from),
                    ("deadline", "<=", date_to),
                ],
                limit=500,
            ):
                push(
                    "regulatory",
                    report,
                    report.deadline,
                    _("Regulatory Report"),
                    "compliance_audit_management.action_ca_regulatory_ui",
                    open_states,
                )

        events.sort(key=lambda row: (row["date"], row["type"], row["name"]))
        return events

    @api.model
    def get_compliance_reports(
        self,
        dataset="checks",
        property_id=False,
        date_from=False,
        date_to=False,
        offset=0,
        limit=20,
    ):
        """Analytics + dataset payload for the Compliance Reports OWL screen."""
        today = fields.Date.context_today(self)
        property_id = int(property_id) if property_id else False
        date_from = fields.Date.to_date(date_from) if date_from else False
        date_to = fields.Date.to_date(date_to) if date_to else False
        offset = max(0, int(offset or 0))
        limit = min(max(1, int(limit or 20)), 100)

        dash = self.get_dashboard_data()
        kpis = dash["kpis"]

        def prop_domain(field="property_id"):
            return [(field, "=", property_id)] if property_id else []

        def date_domain(field):
            domain = []
            if date_from:
                domain.append((field, ">=", date_from))
            if date_to:
                domain.append((field, "<=", date_to))
            return domain

        def count_by_state(model, states, extra=None):
            Model = self.env[model]
            pairs = []
            for state in states:
                domain = [("state", "=", state)] + (extra or []) + prop_domain()
                pairs.append({"state": state, "count": Model.search_count(domain)})
            return pairs

        status_blocks = [
            {
                "id": "checks",
                "label": _("Activities"),
                "pairs": count_by_state(
                    "compliance.check",
                    ["scheduled", "in_progress", "pending", "completed"],
                ),
            },
            {
                "id": "audits",
                "label": _("Audits & Inspections"),
                "pairs": count_by_state(
                    "compliance.audit",
                    ["scheduled", "in_progress", "pending_review", "completed", "failed", "closed"],
                ),
            },
            {
                "id": "documents",
                "label": _("Documents"),
                "pairs": count_by_state(
                    "compliance.document",
                    ["active", "expiring_soon", "renewal_due", "under_renewal", "expired", "archived"],
                ),
            },
            {
                "id": "nc",
                "label": _("Non-Compliance"),
                "pairs": count_by_state(
                    "compliance.non.compliance",
                    ["open", "assigned", "in_progress", "pending_verification", "resolved", "closed"],
                ),
            },
            {
                "id": "regulatory",
                "label": _("Regulatory"),
                "pairs": count_by_state(
                    "compliance.regulatory.report",
                    ["draft", "in_preparation", "submitted"],
                ),
            },
        ]

        datasets = {
            "checks": {
                "model": "compliance.check",
                "date_field": "due_date",
                "order": "due_date asc, id desc",
                "fields": [
                    "name",
                    "reference",
                    "state",
                    "due_date",
                    "is_overdue",
                    "property_id",
                    "assigned_user_id",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_activities_ui",
                "label": _("Activities"),
            },
            "audits": {
                "model": "compliance.audit",
                "date_field": "date_planned",
                "order": "date_planned desc, id desc",
                "fields": [
                    "name",
                    "reference",
                    "kind",
                    "state",
                    "date_planned",
                    "is_overdue",
                    "property_id",
                    "assigned_user_id",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_audits_ui",
                "label": _("Audits & Inspections"),
            },
            "documents": {
                "model": "compliance.document",
                "date_field": "expiry_date",
                "order": "expiry_date asc, id desc",
                "fields": [
                    "name",
                    "document_type",
                    "state",
                    "expiry_date",
                    "property_id",
                    "issuing_authority",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_documents_ui",
                "label": _("Documents"),
            },
            "nc": {
                "model": "compliance.non.compliance",
                "date_field": "due_date",
                "order": "due_date asc, id desc",
                "fields": [
                    "name",
                    "reference",
                    "severity",
                    "state",
                    "due_date",
                    "is_overdue",
                    "property_id",
                    "assigned_user_id",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_nc_ui",
                "label": _("Non-Compliance"),
            },
            "actions": {
                "model": "compliance.action",
                "date_field": "deadline",
                "order": "deadline asc, id desc",
                "fields": [
                    "name",
                    "state",
                    "deadline",
                    "is_overdue",
                    "property_id",
                    "assigned_user_id",
                    "non_compliance_id",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_nc_ui",
                "label": _("Corrective Actions"),
            },
            "regulatory": {
                "model": "compliance.regulatory.report",
                "date_field": "deadline",
                "order": "deadline asc, id desc",
                "fields": [
                    "name",
                    "reference",
                    "regulatory_authority",
                    "state",
                    "deadline",
                    "is_overdue",
                    "property_id",
                    "owner_id",
                ],
                "action_xmlid": "compliance_audit_management.action_ca_regulatory_ui",
                "label": _("Regulatory"),
            },
        }
        meta = datasets.get(dataset) or datasets["checks"]
        Model = self.env[meta["model"]]
        domain = prop_domain() + date_domain(meta["date_field"])
        total = Model.search_count(domain)
        rows = Model.search(domain, order=meta["order"], offset=offset, limit=limit)
        records = []
        for rec in rows:
            when = getattr(rec, meta["date_field"], False)
            secondary = ""
            if getattr(rec, "reference", False):
                secondary = rec.reference
            elif getattr(rec, "regulatory_authority", False):
                secondary = rec.regulatory_authority
            elif getattr(rec, "issuing_authority", False):
                secondary = rec.issuing_authority
            elif getattr(rec, "non_compliance_id", False) and rec.non_compliance_id:
                secondary = rec.non_compliance_id.display_name
            elif getattr(rec, "kind", False):
                secondary = dict(rec._fields["kind"].selection).get(rec.kind, rec.kind)
            assignee = ""
            if getattr(rec, "assigned_user_id", False) and rec.assigned_user_id:
                assignee = rec.assigned_user_id.name
            elif getattr(rec, "owner_id", False) and rec.owner_id:
                assignee = rec.owner_id.name
            records.append(
                {
                    "id": rec.id,
                    "name": rec.name,
                    "secondary": secondary,
                    "state": rec.state,
                    "when": fields.Date.to_string(when) if when else False,
                    "property": rec.property_id.name if getattr(rec, "property_id", False) and rec.property_id else "",
                    "assignee": assignee,
                    "is_overdue": bool(getattr(rec, "is_overdue", False)),
                    "action_xmlid": meta["action_xmlid"],
                }
            )

        return {
            "as_of": fields.Date.to_string(today),
            "kpis": kpis,
            "health_by_category": dash["health_by_category"],
            "status_blocks": status_blocks,
            "dataset": dataset if dataset in datasets else "checks",
            "dataset_label": meta["label"],
            "total": total,
            "records": records,
            "datasets": [
                {"id": key, "label": value["label"]} for key, value in datasets.items()
            ],
        }
