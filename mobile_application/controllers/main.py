# -*- coding: utf-8 -*-

from odoo.http import Controller, request, route


class MobileApplicationController(Controller):
    def _service(self):
        return request.env["mobile.application.service"]

    @route("/mobile/api/capabilities", type="jsonrpc", auth="user", readonly=True)
    def capabilities(self):
        return self._service().get_capabilities()

    @route("/mobile/api/home", type="jsonrpc", auth="user", readonly=True)
    def home(self):
        return self._service().get_home()

    @route("/mobile/api/profile", type="jsonrpc", auth="user", readonly=True)
    def profile(self):
        return self._service().get_profile()

    @route("/mobile/api/sync", type="jsonrpc", auth="user")
    def sync(self, last_sync=None, idempotency_key=None):
        return self._service().sync(last_sync=last_sync, idempotency_key=idempotency_key)

    @route("/mobile/api/notifications", type="jsonrpc", auth="user", readonly=True)
    def notifications(self, limit=50, offset=0):
        return self._service().get_notifications(limit=limit, offset=offset)

    @route("/mobile/api/notifications/read", type="jsonrpc", auth="user")
    def notification_read(self, notification_id):
        return self._service().mark_notification_read(notification_id)

    @route("/mobile/api/notifications/read_all", type="jsonrpc", auth="user")
    def notifications_read_all(self):
        return self._service().mark_all_notifications_read()

    @route("/mobile/api/service_requests", type="jsonrpc", auth="user", readonly=True)
    def service_requests(self, state=None, limit=30):
        return self._service().list_service_requests(state=state, limit=limit)

    @route("/mobile/api/service_request/create", type="jsonrpc", auth="user")
    def service_request_create(self, category, description, idempotency_key=None, attachment_ids=None):
        return self._service().create_service_request(
            category, description, idempotency_key=idempotency_key, attachment_ids=attachment_ids
        )

    @route("/mobile/api/visitors", type="jsonrpc", auth="user", readonly=True)
    def visitors(self, scope="all", limit=30):
        return self._service().list_visitors(scope=scope, limit=limit)

    @route("/mobile/api/visitor/create", type="jsonrpc", auth="user")
    def visitor_create(self, payload, idempotency_key=None):
        return self._service().create_visitor(payload, idempotency_key=idempotency_key)

    @route("/mobile/api/visitor/action", type="jsonrpc", auth="user")
    def visitor_action(self, visitor_id, action):
        return self._service().visitor_action(visitor_id, action)

    @route("/mobile/api/bookings", type="jsonrpc", auth="user", readonly=True)
    def bookings(self, upcoming=True, limit=30):
        return self._service().list_bookings(upcoming=upcoming, limit=limit)

    @route("/mobile/api/booking/create", type="jsonrpc", auth="user")
    def booking_create(self, amenity_name, booking_date, slot_label, idempotency_key=None, notes=None):
        return self._service().create_booking(
            amenity_name, booking_date, slot_label, idempotency_key=idempotency_key, notes=notes
        )

    @route("/mobile/api/booking/cancel", type="jsonrpc", auth="user")
    def booking_cancel(self, booking_id):
        return self._service().cancel_booking(booking_id)

    @route("/mobile/api/payments", type="jsonrpc", auth="user", readonly=True)
    def payments(self):
        return self._service().get_payments()

    @route("/mobile/api/community", type="jsonrpc", auth="user", readonly=True)
    def community(self, section="home"):
        return self._service().get_community(section=section)

    @route("/mobile/api/digital_id", type="jsonrpc", auth="user", readonly=True)
    def digital_id(self):
        return self._service().get_digital_id()

    @route("/mobile/api/digital_id/verify", type="jsonrpc", auth="user")
    def digital_id_verify(self, token):
        return self._service().verify_digital_id(token)

    @route("/mobile/api/amenities", type="jsonrpc", auth="user", readonly=True)
    def amenities(self):
        return self._service().list_amenities()
