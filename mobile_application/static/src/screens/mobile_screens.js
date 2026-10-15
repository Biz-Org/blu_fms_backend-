/** @odoo-module **/

import { Component } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { MOBILE_UI } from "@mobile_application/components/mobile_ui";
import { formatLabel, statusTone } from "@mobile_application/utils/format";

const UI = MOBILE_UI;

export class HomeScreen extends Component {
    static template = "mobile_application.HomeScreen";
    static components = { ...UI };
    static props = ["data", "modules", "role", "onRoute"];

    get canService() {
        return this.props.modules?.service_requests;
    }
    get canBooking() {
        return this.props.modules?.amenity_booking;
    }
    get canVisitor() {
        return this.props.modules?.visitor_management;
    }
    get canPayments() {
        return this.props.modules?.payments;
    }
    onRoute(route) {
        this.props.onRoute(route);
    }
}

export class ServicesScreen extends Component {
    static template = "mobile_application.ServicesScreen";
    static components = { ...UI };
    static props = ["modules", "onRoute"];

    get hasAnyService() {
        const m = this.props.modules || {};
        return Object.values(m).some(Boolean);
    }
    onRoute(route) {
        this.props.onRoute(route);
    }
}

export class AlertsScreen extends Component {
    static template = "mobile_application.AlertsScreen";
    static components = { ...UI };
    static props = ["items", "markAllRead", "openNote"];
}

export class ProfileScreen extends Component {
    static template = "mobile_application.ProfileScreen";
    static components = { ...UI };
    static props = ["profile", "modules", "pushConfigured", "onRoute"];

    logout() {
        browser.location.href = "/web/session/logout";
    }
    onRoute(route) {
        this.props.onRoute(route);
    }
}

export class VisitorsScreen extends Component {
    static template = "mobile_application.VisitorsScreen";
    static components = { ...UI };
    static props = ["items", "role", "onRoute", "openVisitor"];

    onRoute(route) {
        this.props.onRoute(route);
    }
}

export class GenericListScreen extends Component {
    static template = "mobile_application.GenericListScreen";
    static components = { ...UI };
    static props = {
        items: { type: Array, optional: true },
        unavailable: { type: Boolean, optional: true },
        message: { type: String, optional: true },
    };
}

export class FormScreen extends Component {
    static template = "mobile_application.FormScreen";
    static components = { ...UI };
    static props = ["state", "fields", "submit", "submitLabel", "busy"];
}

export class DigitalIdScreen extends Component {
    static template = "mobile_application.DigitalIdScreen";
    static components = { ...UI };
    static props = ["data"];
}

export class PaymentsScreen extends Component {
    static template = "mobile_application.PaymentsScreen";
    static components = { ...UI };
    static props = ["available", "balance", "items", "message", "providerConfigured"];

    get balanceDisplay() {
        return this.props.balance ?? 0;
    }
}

export function decorateRequests(items) {
    return (items || []).map((r) => ({
        ...r,
        stateLabel: formatLabel(r.state),
        stateTone: statusTone(r.state),
    }));
}

export function decorateVisitors(items) {
    return decorateRequests(items);
}
