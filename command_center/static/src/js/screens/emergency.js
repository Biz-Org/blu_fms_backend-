/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import {
    SHELL_PROPS,
    STATES,
    actionClass,
    actionLabel,
    applyShellFilters,
    compactFilters,
    countBy,
    display,
    emergencyActions,
    extractError,
    workflowSteps,
    workflowStepsForScreen,
} from "../cc_utils";

const PREVIEW_ALERT = {
    id: "p1",
    name: "EMG-0042",
    alert_type: "Fire Detection",
    severity: "critical",
    state: "investigating",
    site_name: "Plant 2, Sector B",
    user_name: "J. Smith",
    create_date: "2026-09-23 10:36:00",
    is_emergency: true,
    is_overdue: false,
    message: "SENSOR ALARM: Multi-point heat threshold exceeded. Sprinkler system engaged in Bay 4.",
};

const PREVIEW_HISTORY = [
    { id: "h1", level: 2, result: "escalated", timestamp: "2026-09-23 10:41:00", time: "10:41 AM", title: "Escalated to Level 2 (Site Manager)", body: "Automated escalation due to lack of clearance at Level 1 within 5 minutes.", tone: "warn" },
    { id: "h2", level: 1, result: "acknowledged", timestamp: "2026-09-23 10:37:00", time: "10:37 AM", title: "Acknowledged by Operations", body: "Operator ID J. Smith initiated initial assessment protocol.", tone: "ok" },
    { id: "h3", level: 0, result: "triggered", timestamp: "2026-09-23 10:36:00", time: "10:36 AM", title: "Initial Trigger: Fire Detection", body: "System auto-detected anomalies in Plant 2, Sector B.", tone: "crit" },
];

const PREVIEW_LEVELS = [
    { key: "l1", level: 1, name: "Operations", clock: "00:00", status: "Acknowledged", tone: "ok", active: false },
    { key: "l2", level: 2, name: "Site Manager", clock: "00:13", status: "In Progress", tone: "crit", active: true },
    { key: "l3", level: 3, name: "ER Team", clock: "—", status: "Standby", tone: "", active: false },
    { key: "l4", level: 4, name: "Executive", clock: "—", status: "Standby", tone: "", active: false },
];

export class EmergencyScreen extends Component {
    static template = "command_center.Emergency";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.states = STATES;
        this.display = display;
        this.actionLabel = actionLabel;
        this.actionClass = actionClass;
        this.state = useState({
            loading: true,
            error: null,
            busy: false,
            kpis: {},
            alerts: [],
            sites: [],
            rules: [],
            history: [],
            selected: false,
            selectedId: false,
            filters: {
                alert_type: "",
                site_id: "",
                state: "",
                level: "",
                overdue: false,
                search: "",
            },
            modal: null,
            extra: { note: "", rule_id: "" },
        });
        applyShellFilters(this.state.filters, this.props);
        onWillStart(() => this.refresh());
        onWillUpdateProps((next) => {
            if (next.shellSearch !== this.props.shellSearch || next.shellSiteId !== this.props.shellSiteId) {
                applyShellFilters(this.state.filters, next);
                this.refresh();
            }
        });
    }

    get isPreview() {
        return !(this.state.alerts || []).length;
    }

    get displayAlerts() {
        const rows = this.isPreview ? [PREVIEW_ALERT] : this.state.alerts || [];
        const search = (this.state.filters.search || "").toLowerCase();
        if (!search) {
            return rows;
        }
        return rows.filter((row) => [row.name, row.alert_type, row.site_name].join(" ").toLowerCase().includes(search));
    }

    get displaySelected() {
        if (this.state.selected) {
            return this.state.selected;
        }
        if (this.isPreview) {
            return PREVIEW_ALERT;
        }
        return false;
    }

    get displayHistory() {
        if (this.isPreview) {
            return PREVIEW_HISTORY;
        }
        const rows = this.state.history || [];
        if (rows.length) {
            return rows.map((row) => ({
                ...row,
                title: row.note || ("Level " + row.level + " · " + display(row.result)),
                body: row.note || "",
                time: this.formatTime(row.timestamp),
                tone: row.result === "triggered" || Number(row.level) > 1 ? "warn" : "ok",
            }));
        }
        const selected = this.displaySelected;
        if (!selected) {
            return [];
        }
        return [{
            id: "init",
            title: "Initial Trigger: " + display(selected.alert_type),
            body: display(selected.site_name),
            time: this.formatTime(selected.create_date),
            tone: "crit",
        }];
    }

    get protocolLevels() {
        if (this.isPreview) {
            return PREVIEW_LEVELS;
        }
        const rules = (this.state.rules || []).slice().sort((a, b) => a.level - b.level);
        const history = this.state.history || [];
        const maxLevel = history.reduce((max, row) => Math.max(max, Number(row.level) || 0), 0);
        if (!rules.length) {
            return [];
        }
        return rules.map((rule) => {
            const hit = history.find((row) => Number(row.level) === Number(rule.level));
            let status = "Standby";
            let tone = "";
            let active = false;
            if (hit || (maxLevel && rule.level < maxLevel)) {
                status = "Acknowledged";
                tone = "ok";
            }
            if (maxLevel && rule.level === maxLevel) {
                status = this.displaySelected && this.displaySelected.state === "investigating" ? "In Progress" : display(hit && hit.result);
                tone = status === "In Progress" ? "crit" : "ok";
                active = status === "In Progress";
            }
            return {
                key: "r-" + rule.id,
                level: rule.level,
                name: rule.name,
                clock: rule.delay_minutes ? String(rule.delay_minutes).padStart(2, "0") + ":00" : "00:00",
                status,
                tone,
                active,
            };
        });
    }

    get emergencyKpis() {
        if (this.isPreview) {
            return [
                { key: "active", label: "Active Emergencies", value: 2, icon: "fa-warning", className: "cc-stat-red" },
                { key: "today", label: "Triggered Today", value: 4, icon: "fa-bolt", className: "" },
                { key: "ack", label: "Acknowledged", value: 3, icon: "fa-check-circle", className: "" },
                { key: "esc", label: "Escalated", value: 2, icon: "fa-level-up", className: "" },
                { key: "resp", label: "Response Active", value: 1, icon: "fa-crosshairs", className: "" },
                { key: "avg", label: "Avg Response", value: "4m 32s", icon: "fa-clock-o", className: "" },
            ];
        }
        const alerts = this.state.alerts || [];
        const kpis = this.state.kpis || {};
        return [
            { key: "active", label: "Active Emergencies", value: kpis.emergencies_active ?? 0, icon: "fa-warning", className: "cc-stat-red" },
            { key: "today", label: "Triggered Today", value: kpis.total ?? alerts.length, icon: "fa-bolt", className: "" },
            { key: "ack", label: "Acknowledged", value: countBy(alerts, "state", "acknowledged"), icon: "fa-check-circle", className: "" },
            { key: "esc", label: "Escalated", value: countBy(alerts, "state", "investigating"), icon: "fa-level-up", className: "" },
            { key: "resp", label: "Response Active", value: countBy(alerts, "state", "investigating"), icon: "fa-crosshairs", className: "" },
            { key: "avg", label: "Avg Response", value: "—", icon: "fa-clock-o", className: "" },
        ];
    }

    filtersPayload() {
        const filters = this.state.filters;
        return compactFilters({
            ...filters,
            search: "",
            site_id: filters.site_id ? Number(filters.site_id) : "",
            level: filters.level !== "" ? Number(filters.level) : "",
        });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("cc.ui.api", "get_emergency_data", [this.filtersPayload()]);
            this.state.kpis = data.kpis || {};
            this.state.alerts = data.alerts || [];
            this.state.sites = data.sites || [];
            this.state.rules = data.rules || [];
            if ((data.alerts || []).length) {
                const id = typeof this.state.selectedId === "number" ? this.state.selectedId : data.alerts[0].id;
                await this.selectAlert(id);
            } else {
                this.state.selectedId = "p1";
                this.state.selected = PREVIEW_ALERT;
                this.state.history = PREVIEW_HISTORY;
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange() {
        this.state.selectedId = false;
        this.refresh();
    }

    setChip(field, value) {
        this.state.filters[field] = value;
        this.onFilterChange();
    }

    async selectAlert(id) {
        this.state.selectedId = id;
        this.state.error = null;
        if (typeof id !== "number") {
            this.state.selected = PREVIEW_ALERT;
            this.state.history = PREVIEW_HISTORY;
            return;
        }
        try {
            const detail = await this.orm.call("cc.ui.api", "get_emergency_data", [
                { alert_id: id },
            ]);
            this.state.selected = detail.selected || false;
            this.state.history = detail.history || [];
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    visibleActions(alert) {
        return emergencyActions(this.props.session, alert);
    }

    get workflowSteps() {
        return workflowSteps(this.displaySelected, "emergency");
    }

    get moduleWorkflowSteps() {
        return workflowStepsForScreen("emergency");
    }

    heroTitle(alert) {
        if (!alert) {
            return "—";
        }
        if (alert.alert_type && !String(alert.name).includes(alert.alert_type)) {
            return alert.name + ": " + alert.alert_type;
        }
        return alert.name;
    }

    statusLabel(state) {
        if (state === "investigating") {
            return "Response In Progress";
        }
        if (state === "acknowledged") {
            return "Acknowledged";
        }
        if (state === "open") {
            return "Triggered";
        }
        return display(state);
    }

    severityLabel(severity) {
        if (!severity) {
            return "Critical";
        }
        return String(severity).charAt(0).toUpperCase() + String(severity).slice(1);
    }

    statusMessage(alert) {
        if (alert && alert.message) {
            return alert.message;
        }
        if (alert && alert.resolution_note) {
            return alert.resolution_note;
        }
        if (!alert) {
            return "—";
        }
        return display(alert.alert_type) + " reported at " + display(alert.site_name) + ".";
    }

    triggeredLabel(alert) {
        if (this.isPreview) {
            return "10:36 AM (12 mins ago)";
        }
        const time = this.formatTime(alert && alert.create_date);
        return time;
    }

    formatTime(value) {
        if (!value) {
            return "—";
        }
        const stamp = String(value).includes("T") ? value : String(value).replace(" ", "T");
        const date = new Date(stamp);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }

    broadcastAlert() {
        this.notification.add("Emergency broadcast is not available yet.", { type: "warning" });
    }

    visualAction() {
        this.notification.add("This control is not wired to a live channel.", { type: "info" });
    }

    openModal(action) {
        this.state.extra = { note: "", rule_id: "" };
        this.state.modal = action;
    }

    closeModal() {
        this.state.modal = null;
    }

    async runAction(action) {
        if (!this.displaySelected) {
            return;
        }
        if (["escalate", "resolve", "handle_overdue", "reopen"].includes(action) && this.state.modal !== action) {
            this.openModal(action);
            return;
        }
        if (this.isPreview || typeof this.displaySelected.id !== "number") {
            this.closeModal();
            return;
        }
        const extra = {};
        if (action === "escalate") {
            extra.note = this.state.extra.note;
            if (this.state.extra.rule_id) {
                extra.rule_id = Number(this.state.extra.rule_id);
            }
        }
        this.state.error = null;
        this.state.busy = true;
        try {
            await this.orm.call("cc.ui.api", "run_emergency_action", [
                this.displaySelected.id,
                action,
                extra,
            ]);
            this.closeModal();
            this.notification.add("Emergency updated.", { type: "success" });
            await this.refresh();
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.busy = false;
        }
    }
}
