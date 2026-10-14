/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { MOBILE_UI } from "@mobile_application/components/mobile_ui";
import { MobileApi } from "@mobile_application/services/mobile_api";
import {
    AlertsScreen,
    DigitalIdScreen,
    FormScreen,
    GenericListScreen,
    HomeScreen,
    PaymentsScreen,
    ProfileScreen,
    ServicesScreen,
    VisitorsScreen,
    decorateRequests,
    decorateVisitors,
} from "@mobile_application/screens/mobile_screens";

const SCREENS = {
    home: HomeScreen,
    services: ServicesScreen,
    bookings: GenericListScreen,
    alerts: AlertsScreen,
    profile: ProfileScreen,
    visitors: VisitorsScreen,
    visitor_create: FormScreen,
    service_requests: GenericListScreen,
    helpdesk: GenericListScreen,
    community: GenericListScreen,
    amenity_booking: GenericListScreen,
    payments: PaymentsScreen,
    digital_id: DigitalIdScreen,
};

export class MobileApplication extends Component {
    static template = "mobile_application.MobileApplication";
    static components = { ...MOBILE_UI, ...SCREENS, HomeScreen, ServicesScreen, AlertsScreen, ProfileScreen, VisitorsScreen, GenericListScreen, FormScreen, DigitalIdScreen, PaymentsScreen };

    setup() {
        this.state = useState({
            loading: true,
            error: "",
            route: "home",
            tab: "home",
            capabilities: { role: "resident", modules: {} },
            home: null,
            profile: null,
            notifications: [],
            listItems: [],
            listMeta: {},
            digitalId: null,
            payments: null,
            form: {},
            busy: false,
            unread: 0,
            pushConfigured: false,
        });
        onWillStart(() => this.bootstrap());
    }

    async bootstrap() {
        try {
            const [caps, home, profile, sync] = await Promise.all([
                MobileApi.capabilities(),
                MobileApi.home(),
                MobileApi.profile(),
                MobileApi.sync({ idempotency_key: `boot-${Date.now()}` }),
            ]);
            this.state.capabilities = caps;
            this.state.home = home;
            this.state.profile = profile;
            this.state.unread = sync.unread_notifications || 0;
            this.state.pushConfigured = !!caps.push_configured;
            if (home.my_requests) {
                home.my_requests = decorateRequests(home.my_requests);
            }
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load Mobile Application.";
        } finally {
            this.state.loading = false;
        }
    }

    get role() {
        return this.state.capabilities.role || "resident";
    }

    get modules() {
        return this.state.capabilities.modules || {};
    }

    get subtitle() {
        if (!this.state.profile) {
            return "";
        }
        const parts = [this.state.profile.building, this.state.profile.unit].filter(Boolean);
        return parts.join(" · ");
    }

    get title() {
        const map = {
            home: "Home",
            services: "Services",
            bookings: this.role === "security" ? "Operations" : "Bookings",
            alerts: "Alerts",
            profile: "Profile",
            visitors: "Visitors",
            visitor_create: "Visitor Request",
            service_requests: "Service Requests",
            helpdesk: "Helpdesk",
            community: "Community",
            amenity_booking: "Amenity Booking",
            payments: "Wallet & Payments",
            digital_id: "Digital ID",
        };
        return map[this.state.route] || "Mobile";
    }

    get showBack() {
        return !["home", "services", "bookings", "alerts", "profile"].includes(this.state.route);
    }

    get hideNav() {
        return this.showBack && !["visitors", "service_requests", "community"].includes(this.state.route);
    }

    get Screen() {
        if (this.state.route === "home") {
            return HomeScreen;
        }
        if (this.state.route === "services") {
            return ServicesScreen;
        }
        if (this.state.route === "alerts") {
            return AlertsScreen;
        }
        if (this.state.route === "profile") {
            return ProfileScreen;
        }
        if (this.state.route === "visitors") {
            return VisitorsScreen;
        }
        if (this.state.route === "digital_id") {
            return DigitalIdScreen;
        }
        if (this.state.route === "payments") {
            return PaymentsScreen;
        }
        if (this.state.route === "visitor_create") {
            return FormScreen;
        }
        return GenericListScreen;
    }

    get screenProps() {
        const route = this.state.route;
        if (route === "home") {
            return {
                data: this.state.home || { greeting: "Hello", profile: this.state.profile || {}, important_updates: [], my_requests: [] },
                modules: this.modules,
                role: this.role,
                onRoute: (r) => this.navigate(r),
            };
        }
        if (route === "services") {
            return { modules: this.modules, onRoute: (r) => this.navigate(r) };
        }
        if (route === "alerts") {
            return {
                items: this.state.notifications,
                markAllRead: () => this.markAllRead(),
                openNote: (note) => this.openNote(note),
            };
        }
        if (route === "profile") {
            return {
                profile: { ...this.state.profile, role: this.role },
                modules: this.modules,
                pushConfigured: this.state.pushConfigured,
                onRoute: (r) => this.navigate(r),
            };
        }
        if (route === "visitors") {
            return {
                items: decorateVisitors(this.state.listItems),
                role: this.role,
                onRoute: (r) => this.navigate(r),
                openVisitor: () => {},
            };
        }
        if (route === "digital_id") {
            return { data: this.state.digitalId || {} };
        }
        if (route === "payments") {
            const p = this.state.payments || {};
            return {
                available: p.available,
                balance: p.balance,
                items: decorateRequests(p.items || []),
                message: p.message,
                providerConfigured: p.provider_configured,
            };
        }
        if (route === "visitor_create") {
            return {
                state: this.state,
                fields: [
                    { name: "name", label: "Visitor name", placeholder: "Full name" },
                    { name: "phone", label: "Phone", placeholder: "Phone number" },
                    { name: "purpose", label: "Purpose", placeholder: "Purpose of visit" },
                    { name: "expected_start", label: "Expected arrival", type: "datetime-local" },
                    { name: "notes", label: "Notes", type: "textarea" },
                ],
                submit: () => this.submitVisitor(),
                submitLabel: "Submit request",
                busy: this.state.busy,
            };
        }
        return {
            items: this.state.listItems,
            unavailable: this.state.listMeta.unavailable,
            message: this.state.listMeta.message,
        };
    }

    async navigate(route) {
        this.state.route = route;
        if (["home", "services", "bookings", "alerts", "profile"].includes(route)) {
            this.state.tab = route;
        }
        this.state.loading = true;
        try {
            await this.loadRoute(route);
        } finally {
            this.state.loading = false;
        }
    }

    onTab(tab) {
        this.navigate(tab);
    }

    onBack() {
        this.navigate(this.state.tab || "home");
    }

    onAlerts() {
        this.navigate("alerts");
    }

    async loadRoute(route) {
        if (route === "alerts") {
            const data = await MobileApi.notifications({});
            this.state.notifications = data.items || [];
            this.state.unread = data.unread || 0;
        } else if (route === "visitors" || route === "bookings") {
            const scope = route === "bookings" && this.role === "security" ? "pending_approval" : "upcoming";
            if (route === "bookings" && this.role !== "security") {
                const data = await MobileApi.bookings({});
                this.state.listItems = (data.items || []).map((b) => ({
                    id: b.id,
                    title: b.amenity_name,
                    subtitle: `${b.booking_date} · ${b.slot_label}`,
                    state: b.state,
                }));
                this.state.listMeta = { unavailable: !data.available };
            } else if (route === "bookings") {
                const data = await MobileApi.visitors({ scope: "pending_approval" });
                this.state.listItems = decorateVisitors(data.items || []);
            } else {
                const data = await MobileApi.visitors({});
                this.state.listItems = data.items || [];
            }
        } else if (route === "service_requests") {
            const data = await MobileApi.serviceRequests({});
            this.state.listItems = (data.items || []).map((r) => ({
                id: r.id,
                title: r.name,
                subtitle: r.category,
                state: r.state,
            }));
            this.state.listMeta = { unavailable: data.available === false, message: data.message };
        } else if (route === "helpdesk") {
            this.state.listItems = [];
            this.state.listMeta = { unavailable: !this.modules.helpdesk, message: "Helpdesk module is not installed." };
        } else if (route === "community") {
            const data = await MobileApi.community({ section: "announcements" });
            this.state.listItems = (data.items || []).map((a) => ({
                id: a.id,
                title: a.title,
                subtitle: a.date,
            }));
            this.state.listMeta = { unavailable: !data.available, message: "Community module is not installed." };
        } else if (route === "amenity_booking") {
            const data = await MobileApi.amenities();
            this.state.listItems = data.items || [];
            this.state.listMeta = {
                unavailable: !data.available,
                message: data.message || "No amenities configured.",
            };
        } else if (route === "payments") {
            this.state.payments = await MobileApi.payments();
        } else if (route === "digital_id") {
            this.state.digitalId = await MobileApi.digitalId();
        } else if (route === "home") {
            this.state.home = await MobileApi.home();
            if (this.state.home.my_requests) {
                this.state.home.my_requests = decorateRequests(this.state.home.my_requests);
            }
        }
    }

    async markAllRead() {
        await MobileApi.markAllRead();
        await this.loadRoute("alerts");
    }

    async openNote(note) {
        if (!note.is_read) {
            await MobileApi.markRead(note.id);
        }
        if (note.action_route) {
            this.navigate(note.action_route);
        }
    }

    async submitVisitor() {
        this.state.busy = true;
        try {
            const key = `visitor-${Date.now()}`;
            await MobileApi.createVisitor({
                payload: { ...this.state.form },
                idempotency_key: key,
            });
            this.state.form = {};
            await this.navigate("visitors");
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("mobile_application.action_mobile_app", MobileApplication);
