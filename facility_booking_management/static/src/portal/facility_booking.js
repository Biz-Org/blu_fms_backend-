/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// =============================================================================
// SECTION: RPC / ORM service
// =============================================================================

class FbmService {
    constructor(env) {
        this.orm = env.services.orm;
    }

    getUserContext() {
        return this.orm.call("facility.booking", "get_user_context", []);
    }

    searchProperties(domain, limit, offset, search) {
        return this.orm.call("fms.property", "search_properties", [], {
            domain,
            limit,
            offset,
            search: search || false,
        });
    }

    saveProperty(values, propertyId) {
        return this.orm.call("fms.property", "save_property_from_ui", [], {
            values,
            property_id: propertyId || false,
        });
    }

    getDashboard(filters) {
        return this.orm.call("facility.booking", "get_dashboard_data", [], filters || {});
    }

    searchFacilities(domain, limit, offset) {
        return this.orm.call("facility.facility", "search_facilities", [], { domain, limit, offset });
    }

    saveFacility(values, facilityId) {
        return this.orm.call("facility.facility", "save_facility_from_ui", [], {
            values,
            facility_id: facilityId || false,
        });
    }

    getAvailability(facilityId, date) {
        return this.orm.call("facility.facility", "get_availability", [], {
            facility_id: facilityId,
            date,
        });
    }

    searchSlotConfigs(facilityId) {
        return this.orm.call("facility.slot.config", "search_slot_configs", [], {
            facility_id: facilityId || false,
        });
    }

    saveSlotConfig(values, configId) {
        return this.orm.call("facility.slot.config", "save_slot_config_from_ui", [], {
            values,
            config_id: configId || false,
        });
    }

    searchBookings(domain, limit, offset, order) {
        return this.orm.call("facility.booking", "search_bookings", [], {
            domain,
            limit,
            offset,
            order,
        });
    }

    createBooking(values) {
        return this.orm.call("facility.booking", "create_booking_from_ui", [], { values });
    }

    approveBooking(id, comment) {
        return this.orm.call("facility.booking", "action_approve", [[id]], { comment });
    }

    rejectBooking(id, comment) {
        return this.orm.call("facility.booking", "action_reject", [[id]], { comment });
    }

    cancelBooking(id, reason) {
        return this.orm.call("facility.booking", "action_cancel", [[id]], { reason });
    }

    confirmPayment(id, amount, paymentMethod, transactionId) {
        return this.orm.call("facility.booking", "action_confirm_payment", [[id]], {
            amount,
            payment_method: paymentMethod,
            transaction_id: transactionId || false,
        });
    }

    searchBlocks(domain) {
        return this.orm.call("facility.block", "search_blocks", [], { domain });
    }

    saveBlock(values, blockId) {
        return this.orm.call("facility.block", "save_block_from_ui", [], {
            values,
            block_id: blockId || false,
        });
    }

    getCalendarEvents(params) {
        return this.orm.call("facility.booking", "get_calendar_events", [], params);
    }

    getReports(params) {
        return this.orm.call("facility.booking", "get_reports_data", [], params || {});
    }

    getUtilization(params) {
        return this.orm.call("facility.booking", "get_utilization_analytics", [], params || {});
    }

    getPaymentSummary(propertyId) {
        return this.orm.call("facility.booking.config", "get_payment_summary", [], {
            property_id: propertyId || false,
        });
    }

    getConfig() {
        return this.orm.call("facility.booking.config", "get_config_payload", []);
    }

    saveConfig(values) {
        return this.orm.call("facility.booking.config", "save_config_payload", [], { values });
    }

    getNotifications(params) {
        return this.orm.call("facility.booking.notification", "get_notifications", [], params || {});
    }

    markNotificationRead(id) {
        return this.orm.call("facility.booking.notification", "action_mark_read", [[id]]);
    }

    markAllNotificationsRead() {
        return this.orm.call("facility.booking.notification", "action_mark_all_read", []);
    }
}


registry.category("services").add("fbm", {
    dependencies: ["orm"],
    start(env) {
        return new FbmService(env);
    },
});

// =============================================================================
// SECTION: Shared components, screens, and application shell
// =============================================================================

// --- Reusable UI components ---

class FbmKpiCard extends Component {
    static template = "facility_booking_management.FbmKpiCard";
    static props = ["icon", "value", "label"];
}

class FbmStatusBadge extends Component {
    static template = "facility_booking_management.FbmStatusBadge";
    static props = ["status", "label?"];
}

class FbmDataTable extends Component {
    static template = "facility_booking_management.FbmDataTable";
    static props = {
        columns: Array,
        rows: Array,
        actions: { type: Boolean, optional: true },
        onRowAction: { type: Function, optional: true },
    };
}

class FbmSidebar extends Component {
    static template = "facility_booking_management.FbmSidebar";
    static props = {
        mainItems: Array,
        active: String,
        onNavigate: Function,
    };
}

class FbmTopbar extends Component {
    static template = "facility_booking_management.FbmTopbar";
    static props = ["title", "breadcrumb", "userName"];
}

const FBM_NAV_ITEMS = [
    { id: "dashboard", label: "Dashboard" },
    { id: "properties", label: "Properties" },
    { id: "facilities", label: "Facilities" },
    { id: "availability", label: "Facility Availability" },
    { id: "time_slots", label: "Time Slots" },
    { id: "booking_management", label: "Booking Management" },
    { id: "approval_center", label: "Approval Center" },
    { id: "create_booking", label: "Create Booking" },
    { id: "my_bookings", label: "My Bookings" },
    { id: "booking_history", label: "Booking History" },
    { id: "facility_blocking", label: "Facility Blocking" },
    { id: "facility_calendar", label: "Facility Calendar" },
    { id: "payments", label: "Payment & Charges" },
    { id: "reports", label: "Reports & Revenue" },
    { id: "notifications", label: "Notifications & Alerts" },
];

const FBM_SCREEN_META = {
    dashboard: { title: "Facility Booking Dashboard", breadcrumb: "Home / Dashboard" },
    properties: { title: "Property Management", breadcrumb: "Home / Properties" },
    facilities: { title: "Facility Master", breadcrumb: "Home / Facilities" },
    availability: { title: "Facility Availability", breadcrumb: "Home / Availability" },
    time_slots: { title: "Time Slot Management", breadcrumb: "Home / Time Slots" },
    booking_management: { title: "Booking Management", breadcrumb: "Home / Bookings" },
    booking_detail: { title: "Booking Details", breadcrumb: "Home / Bookings / Details" },
    approval_center: { title: "Approval Center", breadcrumb: "Home / Approvals" },
    create_booking: { title: "Create Booking", breadcrumb: "Home / Create Booking" },
    my_bookings: { title: "My Bookings", breadcrumb: "Home / My Bookings" },
    booking_history: { title: "Booking History", breadcrumb: "Home / History" },
    facility_blocking: { title: "Facility Blocking", breadcrumb: "Home / Blocking" },
    facility_calendar: { title: "Facility Calendar", breadcrumb: "Home / Calendar" },
    payments: { title: "Payment & Charges", breadcrumb: "Home / Payments" },
    reports: { title: "Reports & Revenue", breadcrumb: "Home / Reports" },
    notifications: { title: "Notifications & Alerts", breadcrumb: "Home / Notifications" },
    settings: { title: "Settings & Configuration", breadcrumb: "Home / Settings" },
};

class FbmDashboardScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ loading: true, data: null, propertyId: "" });
        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.fbm.getDashboard({
            property_id: this.state.propertyId ? parseInt(this.state.propertyId) : false,
        });
        this.state.loading = false;
    }

    static components = { FbmKpiCard, FbmDataTable, FbmStatusBadge };
    static template = "facility_booking_management.FbmDashboardScreen";
    upcomingCols = [
        { key: "name", label: "Booking ID" },
        { key: "facility_name", label: "Facility" },
        { key: "booking_date", label: "Date" },
        { key: "booking_status", label: "Status", type: "badge" },
    ];
    static props = ["context", "onNavigate", "onOpenBooking"];
}

class FbmPropertiesScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({
            rows: [],
            selected: null,
            search: "",
            form: {},
            message: "",
        });
        onWillStart(async () => {
            await this.load();
            if (!this.props.context.can_manage_properties && this.state.rows.length === 1) {
                this.selectRow(this.state.rows[0]);
            }
        });
    }

    async load() {
        const result = await this.fbm.searchProperties([], 200, 0, this.state.search || false);
        this.state.rows = result.records;
    }

    selectRow(row) {
        this.state.selected = row;
        this.state.form = { ...row };
        this.state.message = "";
    }

    startCreate() {
        this.state.selected = { id: null };
        this.state.form = { active: true, name: "", code: "", building: "", city: "", address: "" };
        this.state.message = "";
    }

    async save() {
        if (!this.props.context.can_manage_properties) {
            return;
        }
        try {
            const id = this.state.form.id;
            const values = { ...this.state.form };
            delete values.id;
            delete values.manager_names;
            delete values.resident_count;
            delete values.manager_ids;
            await this.fbm.saveProperty(values, id);
            this.state.message = "Property saved.";
            await this.load();
            if (this.props.onContextRefresh) {
                await this.props.onContextRefresh();
            }
        } catch (e) {
            this.state.message = e.message || "Failed to save property.";
        }
    }

    static components = { FbmDataTable };
    static template = "facility_booking_management.FbmPropertiesScreen";
    cols = [
        { key: "code", label: "Code" },
        { key: "name", label: "Property" },
        { key: "building", label: "Building" },
        { key: "city", label: "City" },
        { key: "resident_count", label: "Residents" },
        { key: "active", label: "Active" },
    ];
    static props = ["context", "onContextRefresh"];
}

class FbmFacilitiesScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({
            rows: [],
            selected: null,
            search: "",
            form: {},
            message: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        const domain = this.state.search ? [["name", "ilike", this.state.search]] : [];
        const result = await this.fbm.searchFacilities(domain, 100, 0);
        this.state.rows = result.records;
    }

    selectRow(row) {
        this.state.selected = row;
        this.state.form = { ...row };
        this.state.message = "";
    }

    startCreate() {
        const types = this.props.context.facility_types || [];
        const properties = this.props.context.properties || [];
        this.state.selected = { id: null };
        this.state.form = {
            active: true,
            charge_type: "free",
            booking_status: "open",
            booking_type: "slot",
            capacity: 1,
            name: "",
            facility_type_id: types.length ? types[0].id : false,
            property_id: properties.length ? properties[0].id : false,
        };
        this.state.message = "";
    }

    async save() {
        try {
            const id = this.state.form.id;
            const values = { ...this.state.form };
            delete values.id;
            delete values.facility_type_name;
            delete values.property_name;
            delete values.availability_status;
            if (!values.name || !String(values.name).trim()) {
                this.state.message = "Facility name is required.";
                return;
            }
            if (!values.facility_type_id) {
                this.state.message = "Please select a facility type.";
                return;
            }
            values.facility_type_id = parseInt(values.facility_type_id);
            if (values.property_id) {
                values.property_id = parseInt(values.property_id);
            } else {
                delete values.property_id;
            }
            if (values.capacity !== undefined && values.capacity !== "") {
                values.capacity = parseInt(values.capacity);
            }
            await this.fbm.saveFacility(values, id);
            this.state.message = "Facility saved.";
            await this.load();
        } catch (e) {
            this.state.message = e.message || "Failed to save facility.";
        }
    }

    static components = { FbmDataTable, FbmStatusBadge };
    static template = "facility_booking_management.FbmFacilitiesScreen";
    cols = [
        { key: "code", label: "ID" },
        { key: "name", label: "Facility" },
        { key: "facility_type_name", label: "Type" },
        { key: "property_name", label: "Property" },
        { key: "capacity", label: "Capacity" },
        { key: "charge_type", label: "Paid/Free" },
    ];
    static props = ["context", "onNavigate", "onOpenBooking"];
}

class FbmAvailabilityScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.bookSlot = this.bookSlot.bind(this);
        this.state = useState({
            facilityId: "",
            date: new Date().toISOString().slice(0, 10),
            data: null,
        });
    }

    async check() {
        if (!this.state.facilityId) return;
        this.state.data = await this.fbm.getAvailability(parseInt(this.state.facilityId), this.state.date);
    }

    bookSlot(slot) {
        if (slot.status !== "available") return;
        this.props.onNavigate("create_booking", {
            facility_id: parseInt(this.state.facilityId),
            booking_date: this.state.date,
            start_time: slot.start_time,
            end_time: slot.end_time,
        });
    }

    static template = "facility_booking_management.FbmAvailabilityScreen";
    static components = { FbmStatusBadge };
    static props = ["facilities", "onNavigate"];
}

class FbmBookingsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ rows: [], statusFilter: "" });
        onWillStart(() => this.load());
    }

    async load() {
        const domain = [];
        if (this.props.domain && this.props.domain.length) {
            domain.push(...this.props.domain);
        }
        if (this.state.statusFilter) domain.push(["booking_status", "=", this.state.statusFilter]);
        const result = await this.fbm.searchBookings(domain, 100, 0);
        this.state.rows = result.records;
    }

    static components = { FbmDataTable };
    static template = "facility_booking_management.FbmBookingsScreen";
    cols = [
        { key: "name", label: "Booking ID" },
        { key: "facility_name", label: "Facility" },
        { key: "resident_name", label: "Requester" },
        { key: "booking_date", label: "Date" },
        { key: "start_label", label: "Start" },
        { key: "end_label", label: "End" },
        { key: "total_amount", label: "Amount" },
        { key: "payment_status", label: "Payment", type: "badge" },
        { key: "approval_status", label: "Approval", type: "badge" },
        { key: "booking_status", label: "Status", type: "badge" },
    ];
    static props = {
        domain: { type: Array, optional: true },
        onOpenBooking: Function,
    };
}

class FbmBookingDetailScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ booking: null, rejectComment: "", payAmount: 0, payMethod: "cash", txnId: "" });
        onWillStart(() => this.load());
    }

    async load() {
        const result = await this.fbm.searchBookings([["id", "=", this.props.bookingId]], 1, 0);
        this.state.booking = result.records[0];
    }

    async approve() {
        await this.fbm.approveBooking(this.props.bookingId, "");
        await this.load();
    }

    async reject() {
        if (!this.state.rejectComment) return;
        await this.fbm.rejectBooking(this.props.bookingId, this.state.rejectComment);
        await this.load();
    }

    async cancel() {
        await this.fbm.cancelBooking(this.props.bookingId, "Cancelled by user");
        await this.load();
    }

    async confirmPayment() {
        await this.fbm.confirmPayment(
            this.props.bookingId,
            parseFloat(this.state.payAmount),
            this.state.payMethod,
            this.state.txnId
        );
        await this.load();
    }

    receiptUrl() {
        return `/facility_booking/receipt/${this.props.bookingId}`;
    }

    static template = "facility_booking_management.FbmBookingDetailScreen";
    static components = { FbmStatusBadge };
    static props = ["bookingId", "context"];
}

class FbmCreateBookingScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({
            step: 1,
            form: {
                guest_count: 1,
                ...(this.props.initial || {}),
            },
            slots: [],
            message: "",
        });
    }

    async loadSlots() {
        if (!this.state.form.facility_id || !this.state.form.booking_date) return;
        const data = await this.fbm.getAvailability(
            parseInt(this.state.form.facility_id),
            this.state.form.booking_date
        );
        this.state.slots = data.slots || [];
    }

    selectSlot(slot) {
        this.state.form.start_time = slot.start_time;
        this.state.form.end_time = slot.end_time;
    }

    async submit() {
        try {
            const values = { ...this.state.form };
            ["facility_id", "property_id", "resident_id", "guest_count"].forEach((k) => {
                if (values[k]) values[k] = parseInt(values[k]);
            });
            const booking = await this.fbm.createBooking(values);
            this.state.message = `Booking ${booking.name} created.`;
            this.props.onOpenBooking(booking.id);
        } catch (e) {
            this.state.message = e.message || "Failed to create booking.";
        }
    }

    static template = "facility_booking_management.FbmCreateBookingScreen";
    static props = ["context", "facilities", "initial", "onOpenBooking"];
}

class FbmGenericTableScreen extends Component {
    static components = { FbmDataTable, FbmKpiCard };
    static props = ["title", "kpis", "columns", "rows", "toolbar", "onOpenBooking"];
    static template = "facility_booking_management.FbmGenericTableScreen";
}

class FbmTimeSlotsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ configs: [], facilityId: "", form: {} });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.configs = await this.fbm.searchSlotConfigs(
            this.state.facilityId ? parseInt(this.state.facilityId) : false
        );
    }

    edit(config) {
        this.state.form = { ...config };
    }

    async save() {
        const id = this.state.form.id;
        const values = { ...this.state.form };
        delete values.id;
        delete values.facility_name;
        delete values.opening_label;
        delete values.closing_label;
        delete values.working_day_names;
        if (values.facility_id) values.facility_id = parseInt(values.facility_id);
        await this.fbm.saveSlotConfig(values, id);
        this.state.form = {};
        await this.load();
    }

    static template = "facility_booking_management.FbmTimeSlotsScreen";
    static props = ["context", "facilities"];
}

class FbmBlockingScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ rows: [], form: { all_day: true, state: "active", block_reason: "maintenance" } });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.rows = await this.fbm.searchBlocks([]);
    }

    async save() {
        const values = { ...this.state.form };
        if (values.facility_id) values.facility_id = parseInt(values.facility_id);
        await this.fbm.saveBlock(values, values.id);
        this.state.form = { all_day: true, state: "active", block_reason: "maintenance" };
        await this.load();
    }

    static template = "facility_booking_management.FbmBlockingScreen";
    static props = ["context", "facilities"];
}

class FbmCalendarScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        const today = new Date();
        this.state = useState({
            month: today.getMonth(),
            year: today.getFullYear(),
            facilityId: "",
            events: [],
            view: "month",
        });
        onWillStart(() => this.load());
    }

    async load() {
        const start = new Date(this.state.year, this.state.month, 1);
        const end = new Date(this.state.year, this.state.month + 1, 0);
        this.state.events = await this.fbm.getCalendarEvents({
            date_start: start.toISOString().slice(0, 10),
            date_end: end.toISOString().slice(0, 10),
            facility_id: this.state.facilityId ? parseInt(this.state.facilityId) : false,
        });
    }

    daysInMonth() {
        return new Date(this.state.year, this.state.month + 1, 0).getDate();
    }

    eventsForDay(day) {
        const dateStr = `${this.state.year}-${String(this.state.month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        return this.state.events.filter((e) => e.date === dateStr);
    }

    dayList() {
        const count = this.daysInMonth();
        return Array.from({ length: count }, (_, i) => i + 1);
    }

    static template = "facility_booking_management.FbmCalendarScreen";
    static props = ["facilities", "onOpenBooking"];
}

class FbmPaymentsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ summary: null });
        onWillStart(async () => {
            this.state.summary = await this.fbm.getPaymentSummary(false);
        });
    }

    static template = "facility_booking_management.FbmPaymentsScreen";
    static props = ["onOpenBooking"];
}

class FbmReportsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ tab: "revenue", reports: null, utilization: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.reports = await this.fbm.getReports({});
        this.state.utilization = await this.fbm.getUtilization({});
    }

    static template = "facility_booking_management.FbmReportsScreen";
}

class FbmNotificationsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ category: "all", search: "", items: [] });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.items = await this.fbm.getNotifications({
            category: this.state.category,
            search: this.state.search,
        });
    }

    async markRead(id) {
        await this.fbm.markNotificationRead(id);
        await this.load();
    }

    async markAll() {
        await this.fbm.markAllNotificationsRead();
        await this.load();
    }

    static template = "facility_booking_management.FbmNotificationsScreen";
}

class FbmSettingsScreen extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({ tab: "booking", config: {}, message: "" });
        onWillStart(async () => {
            this.state.config = await this.fbm.getConfig();
        });
    }

    async saveAll() {
        try {
            this.state.config = await this.fbm.saveConfig(this.state.config);
            this.state.message = "Configuration saved.";
        } catch (e) {
            this.state.message = e.message || "Save failed.";
        }
    }

    static template = "facility_booking_management.FbmSettingsScreen";
    static props = ["context"];
}

class FbmApp extends Component {
    setup() {
        this.fbm = useService("fbm");
        this.state = useState({
            screen: "dashboard",
            bookingId: null,
            createInitial: {},
            loading: true,
            context: {},
            facilities: [],
        });
        onWillStart(async () => {
            this.state.context = await this.fbm.getUserContext();
            const result = await this.fbm.searchFacilities([], 500, 0);
            this.state.facilities = result.records;
            this.state.loading = false;
        });
    }

    navigate(screen, extra = {}) {
        this.state.screen = screen;
        if (screen === "booking_detail") {
            this.state.bookingId = extra.bookingId || extra;
            return;
        }
        this.state.bookingId = null;
        if (screen === "create_booking") {
            this.state.createInitial = extra || {};
        }
    }

    openBooking(id) {
        this.state.screen = "booking_detail";
        this.state.bookingId = id;
    }

    filteredNavItems() {
        const ctx = this.state.context;
        return FBM_NAV_ITEMS.filter((item) => {
            if (item.id === "properties") {
                if (ctx.is_manager) {
                    return true;
                }
                return ctx.is_resident && ctx.resident_property_id;
            }
            if (item.id === "approval_center" && !ctx.is_approver && !ctx.is_manager) {
                return false;
            }
            if (item.id === "booking_management" && !ctx.is_manager) {
                return false;
            }
            if (["facilities", "time_slots", "facility_blocking", "reports"].includes(item.id) && !ctx.is_manager) {
                return false;
            }
            if (item.id === "payments" && !ctx.is_manager && !ctx.is_resident) {
                return false;
            }
            return true;
        });
    }

    async refreshContext() {
        this.state.context = await this.fbm.getUserContext();
        const result = await this.fbm.searchFacilities([], 500, 0);
        this.state.facilities = result.records;
    }

    screenMeta() {
        return FBM_SCREEN_META[this.state.screen] || FBM_SCREEN_META.dashboard;
    }

    get approvalDomain() {
        return [["approval_status", "=", "pending"]];
    }

    get myBookingsDomain() {
        return [["resident_id", "=", this.state.context.resident_id || 0]];
    }

    get historyDomain() {
        return [["booking_status", "in", ["completed", "cancelled", "rejected", "expired"]]];
    }

    static template = "facility_booking_management.FbmApp";

    static components = {
        FbmSidebar,
        FbmTopbar,
        FbmDashboardScreen,
        FbmPropertiesScreen,
        FbmFacilitiesScreen,
        FbmAvailabilityScreen,
        FbmTimeSlotsScreen,
        FbmBookingsScreen,
        FbmCreateBookingScreen,
        FbmBlockingScreen,
        FbmCalendarScreen,
        FbmPaymentsScreen,
        FbmReportsScreen,
        FbmNotificationsScreen,
        FbmSettingsScreen,
        FbmBookingDetailScreen,
    };
}

registry.category("actions").add("facility_booking_management.fbm_app", FbmApp);
