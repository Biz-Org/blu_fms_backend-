/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "dashboard", label: "Dashboard", icon: "fa-th-large" },
    { id: "register", label: "Visitor Management", icon: "fa-users" },
    { id: "vehicles", label: "Vehicle Management", icon: "fa-car" },
    { id: "perimeter", label: "Gate Operations", icon: "fa-shield" },
    { id: "live", label: "Live Monitoring", icon: "fa-video-camera" },
    { id: "ai", label: "AI Verification", icon: "fa-magic" },
    { id: "alerts", label: "AI Security Alerts", icon: "fa-exclamation-triangle" },
    { id: "analytics", label: "Reports & Analytics", icon: "fa-line-chart" },
    { id: "employees", label: "Employee Management", icon: "fa-id-badge" },
    { id: "devices", label: "Hardware & Devices", icon: "fa-microchip" },
    { id: "settings", label: "Settings", icon: "fa-cog" },
];

const VISITOR_TABS = [
    { id: "register", label: "Registration" },
    { id: "pending", label: "Pending Requests" },
    { id: "details", label: "Visitor Details" },
    { id: "qr", label: "QR Access Pass" },
    { id: "profile", label: "Visitor Profile" },
    { id: "timeline", label: "Visit Timeline" },
];

const VEHICLE_TABS = [
    { id: "vehicle_dash", label: "Dashboard" },
    { id: "vehicles", label: "Fleet Register" },
    { id: "vehicle_history", label: "Entry / Exit History" },
    { id: "vehicle_exit", label: "Exit Verification" },
];

const EMPLOYEE_TABS = [
    { id: "employees", label: "Employees" },
    { id: "access", label: "Access Control" },
];

const HARDWARE_TABS = [
    { id: "devices", label: "Devices" },
    { id: "topology", label: "Network Topology" },
];

const SETTINGS_TABS = [
    { id: "settings", label: "System Settings" },
    { id: "notifications", label: "Notifications" },
];

export class GatePortal extends Component {
    static template = "gate_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.navItems = NAV;
        this.visitorTabs = VISITOR_TABS;
        this.vehicleTabs = VEHICLE_TABS;
        this.employeeTabs = EMPLOYEE_TABS;
        this.hardwareTabs = HARDWARE_TABS;
        this.settingsTabs = SETTINGS_TABS;
        this.state = useState({
            page: "dashboard",
            loading: true,
            data: {},
            selectedVisitor: false,
            selectedPass: false,
            noteTab: "all",
            alertFilter: "all",
            search: "",
            form: this.emptyForm(),
            vehicleForm: { plate: "", access: "staff", permit: "" },
            config: {},
            saving: false,
        });
        onWillStart(() => this.load());
    }

    emptyForm() {
        return {
            name: "", company: "", phone: "", email: "", host_id: "", purpose: "meeting",
            vehicle_id: "", plate: "", vehicle_type: "Sedan", gate_id: "", count: 1, priority: "normal",
            planned_date: "", planned_time: "", department: "",
        };
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("gate.portal", "get_dashboard_data", []);
            this.state.config = { ...(this.state.data.config || {}) };
            const rows = this.visitors();
            if (!this.state.selectedVisitor && rows.length) {
                this.state.selectedVisitor = rows[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || "Could not load GateFlow.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async call(method, args = []) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("gate.portal", method, args);
            this.state.config = { ...(this.state.data.config || {}) };
        } catch (error) {
            this.notification.add(error?.data?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        this.state.search = "";
    }

    isNavOn(itemId) {
        const page = this.state.page;
        if (itemId === "register") {
            return ["register", "pending", "details", "qr", "profile", "timeline"].includes(page);
        }
        if (itemId === "vehicles") {
            return ["vehicles", "vehicle_dash", "vehicle_history", "vehicle_exit"].includes(page);
        }
        if (itemId === "employees") {
            return ["employees", "access"].includes(page);
        }
        if (itemId === "devices") {
            return ["devices", "topology"].includes(page);
        }
        if (itemId === "settings") {
            return ["settings", "notifications"].includes(page);
        }
        return page === itemId;
    }

    breadcrumb() {
        const map = {
            dashboard: "Pages / Command Dashboard",
            register: "Visitors / Registration",
            pending: "Visitors / Approvals / Pending Requests",
            details: "Visitors / Visitor Details",
            qr: "Visitors / QR Access Pass",
            profile: "Visitors / Visitor Profile",
            timeline: "Visitors / Visit Timeline",
            live: "Pages / Live Monitoring",
            ai: "Pages / AI Validation",
            vehicle_dash: "SOC / Vehicle Management",
            vehicles: "SOC / Vehicle Management",
            vehicle_history: "SOC / Vehicle Entry History",
            vehicle_exit: "SOC / Vehicle Exit Verification",
            perimeter: "SOC / Gate Operations",
            analytics: "Pages / Reports & Analytics",
            employees: "Pages / Employee Management",
            access: "Pages / Employee Access",
            alerts: "Dashboard / AI Security Alerts",
            devices: "Pages / Hardware & Devices",
            topology: "Pages / Network Topology",
            notifications: "Pages / Notifications",
            settings: "Pages / System Settings",
        };
        return map[this.state.page] || "Pages";
    }

    liveActivity() {
        const rows = [];
        for (const e of this.state.data.entries || []) {
            rows.push({
                id: `e-${e.id}`,
                subject: e.plate || e.visitor || "Unknown",
                zone: e.gate,
                when: e.when,
                ai: e.result === "granted" ? 98 : e.result === "hold" ? 54 : 31,
                risk: e.result,
            });
        }
        for (const m of this.state.data.movements || []) {
            rows.push({
                id: `m-${m.id}`,
                subject: m.plate || "Vehicle",
                zone: m.gate,
                when: m.when,
                ai: Math.round(m.confidence || 80),
                risk: m.status === "verified" ? "granted" : m.status === "hold" || m.status === "failed" ? "rejected" : "pending",
            });
        }
        return rows.slice(0, 8);
    }

    visitors() {
        return this.state.data.visitors || [];
    }

    selected() {
        return this.visitors().find((r) => r.id === this.state.selectedVisitor) || this.visitors()[0] || {};
    }

    selectedPass() {
        return (this.state.data.passes || []).find((p) => p.id === this.state.selectedPass) || (this.state.data.passes || [])[0] || {};
    }

    eventsOf() {
        const id = this.selected().id;
        return (this.state.data.events || []).filter((e) => e.visitor_id === id);
    }

    notes() {
        let rows = this.state.data.notifications || [];
        if (this.state.noteTab !== "all") {
            rows = rows.filter((n) => n.type === this.state.noteTab);
        }
        return rows;
    }

    filteredAlerts() {
        let rows = this.state.data.alerts || [];
        if (this.state.alertFilter === "critical") {
            rows = rows.filter((a) => a.severity === "critical" || a.severity === "high");
        } else if (this.state.alertFilter === "medium") {
            rows = rows.filter((a) => a.severity === "medium");
        } else if (this.state.alertFilter === "low") {
            rows = rows.filter((a) => a.severity === "low");
        }
        return rows;
    }

    pendingCount() {
        return (this.state.data.requests || []).filter((r) => r.state !== "approved" && r.state !== "rejected").length;
    }

    urgentCount() {
        return (this.state.data.requests || []).filter((r) => r.priority === "urgent").length;
    }

    firstGate() {
        return (this.state.data.gates || [])[0] || {};
    }

    firstAI() {
        return (this.state.data.validations || [])[0] || {};
    }

    badge(status) {
        return {
            approved: "ok", checked_in: "ok", checked_out: "muted", granted: "ok", verified: "ok", active: "ok", online: "ok",
            resolved: "ok", entry: "ok", clear: "ok",
            requested: "warn", pending: "warn", host: "warn", security: "warn", investigating: "warn",
            degraded: "warn", exit: "info", medium: "warn",
            rejected: "bad", failed: "bad", hold: "bad", blocked: "bad", critical: "bad", new: "bad",
            offline: "bad", denied: "bad", high: "bad",
        }[status] || "muted";
    }

    openVisitor(row, page = "profile") {
        this.state.selectedVisitor = row.id || row.visitor_id;
        this.state.page = page;
    }

    openPass(row) {
        this.state.selectedPass = row?.id || this.selectedPass().id;
        this.state.page = "qr";
    }

    async register() {
        await this.call("register_visitor", [this.state.form]);
        this.state.form = this.emptyForm();
        this.state.page = "pending";
        this.notification.add("Visitor request created.", { type: "success" });
    }

    async review(id, action) {
        await this.call("review_request", [id, action]);
        this.notification.add("Request updated.", { type: "success" });
    }

    async check(action) {
        await this.call("check_visitor", [this.selected().id, action]);
    }

    async doGate(action) {
        const gate = this.firstGate();
        const visitor = this.selected();
        await this.call("gate_action", [gate.id, action, visitor.vehicle_id || false, visitor.id || false]);
        this.notification.add(`Gate ${action}.`, { type: "success" });
    }

    async runAI() {
        await this.call("run_ai_validation", [{ visitor_id: this.selected().id }]);
        this.state.page = "ai";
    }

    async exitAction(id, action) {
        await this.call("verify_exit", [id, action]);
    }

    async toggleBlacklist(row) {
        await this.call("update_vehicle", [{ id: row.id, authorized: row.authorized, blacklisted: !row.blacklisted, permit: row.permit }]);
    }

    async createVehicle() {
        await this.call("create_vehicle", [this.state.vehicleForm]);
        this.state.vehicleForm = { plate: "", access: "staff", permit: "" };
        this.notification.add("Vehicle saved in Fleet.", { type: "success" });
    }

    async toggleAttendance(row) {
        await this.call("toggle_attendance", [row.id]);
        this.notification.add("Attendance updated.", { type: "success" });
    }

    async logMaintenance(row) {
        await this.call("log_device_maintenance", [row.id]);
        this.notification.add("Maintenance request created.", { type: "success" });
    }

    async saveEmployee(row) {
        await this.call("update_employee_access", [{ id: row.id, clearance: row.clearance, badge: row.badge, face: !row.face }]);
    }

    async reviewAlert(id, action) {
        await this.call("review_alert", [id, action]);
    }

    async markNotes(action, id = false) {
        await this.call("mark_notifications", [action, id]);
    }

    async saveSettings() {
        await this.call("save_config", [this.state.config]);
        this.notification.add("Settings saved.", { type: "success" });
    }

    logout() {
        window.location = "/web/session/logout";
    }
}

registry.category("actions").add("gate_management.portal", GatePortal);
