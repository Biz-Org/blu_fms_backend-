# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .source_catalog import KNOWN_SOURCES


class AnalyticsDataSource(models.Model):
    _name = "analytics.data.source"
    _description = "Analytics Data Source Registry"
    _order = "module, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Human-readable name of the analytics data source.",
    )
    technical_identifier = fields.Char(
        required=True,
        index=True,
        help="Stable technical key used by report and KPI definitions.",
    )
    model_name = fields.Char(
        string="Model",
        index=True,
        help="Odoo model technical name when the source maps to a single model.",
    )
    module = fields.Char(
        required=True,
        index=True,
        help="Source FMS module technical name (e.g. fire_safety_management).",
    )
    category = fields.Char(index=True)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    is_available = fields.Boolean(compute="_compute_availability")
    availability_reason = fields.Char(compute="_compute_availability")

    _sql_constraints = [
        (
            "analytics_data_source_technical_identifier_uniq",
            "unique(technical_identifier)",
            _("The technical identifier must be unique."),
        ),
    ]

    @api.depends("model_name", "module", "active")
    def _compute_availability(self):
        for record in self:
            available, reason = record._availability()
            record.is_available = available
            record.availability_reason = reason

    def _availability(self):
        self.ensure_one()
        if not self.active:
            return False, _("Inactive")
        if not self.model_name:
            return False, _("No model mapped")
        if self.model_name not in self.env:
            return False, _("Source module is not installed")
        if not self.env[self.model_name].has_access("read"):
            return False, _("No permission to read this source")
        return True, ""

    def get_model(self):
        self.ensure_one()
        available, reason = self._availability()
        if not available:
            return False
        return self.env[self.model_name]

    @api.model
    def _sync_known_sources(self):
        for spec in KNOWN_SOURCES:
            existing = self.search([("technical_identifier", "=", spec["technical_identifier"])], limit=1)
            vals = {
                "name": spec["name"],
                "model_name": spec["model_name"],
                "module": spec["module"],
                "category": spec.get("category"),
                "description": spec.get("description"),
            }
            if existing:
                existing.write({k: v for k, v in vals.items() if existing[k] != v})
            else:
                self.create({"technical_identifier": spec["technical_identifier"], **vals})
        return True

    @api.model
    def get_registry_payload(self):
        self._sync_known_sources()
        rows = []
        for source in self.search([("active", "=", True)]):
            available, reason = source._availability()
            rows.append({
                "id": source.id,
                "name": source.name,
                "technical_identifier": source.technical_identifier,
                "model_name": source.model_name,
                "module": source.module,
                "category": source.category or "",
                "available": available,
                "reason": reason,
                "description": source.description or "",
            })
        return rows
