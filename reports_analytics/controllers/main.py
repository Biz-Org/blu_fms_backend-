# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.tools.translate import _


class ReportsAnalyticsController(http.Controller):
    @http.route(
        "/reports_analytics/execution/<int:execution_id>/export",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def export_execution(self, execution_id, export_format="csv", **kwargs):
        execution = request.env["analytics.report.execution"].browse(execution_id)
        if not execution.exists():
            raise MissingError(_("Execution not found."))
        if not execution.has_access("read"):
            raise AccessError(_("You cannot export this report."))
        payload = execution.result_json or {}
        if not payload:
            payload = request.env["analytics.query.engine"].execute_config(
                execution.report_id.get_config(), persist=True
            )
        if not execution.attachment_id or execution.output_format != export_format:
            execution.output_format = export_format
            attachment = execution._store_output(payload, export_format)
            if attachment:
                execution.attachment_id = attachment.id
        request.env["analytics.audit.log"].log_event(
            "export",
            _("Exported %s") % execution.report_id.name,
            report_id=execution.report_id.id,
        )
        attachment = execution.attachment_id
        if not attachment:
            return request.make_response(_("No Data"), headers=[("Content-Type", "text/plain")])
        return request.make_response(
            attachment.raw,
            headers=[
                ("Content-Type", attachment.mimetype or "application/octet-stream"),
                ("Content-Disposition", f"attachment; filename={attachment.name}"),
            ],
        )
