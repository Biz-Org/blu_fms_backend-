# -*- coding: utf-8 -*-

import base64
import csv
import io

from odoo import fields, models
from odoo.tools.translate import _

from .constants import EXECUTION_STATUSES, OUTPUT_FORMATS


class AnalyticsReportExecution(models.Model):
    _name = "analytics.report.execution"
    _description = "Analytics Report Execution History"
    _order = "execution_datetime desc, id desc"
    _check_company_auto = True

    report_id = fields.Many2one(
        "analytics.report",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    execution_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    status = fields.Selection(
        EXECUTION_STATUSES,
        required=True,
        default="pending",
        index=True,
    )
    duration_ms = fields.Integer(
        string="Duration (ms)",
        help="Execution duration in milliseconds when available.",
    )
    error_message = fields.Text(readonly=True)
    company_id = fields.Many2one(
        related="report_id.company_id",
        store=True,
        index=True,
    )
    output_format = fields.Selection(OUTPUT_FORMATS, default="csv")
    result_json = fields.Json()
    row_count = fields.Integer()
    attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    schedule_id = fields.Many2one("analytics.report.schedule", ondelete="set null", index=True)

    def ui_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "report_id": self.report_id.id,
            "report_name": self.report_id.name,
            "status": self.status,
            "execution_datetime": fields.Datetime.to_string(self.execution_datetime),
            "duration_ms": self.duration_ms,
            "error_message": self.error_message or "",
            "output_format": self.output_format,
            "row_count": self.row_count,
            "attachment_id": self.attachment_id.id if self.attachment_id else False,
            "download_url": f"/reports_analytics/execution/{self.id}/export?export_format={self.output_format}" if self.id else False,
            "result": self.result_json or {},
        }

    def _store_output(self, payload, output_format):
        self.ensure_one()
        output_format = output_format or "csv"
        name = f"{self.report_id.name or 'report'}-{self.id or 'preview'}"
        datas = False
        mimetype = "text/csv"
        filename = f"{name}.csv"
        if output_format == "csv":
            datas, filename, mimetype = self._to_csv(payload, name)
        elif output_format == "xlsx":
            datas, filename, mimetype = self._to_xlsx(payload, name)
        elif output_format == "pdf":
            datas, filename, mimetype = self._to_pdf(payload, name)
        if not datas:
            return self.env["ir.attachment"]
        return self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": datas,
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": mimetype,
        })

    def _to_csv(self, payload, name):
        buffer = io.StringIO()
        columns = payload.get("columns") or []
        fieldnames = [col["name"] for col in columns] or ["message"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        rows = payload.get("rows") or []
        if not rows:
            writer.writerow({fieldnames[0]: payload.get("reason") or "No Data"})
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
        encoded = base64.b64encode(buffer.getvalue().encode("utf-8"))
        return encoded, f"{name}.csv", "text/csv"

    def _to_xlsx(self, payload, name):
        try:
            import xlsxwriter
        except ImportError:
            return self._to_csv(payload, name)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Report")
        columns = payload.get("columns") or [{"name": "message", "label": "Message"}]
        for index, col in enumerate(columns):
            sheet.write(0, index, col.get("label") or col.get("name"))
        rows = payload.get("rows") or []
        if not rows:
            sheet.write(1, 0, payload.get("reason") or "No Data")
        for r_index, row in enumerate(rows, start=1):
            for c_index, col in enumerate(columns):
                sheet.write(r_index, c_index, row.get(col["name"], ""))
        workbook.close()
        encoded = base64.b64encode(output.getvalue())
        return encoded, f"{name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _to_pdf(self, payload, name):
        self.result_json = payload
        try:
            pdf, _unused = self.env["ir.actions.report"]._render_qweb_pdf(
                "reports_analytics.action_report_execution_pdf",
                res_ids=self.ids,
            )
            encoded = base64.b64encode(pdf)
            return encoded, f"{name}.pdf", "application/pdf"
        except Exception:
            return self._to_csv(payload, name)
