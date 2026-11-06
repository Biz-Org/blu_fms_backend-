# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class FacilityBookingController(http.Controller):
    @http.route("/facility_booking/receipt/<int:booking_id>", type="http", auth="user")
    def download_receipt(self, booking_id, **kwargs):
        booking = request.env["facility.booking"].browse(booking_id)
        if not booking.exists():
            return request.not_found()
        pdf, _ = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "facility_booking_management.action_facility_booking_report",
            booking.ids,
        )
        pdfhttpheaders = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf)),
            ("Content-Disposition", f"attachment; filename=Receipt-{booking.name}.pdf"),
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)
