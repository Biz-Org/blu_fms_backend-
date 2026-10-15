# -*- coding: utf-8 -*-

from odoo import api, fields, models


class FireSafetyDashboard(models.AbstractModel):
    """Domain aggregation used by the Staff Dashboard (Stitch p1) and
    Compliance Reports (Stitch p12). OWL screens consume these methods;
    FMS Reports (#25) can wrap the same datasets.

    FUTURE / NOT IMPLEMENTED: PDF export polish.
    """

    _name = "fire.safety.dashboard"
    _description = "Fire & Safety Dashboard"

    @api.model
    def get_compliance_target(self, company=None):
        company = company or self.env.company
        ICP = self.env["ir.config_parameter"].sudo()
        key = f"fire_safety_management.compliance_target.{company.id}"
        value = ICP.get_param(key) or ICP.get_param(
            "fire_safety_management.compliance_target", "95"
        )
        try:
            return float(value)
        except (TypeError, ValueError):
            return 95.0

    @api.model
    def compute_compliance(self, company=None):
        """Weighted inspections + non-expired equipment + completed actions."""
        company = company or self.env.company
        domain_company = [("company_id", "=", company.id)]

        inspection_score = 100.0
        if self._fs_can_read("fire.safety.inspection"):
            inspections = self.env["fire.safety.inspection"].search(domain_company)
            closed_like = inspections.filtered(lambda rec: rec.state in ("completed", "closed"))
            inspection_score = (len(closed_like) / len(inspections) * 100.0) if inspections else 100.0

        equipment_score = 100.0
        if self._fs_can_read("fire.safety.equipment"):
            equipment = self.env["fire.safety.equipment"].search(
                domain_company + [("condition", "!=", "replaced")]
            )
            non_expired = equipment.filtered(lambda rec: rec.state != "expired")
            equipment_score = (len(non_expired) / len(equipment) * 100.0) if equipment else 100.0

        action_score = 100.0
        if self._fs_can_read("fire.safety.action"):
            actions = self.env["fire.safety.action"].search(domain_company)
            closed_actions = actions.filtered(lambda rec: rec.state == "closed")
            action_score = (len(closed_actions) / len(actions) * 100.0) if actions else 100.0

        result = (inspection_score * 0.4) + (equipment_score * 0.3) + (action_score * 0.3)
        return {
            "compliance": round(result, 2),
            "target": self.get_compliance_target(company),
            "inspection_score": round(inspection_score, 2),
            "equipment_score": round(equipment_score, 2),
            "action_score": round(action_score, 2),
        }

    @api.model
    def get_dashboard_data(self, company=None):
        company = company or self.env.company
        domain = [("company_id", "=", company.id)]
        overdue = 0
        if self._fs_can_read("fire.safety.inspection"):
            overdue = self.env["fire.safety.inspection"].search_count(
                domain + [("is_overdue", "=", True)]
            )
        now = fields.Datetime.now()
        return {
            "compliance": self.compute_compliance(company) if self._fs_can_read("fire.safety.inspection") else False,
            "inspection_counts": self._count_by_state("fire.safety.inspection", domain),
            "incident_counts": self._count_by_state("fire.safety.incident", domain),
            "drill_counts": self._count_by_state("fire.safety.drill", domain),
            "equipment_counts": self._count_by_state("fire.safety.equipment", domain),
            "emergency_counts": self._count_by_state("fire.safety.emergency", domain),
            "open_actions": self._safe_search_count(
                "fire.safety.action", domain + [("state", "!=", "closed")]
            ),
            "overdue_inspections": overdue,
            "recent_inspections": self._safe_search_read(
                "fire.safety.inspection",
                domain,
                ["name", "inspection_type", "state", "scheduled_date"],
                order="scheduled_date desc, id desc",
            ),
            "recent_incidents": self._safe_search_read(
                "fire.safety.incident",
                domain,
                ["name", "incident_type", "state", "incident_datetime"],
                order="incident_datetime desc, id desc",
            ),
            "upcoming_drills": self._safe_search_read(
                "fire.safety.drill",
                domain + [
                    ("state", "in", ("scheduled", "rescheduled")),
                    ("scheduled_datetime", ">=", now),
                ],
                ["name", "drill_type", "state", "scheduled_datetime"],
                order="scheduled_datetime asc, id asc",
            ),
        }

    def _fs_can_read(self, model_name):
        return model_name in self.env and self.env[model_name].has_access("read")

    def _safe_search_count(self, model_name, domain):
        if not self._fs_can_read(model_name):
            return 0
        return self.env[model_name].search_count(domain)

    def _safe_search_read(self, model_name, domain, fields, limit=5, order=None):
        if not self._fs_can_read(model_name):
            return []
        return self.env[model_name].search_read(domain, fields, limit=limit, order=order)

    def _count_by_state(self, model_name, domain):
        if not self._fs_can_read(model_name):
            return {}
        grouped = self.env[model_name]._read_group(domain, groupby=["state"], aggregates=["__count"])
        return {state: count for state, count in grouped if state}
