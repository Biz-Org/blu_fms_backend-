/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

export async function mobileRpc(route, params = {}) {
    return rpc(route, params);
}

export const MobileApi = {
    capabilities: () => mobileRpc("/mobile/api/capabilities"),
    home: () => mobileRpc("/mobile/api/home"),
    profile: () => mobileRpc("/mobile/api/profile"),
    sync: (params) => mobileRpc("/mobile/api/sync", params),
    notifications: (params) => mobileRpc("/mobile/api/notifications", params),
    markRead: (notification_id) => mobileRpc("/mobile/api/notifications/read", { notification_id }),
    markAllRead: () => mobileRpc("/mobile/api/notifications/read_all"),
    serviceRequests: (params) => mobileRpc("/mobile/api/service_requests", params),
    createServiceRequest: (params) => mobileRpc("/mobile/api/service_request/create", params),
    visitors: (params) => mobileRpc("/mobile/api/visitors", params),
    createVisitor: (params) => mobileRpc("/mobile/api/visitor/create", params),
    visitorAction: (params) => mobileRpc("/mobile/api/visitor/action", params),
    bookings: (params) => mobileRpc("/mobile/api/bookings", params),
    createBooking: (params) => mobileRpc("/mobile/api/booking/create", params),
    cancelBooking: (booking_id) => mobileRpc("/mobile/api/booking/cancel", { booking_id }),
    payments: () => mobileRpc("/mobile/api/payments"),
    community: (params) => mobileRpc("/mobile/api/community", params),
    digitalId: () => mobileRpc("/mobile/api/digital_id"),
    verifyDigitalId: (token) => mobileRpc("/mobile/api/digital_id/verify", { token }),
    amenities: () => mobileRpc("/mobile/api/amenities"),
};
