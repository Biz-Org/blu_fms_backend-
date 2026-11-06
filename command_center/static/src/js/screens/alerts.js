/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import {
    SEVERITIES,
    SHELL_PROPS,
    SOURCES,
    STATES,
    actionClass,
    actionLabel,
    alertActions,
    applyShellFilters,
    compactFilters,
    countBy,
    display,
    extractError,
    fromDatetimeLocal,
    workflowSteps,
    workflowStepsForScreen,
} from "../cc_utils";

export class AlertsScreen extends Component {
    static template = "command_center.Alerts";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.severities = SEVERITIES;
        this.sources = SOURCES;
        this.states = STATES;
        this.display = display;
        this.actionLabel = actionLabel;
        this.actionClass = actionClass;
        this.state = useState({
            loading: true,
            error: null,
            notice: null,
            busy: false,
            kpis: {},
            alerts: [],
            sites: [],
            assignable_users: [],
            selected: false,
            selectedId: false,
            filters: {
                severity: "",
                source: "",
                alert_type: "",
                site_id: "",
                state: "",
                user_id: "",
                is_emergency: false,
                date_from: "",
                date_to: "",
                search: "",
            },
            modal: null,
            extra: { user_id: "", body: "", note: "", resolution_note: "", summary: "", severity: "medium" },
            checkedIds: [],
            page: 1,
            showMoreFilters: false,
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
        if (this.isPreview) {
            return [
                { id: "p1", name: "ALT-20482", create_date: "2026-09-23 10:42:00", site_name: "Plant 1", source: "HVAC-04", alert_type: "Equipment", severity: "critical", state: "open", user_name: "Maintenance" },
                { id: "p2", name: "ALT-20481", create_date: "2026-09-23 10:15:00", site_name: "Plant 2", source: "Line A Sensor", alert_type: "Process", severity: "high", state: "acknowledged", user_name: "Operator John" },
                { id: "p3", name: "ALT-20480", create_date: "2026-09-23 09:30:00", site_name: "Warehouse B", source: "Forklift 3", alert_type: "Equipment", severity: "medium", state: "investigating", user_name: "Logistics Team" },
                { id: "p4", name: "ALT-20479", create_date: "2026-09-23 08:00:00", site_name: "Plant 1", source: "Mixer 2", alert_type: "Process", severity: "high", state: "resolved", user_name: "Eng. Dept" },
            ];
        }
        return this.state.alerts || [];
    }

    get alertKpis() {
        if (this.isPreview) {
            return [
                { key: "active", label: "Active Alerts", value: 18, icon: "fa-bell", className: "cc-stat-purple" },
                { key: "critical", label: "Critical", value: 4, icon: "fa-exclamation-triangle", className: "cc-stat-red" },
                { key: "high", label: "High", value: 6, icon: "fa-exclamation-circle", className: "cc-stat-orange" },
                { key: "ack", label: "Acknowledged", value: 8, icon: "fa-check", className: "cc-stat-blue" },
                { key: "escalated", label: "Escalated", value: 3, icon: "fa-level-up", className: "cc-stat-violet" },
                { key: "resolved", label: "Resolved Today", value: 24, icon: "fa-check-circle", className: "cc-stat-green" },
            ];
        }
        const alerts = this.state.alerts || [];
        const kpis = this.state.kpis || {};
        const closed = ["resolved", "closed"];
        return [
            { key: "active", label: "Active Alerts", value: kpis.alerts_active ?? alerts.filter((row) => !closed.includes(row.state)).length, icon: "fa-bell", className: "cc-stat-purple" },
            { key: "critical", label: "Critical", value: countBy(alerts, "severity", "critical"), icon: "fa-exclamation-triangle", className: "cc-stat-red" },
            { key: "high", label: "High", value: countBy(alerts, "severity", "high"), icon: "fa-exclamation-circle", className: "cc-stat-orange" },
            { key: "ack", label: "Acknowledged", value: countBy(alerts, "state", "acknowledged"), icon: "fa-check", className: "cc-stat-blue" },
            { key: "escalated", label: "Escalated", value: countBy(alerts, "state", "investigating"), icon: "fa-level-up", className: "cc-stat-violet" },
            { key: "resolved", label: "Resolved Today", value: countBy(alerts, "state", "resolved"), icon: "fa-check-circle", className: "cc-stat-green" },
        ];
    }

    filtersPayload() {
        const filters = { ...this.state.filters };
        const payload = compactFilters({
            ...filters,
            date_from: fromDatetimeLocal(filters.date_from),
            date_to: fromDatetimeLocal(filters.date_to),
            site_id: filters.site_id ? Number(filters.site_id) : "",
            user_id: filters.user_id ? Number(filters.user_id) : "",
        });
        return payload;
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("cc.ui.api", "get_alerts_data", [this.filtersPayload()]);
            this.state.kpis = data.kpis || {};
            this.state.alerts = data.alerts || [];
            this.state.sites = data.sites || [];
            this.state.assignable_users = data.assignable_users || [];
            if (this.state.selectedId) {
                const detail = await this.orm.call("cc.ui.api", "get_alerts_data", [
                    { alert_id: this.state.selectedId },
                ]);
                this.state.selected = detail.selected || false;
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange() {
        this.state.page = 1;
        this.refresh();
    }

    setChip(field, value) {
        this.state.filters[field] = this.state.filters[field] === value ? "" : value;
        this.onFilterChange();
    }

    get pagedAlerts() {
        const start = (this.state.page - 1) * 10;
        return this.displayAlerts.slice(start, start + 10);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.displayAlerts.length / 10));
    }

    get pageStart() {
        return this.displayAlerts.length ? (this.state.page - 1) * 10 + 1 : 0;
    }

    get pageEnd() {
        return Math.min(this.state.page * 10, this.displayAlerts.length);
    }

    toggleMoreFilters() {
        this.state.showMoreFilters = !this.state.showMoreFilters;
    }

    clearSelected() {
        this.state.selected = false;
        this.state.selectedId = false;
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

    statusLabel(state) {
        if (state === "open") {
            return "New";
        }
        if (state === "investigating") {
            return "In Progress";
        }
        return display(state);
    }

    toggleCheck(id, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        const ids = this.state.checkedIds.slice();
        const index = ids.indexOf(id);
        if (index >= 0) {
            ids.splice(index, 1);
        } else {
            ids.push(id);
        }
        this.state.checkedIds = ids;
    }

    isChecked(id) {
        return this.state.checkedIds.includes(id);
    }

    pagePrev() {
        this.state.page = Math.max(1, this.state.page - 1);
    }

    pageNext() {
        this.state.page = Math.min(this.pageCount, this.state.page + 1);
    }

    async acknowledgeSelected() {
        const openIds = (this.state.alerts || [])
            .filter((alert) => typeof alert.id === "number" && this.state.checkedIds.includes(alert.id) && alert.state === "open")
            .map((alert) => alert.id);
        if (!openIds.length) {
            this.state.notice = "Select open alerts to acknowledge.";
            return;
        }
        this.state.busy = true;
        this.state.error = null;
        try {
            for (const id of openIds) {
                await this.orm.call("cc.ui.api", "run_alert_action", [id, "acknowledge", {}]);
            }
            this.state.checkedIds = [];
            this.notification.add("Selected alerts acknowledged.", { type: "success" });
            await this.refresh();
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.busy = false;
        }
    }

    async selectAlert(id) {
        this.state.selectedId = id;
        this.state.error = null;
        if (typeof id !== "number") {
            this.state.selected = this.displayAlerts.find((row) => row.id === id) || false;
            return;
        }
        try {
            const detail = await this.orm.call("cc.ui.api", "get_alerts_data", [
                { alert_id: id },
            ]);
            this.state.selected = detail.selected || false;
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    visibleActions(alert) {
        return alertActions(this.props.session, alert);
    }

    get workflowSteps() {
        return workflowSteps(this.state.selected, "alert");
    }

    get moduleWorkflowSteps() {
        return workflowStepsForScreen("alerts");
    }

    labelFor(action) {
        if (action === "assign" && !this.props.session.is_manager) {
            return "Assign self";
        }
        return actionLabel(action);
    }

    openModal(action) {
        this.state.extra = {
            user_id: this.props.session.uid || "",
            body: "",
            note: "",
            resolution_note: "",
            summary: this.state.selected && this.state.selected.alert_type || "",
            severity: this.state.selected && this.state.selected.severity || "medium",
        };
        this.state.modal = action;
    }

    closeModal() {
        this.state.modal = null;
    }

    async runAction(action) {
        if (!this.state.selected) {
            return;
        }
        const needsModal = ["escalate", "resolve", "add_note", "close", "reopen", "to_incident"];
        if (action === "assign" && this.props.session.is_manager) {
            needsModal.push("assign");
        }
        if (needsModal.includes(action) && this.state.modal !== action) {
            this.openModal(action);
            return;
        }
        const extra = {};
        if (action === "assign") {
            extra.user_id = this.props.session.is_manager
                ? Number(this.state.extra.user_id || this.props.session.uid)
                : this.props.session.uid;
        }
        if (action === "escalate") {
            extra.note = this.state.extra.note;
        }
        if (action === "resolve") {
            extra.resolution_note = this.state.extra.resolution_note;
        }
        if (action === "add_note") {
            extra.body = this.state.extra.body;
        }
        if (action === "to_incident") {
            extra.summary = this.state.extra.summary;
            extra.severity = this.state.extra.severity;
        }
        this.state.error = null;
        this.state.notice = null;
        this.state.busy = true;
        try {
            await this.orm.call("cc.ui.api", "run_alert_action", [
                this.state.selected.id,
                action,
                extra,
            ]);
            this.closeModal();
            this.state.notice = "Action completed.";
            this.notification.add("Alert updated.", { type: "success" });
            await this.refresh();
            if (action === "to_incident" && this.props.navigate) {
                this.props.navigate("incidents");
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.busy = false;
        }
    }
}
