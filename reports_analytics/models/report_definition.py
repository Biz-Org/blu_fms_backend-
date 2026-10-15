# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import REPORT_STATUSES, REPORT_TYPES, VISUALIZATIONS
from .utils import dumps_json, parse_json


class AnalyticsReportDefinition(models.Model):
    _name = "analytics.report"
    _description = "Analytics Report Definition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    report_type = fields.Selection(
        REPORT_TYPES,
        required=True,
        default="tabular",
        tracking=True,
        index=True,
    )
    source_module = fields.Char(
        string="Module / Source",
        required=True,
        index=True,
        tracking=True,
        default="reports_analytics",
        help="FMS module or logical source this report reads from.",
    )
    status = fields.Selection(
        REPORT_STATUSES,
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    description = fields.Html(sanitize=True)
    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        related="create_uid",
        store=True,
        readonly=True,
    )
    generated_date = fields.Datetime(
        readonly=True,
        help="Timestamp of the last successful report generation.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    data_source_id = fields.Many2one(
        "analytics.data.source",
        string="Primary Data Source",
        ondelete="set null",
        index=True,
    )
    data_source_ids = fields.Many2many(
        "analytics.data.source",
        "analytics_report_data_source_rel",
        "report_id",
        "source_id",
        string="Data Sources",
        help="Registered analytics sources used by this report definition.",
    )
    visualization = fields.Selection(VISUALIZATIONS, default="table", required=True)
    config_json = fields.Json(default=lambda self: {})
    execution_ids = fields.One2many(
        "analytics.report.execution",
        "report_id",
        string="Executions",
    )
    execution_count = fields.Integer(compute="_compute_execution_count")
    last_execution_id = fields.Many2one(
        "analytics.report.execution",
        compute="_compute_execution_count",
    )

    @api.depends("execution_ids", "execution_ids.status")
    def _compute_execution_count(self):
        for record in self:
            record.execution_count = len(record.execution_ids)
            record.last_execution_id = record.execution_ids[:1].id if record.execution_ids else False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.env["analytics.audit.log"].log_event(
                "create",
                _("Report created: %s") % record.name,
                report_id=record.id,
                related_module=record.source_module,
            )
        return records

    def write(self, vals):
        for record in self:
            if any(key in vals for key in ("name", "config_json", "status", "data_source_id", "visualization")):
                self.env["analytics.audit.log"].log_event(
                    "write",
                    _("Report updated: %s") % record.name,
                    report_id=record.id,
                    previous_value=dumps_json(record.config_json),
                    new_value=dumps_json(vals),
                    related_module=record.source_module,
                )
        return super().write(vals)

    def get_config(self):
        self.ensure_one()
        config = dict(parse_json(self.config_json, {}))
        config.setdefault("data_source_id", self.data_source_id.id)
        config.setdefault("visualization", self.visualization)
        config.setdefault("fields", [])
        config.setdefault("metrics", [])
        config.setdefault("grouping", [])
        config.setdefault("filters", {})
        config.setdefault("report_type", self.report_type)
        return config

    def ui_row(self):
        self.ensure_one()
        last = self.execution_ids[:1]
        return {
            "id": self.id,
            "name": self.name,
            "source_module": self.source_module,
            "report_type": self.report_type,
            "status": self.status,
            "visualization": self.visualization,
            "generated_date": fields.Datetime.to_string(self.generated_date) if self.generated_date else False,
            "created_by": self.created_by_id.name,
            "last_status": last.status if last else self.status,
            "execution_count": self.execution_count,
            "last_execution_id": last.id if last else False,
        }

    def ui_detail(self):
        self.ensure_one()
        payload = self.ui_row()
        payload["description"] = self.description or ""
        payload["config"] = self.get_config()
        payload["data_source_id"] = self.data_source_id.id
        last = self.execution_ids.filtered(lambda rec: rec.status == "success")[:1]
        payload["last_result"] = last.result_json if last else False
        return payload

    @api.model
    def action_preview_config(self, config):
        return self.env["analytics.query.engine"].execute_config(config, persist=False)

    @api.model
    def action_save_draft(self, vals, report_id=False):
        vals = vals or {}
        record = self.browse(report_id) if report_id else self.env["analytics.report"]
        payload = record._vals_from_builder(vals, status="draft")
        if record:
            record.write(payload)
        else:
            record = self.create(payload)
        return record.ui_detail()

    @api.model
    def action_generate(self, vals, report_id=False):
        vals = vals or {}
        record = self.browse(report_id) if report_id else self.env["analytics.report"]
        status = record.status if record and record.status != "archived" else "active"
        payload = record._vals_from_builder(vals, status=status)
        if record:
            record.write(payload)
        else:
            record = self.create(payload)
        execution = record._execute(output_format=vals.get("output_format") or "csv")
        return {
            "report": record.ui_detail(),
            "execution": execution.ui_payload(),
        }

    def _vals_from_builder(self, vals, status=None):
        config = parse_json(vals.get("config") or vals, {})
        source_id = config.get("data_source_id") or vals.get("data_source_id")
        source = self.env["analytics.data.source"].browse(source_id) if source_id else self.env["analytics.data.source"]
        result = {
            "name": vals.get("name") or (self.name if self else _("Untitled report")),
            "report_type": vals.get("report_type") or config.get("report_type") or "tabular",
            "description": vals.get("description") or (self.description if self else False),
            "visualization": config.get("visualization") or vals.get("visualization") or "table",
            "config_json": config,
            "data_source_id": source.id if source else False,
            "source_module": source.module if source else (vals.get("source_module") or "reports_analytics"),
        }
        if source:
            result["data_source_ids"] = [(6, 0, source.ids)]
        if status:
            result["status"] = status
        return result

    def _execute(self, output_format="csv", scheduled=False):
        self.ensure_one()
        started = fields.Datetime.now()
        execution = self.env["analytics.report.execution"].create({
            "report_id": self.id,
            "status": "running",
            "output_format": output_format,
            "user_id": self.env.user.id,
        })
        try:
            payload = self.env["analytics.query.engine"].execute_config(self.get_config(), persist=True)
            attachment = execution._store_output(payload, output_format)
            duration = int((fields.Datetime.now() - started).total_seconds() * 1000)
            execution.write({
                "status": "success" if payload.get("available") else "failed",
                "result_json": payload,
                "row_count": payload.get("row_count") or 0,
                "duration_ms": duration,
                "attachment_id": attachment.id if attachment else False,
                "error_message": "" if payload.get("available") else payload.get("reason"),
            })
            self.generated_date = fields.Datetime.now()
            if self.status == "draft":
                self.status = "scheduled" if scheduled else "active"
            self.env["analytics.audit.log"].log_event(
                "run",
                _("Report generated: %s") % self.name,
                report_id=self.id,
                related_module=self.source_module,
            )
        except Exception as exc:
            execution.write({
                "status": "failed",
                "error_message": str(exc),
                "duration_ms": int((fields.Datetime.now() - started).total_seconds() * 1000),
            })
            raise
        return execution

    def action_export_last(self, output_format="csv"):
        self.ensure_one()
        execution = self._execute(output_format=output_format)
        self.env["analytics.audit.log"].log_event(
            "export",
            _("Report exported (%s): %s") % (output_format, self.name),
            report_id=self.id,
        )
        return execution.ui_payload()

    def _register_hook(self):
        super()._register_hook()
        self._ensure_owl_launch()

    @api.model
    def _ensure_owl_launch(self):
        """Point the app home URL and root menu at the OWL dashboard client action."""
        owl = self.env.ref("reports_analytics.action_ra_dashboard", raise_if_not_found=False)
        native = self.env.ref("reports_analytics.action_analytics_report", raise_if_not_found=False)
        menu = self.env.ref("reports_analytics.menu_analytics_root", raise_if_not_found=False)
        if native and native.path == "analytics-reports":
            native.sudo().path = "analytics-report-definitions"
        if owl:
            if owl.path != "analytics-reports":
                owl.sudo().path = "analytics-reports"
            if menu and menu.action != owl:
                menu.sudo().action = f"{owl._name},{owl.id}"
