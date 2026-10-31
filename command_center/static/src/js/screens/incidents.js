/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import {
    SEVERITIES,
    SHELL_PROPS,
    STATES,
    actionClass,
    actionLabel,
    applyShellFilters,
    compactFilters,
    countBy,
    display,
    extractError,
    fromDatetimeLocal,
    incidentActions,
    workflowSteps,
    workflowStepsForScreen,
} from "../cc_utils";

const CATEGORIES = ["Equipment", "Safety", "Quality", "Logistics"];

const FEATURED = [
    { id: "p1", name: "INC-20448", opened_at: "2026-09-23 10:32:00", when: "Today, 10:32 AM", site_name: "Plant 1", category: "Equipment", summary: "Cooling system failure in Zone B", severity: "critical", state: "investigating", user_name: "Ravi Sharma" },
    { id: "p2", name: "INC-20447", opened_at: "2026-09-23 09:15:00", when: "Today, 09:15 AM", site_name: "Plant 3", category: "Safety", summary: "Minor slip hazard near loading bay", severity: "medium", state: "open", user_name: "Safety Lead" },
    { id: "p3", name: "INC-20446", opened_at: "2026-09-23 08:15:00", when: "Today, 08:15 AM", site_name: "Plant 1", category: "Quality", summary: "Concrete mix ratio deviation", severity: "high", state: "investigating", user_name: "QA Desk" },
    { id: "p4", name: "INC-20445", opened_at: "2026-09-22 16:20:00", when: "Yesterday, 16:20 PM", site_name: "Plant 2", category: "Logistics", summary: "Delivery truck breakdown", severity: "high", state: "open", user_name: "Dispatch" },
];

const PREVIEW_DETAIL = {
    p1: {
        id: "p1",
        name: "INC-20448",
        severity: "critical",
        state: "investigating",
        site_name: "Plant 1",
        user_name: "Ravi Sharma",
        summary: "Cooling system failure detected in Zone B. Initial diagnostics indicate a pressure drop in the primary cooling loop. This is causing a steady temperature rise in Curing Chamber 4, which currently holds Batch #8922.",
        opened_at: "2026-09-23 10:32:00",
        reported_by: "Sensor Auto-Alert",
        equipment: "Curing Chamber 4",
        location: "Plant 1, Zone B",
        category: "Equipment Failure",
        notes: [
            { id: "n1", user_name: "Ravi Sharma", create_date: "2026-09-23 10:35:00", time: "10:35 AM", body: "On-site inspection confirms pump seal degradation. Attempting manual bypass to auxiliary pump." },
            { id: "n2", user_name: "System Auto-Alert", create_date: "2026-09-23 10:32:00", time: "10:32 AM", body: "Pressure drop detected below safe threshold (15 pct). Alerted immediately." },
        ],
        actions: [
            { id: "a1", label: "Engage auxiliary pump bypass", done: false },
            { id: "a2", label: "Dispatch maintenance team for pump seal replacement", done: false, hint: "Assigned: Maria Alpha" },
        ],
    },
};

function previewRows() {
    const rows = FEATURED.slice();
    const sites = ["Plant 1", "Plant 2", "Plant 3", "Plant 4"];
    for (let index = 5; index <= 42; index++) {
        const number = 20449 - index;
        rows.push({
            id: "p" + index,
            name: "INC-" + number,
            opened_at: "2026-09-22 14:00:00",
            when: "Yesterday, 02:00 PM",
            site_name: sites[index % sites.length],
            category: CATEGORIES[index % CATEGORIES.length],
            summary: "Operational follow-up required",
            severity: index % 5 === 0 ? "high" : "medium",
            state: index % 3 === 0 ? "investigating" : "open",
            user_name: "Operations",
        });
    }
    return rows;
}

function detailFromRow(row) {
    if (PREVIEW_DETAIL[row.id]) {
        return PREVIEW_DETAIL[row.id];
    }
    return {
        ...row,
        reported_by: row.user_name || "Operations",
        equipment: "—",
        location: row.site_name,
        notes: [],
        actions: [],
    };
}

export class IncidentsScreen extends Component {
    static template = "command_center.Incidents";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.severities = SEVERITIES;
        this.states = STATES;
        this.categories = CATEGORIES;
        this.display = display;
        this.actionLabel = actionLabel;
        this.actionClass = actionClass;
        this.state = useState({
            loading: true,
            error: null,
            notice: null,
            busy: false,
            kpis: {},
            incidents: [],
            sites: [],
            assignable_users: [],
            selected: false,
            selectedId: false,
            filters: {
                severity: "",
                state: "active",
                site_id: "",
                user_id: "",
                category: "",
                date_from: "",
                date_to: "",
                search: "",
            },
            modal: null,
            extra: {
                user_id: "",
                body: "",
                resolution: "",
                summary: "",
                severity: "medium",
                site_id: "",
            },
            page: 1,
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
        return !(this.state.incidents || []).length;
    }

    get rawIncidents() {
        return this.isPreview ? previewRows() : this.state.incidents || [];
    }

    get displayIncidents() {
        const category = this.state.filters.category;
        const status = this.state.filters.state;
        return this.rawIncidents.filter((row) => {
            if (category && (row.category || "") !== category) {
                return false;
            }
            if (status === "active" && ["resolved", "closed"].includes(row.state)) {
                return false;
            }
            return true;
        });
    }

    get pagedIncidents() {
        const start = (this.state.page - 1) * 10;
        return this.displayIncidents.slice(start, start + 10);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.displayIncidents.length / 10));
    }

    get pageStart() {
        return this.displayIncidents.length ? (this.state.page - 1) * 10 + 1 : 0;
    }

    get pageEnd() {
        return Math.min(this.state.page * 10, this.displayIncidents.length);
    }

    get pageItems() {
        const total = this.pageCount;
        const current = this.state.page;
        const items = [];
        const push = (page, label) => items.push({ key: label + "-" + page, page, label });
        if (total <= 5) {
            for (let page = 1; page <= total; page++) {
                push(page, String(page));
            }
            return items;
        }
        push(1, "1");
        if (current > 3) {
            items.push({ key: "gap-a", page: 0, label: "…" });
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(total - 1, current + 1);
        for (let page = start; page <= end; page++) {
            push(page, String(page));
        }
        if (current < total - 2) {
            items.push({ key: "gap-b", page: 0, label: "…" });
        }
        push(total, String(total));
        return items;
    }

    get displaySelected() {
        if (this.state.selected) {
            return this.state.selected;
        }
        if (this.isPreview && this.state.selectedId) {
            const row = this.rawIncidents.find((item) => item.id === this.state.selectedId);
            return row ? detailFromRow(row) : false;
        }
        return false;
    }

    get incidentKpis() {
        if (this.isPreview) {
            return [
                { key: "open", label: "Open Incidents", value: 7, icon: "fa-folder-o", className: "cc-stat-purple" },
                { key: "new", label: "New", value: 2, icon: "fa-plus-circle", className: "cc-stat-blue" },
                { key: "invest", label: "Investigating", value: 3, icon: "fa-search", className: "" },
                { key: "high", label: "High Priority", value: 2, icon: "fa-exclamation-triangle", className: "cc-stat-orange" },
                { key: "resolved", label: "Resolved Today", value: 12, icon: "fa-check-circle", className: "cc-stat-green" },
                { key: "avg", label: "Avg Resolution", value: "2h 18m", icon: "fa-clock-o", className: "cc-stat-violet" },
            ];
        }
        const rows = this.state.incidents || [];
        const kpis = this.state.kpis || {};
        const closed = ["resolved", "closed"];
        return [
            { key: "open", label: "Open Incidents", value: kpis.incidents_open ?? rows.filter((row) => !closed.includes(row.state)).length, icon: "fa-folder-o", className: "cc-stat-purple" },
            { key: "new", label: "New", value: countBy(rows, "state", "open"), icon: "fa-plus-circle", className: "cc-stat-blue" },
            { key: "invest", label: "Investigating", value: countBy(rows, "state", "investigating"), icon: "fa-search", className: "" },
            { key: "high", label: "High Priority", value: countBy(rows, "severity", "high") + countBy(rows, "severity", "critical"), icon: "fa-exclamation-triangle", className: "cc-stat-orange" },
            { key: "resolved", label: "Resolved Today", value: countBy(rows, "state", "resolved"), icon: "fa-check-circle", className: "cc-stat-green" },
            { key: "avg", label: "Avg Resolution", value: this.avgResolution(rows), icon: "fa-clock-o", className: "cc-stat-violet" },
        ];
    }

    avgResolution(rows) {
        const resolved = (rows || []).filter((row) => row.resolved_at && row.opened_at);
        if (!resolved.length) {
            return "—";
        }
        const total = resolved.reduce((sum, row) => {
            const start = new Date(String(row.opened_at).replace(" ", "T")).getTime();
            const end = new Date(String(row.resolved_at).replace(" ", "T")).getTime();
            return sum + Math.max(0, end - start);
        }, 0);
        const minutes = Math.round(total / resolved.length / 60000);
        const hours = Math.floor(minutes / 60);
        return hours + "h " + (minutes % 60) + "m";
    }

    filtersPayload() {
        const filters = { ...this.state.filters };
        const state = filters.state === "active" ? "" : filters.state;
        return compactFilters({
            ...filters,
            category: "",
            state,
            date_from: fromDatetimeLocal(filters.date_from),
            date_to: fromDatetimeLocal(filters.date_to),
            site_id: filters.site_id ? Number(filters.site_id) : "",
            user_id: filters.user_id ? Number(filters.user_id) : "",
        });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("cc.ui.api", "get_incidents_data", [this.filtersPayload()]);
            this.state.kpis = data.kpis || {};
            this.state.incidents = data.incidents || [];
            this.state.sites = data.sites || [];
            this.state.assignable_users = data.assignable_users || [];
            if (this.state.selectedId && typeof this.state.selectedId === "number") {
                const detail = await this.orm.call("cc.ui.api", "get_incidents_data", [
                    { incident_id: this.state.selectedId },
                ]);
                this.state.selected = detail.selected || false;
            } else if (!(data.incidents || []).length) {
                this.state.selectedId = this.state.selectedId || "p1";
                this.state.selected = detailFromRow(FEATURED[0]);
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

    pagePrev() {
        this.state.page = Math.max(1, this.state.page - 1);
    }

    pageNext() {
        this.state.page = Math.min(this.pageCount, this.state.page + 1);
    }

    goPage(page) {
        if (!page) {
            return;
        }
        this.state.page = page;
    }

    async selectIncident(id) {
        this.state.selectedId = id;
        this.state.error = null;
        if (typeof id !== "number") {
            const row = this.rawIncidents.find((item) => item.id === id);
            this.state.selected = row ? detailFromRow(row) : false;
            return;
        }
        try {
            const detail = await this.orm.call("cc.ui.api", "get_incidents_data", [
                { incident_id: id },
            ]);
            this.state.selected = detail.selected || false;
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    clearSelected() {
        this.state.selected = false;
        this.state.selectedId = false;
    }

    visibleActions(incident) {
        return incidentActions(this.props.session, incident);
    }

    get canCreate() {
        return Boolean(this.props.session.is_manager);
    }

    get workflowSteps() {
        return workflowSteps(this.displaySelected, "incident");
    }

    get moduleWorkflowSteps() {
        return workflowStepsForScreen("incidents");
    }

    get canEscalate() {
        return this.visibleActions(this.displaySelected).includes("escalate");
    }

    labelFor(action) {
        if (action === "assign" && !this.props.session.is_manager) {
            return "Assign self";
        }
        return actionLabel(action);
    }

    formatWhen(row) {
        if (row && row.when) {
            return row.when;
        }
        const value = row && row.opened_at;
        if (!value) {
            return "—";
        }
        const stamp = String(value).includes("T") ? value : String(value).replace(" ", "T");
        const date = new Date(stamp);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        const today = new Date();
        const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        const startRow = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const diff = (startToday - startRow) / 86400000;
        if (diff === 0) {
            return "Today, " + time;
        }
        if (diff === 1) {
            return "Yesterday, " + time;
        }
        return date.toLocaleDateString([], { month: "short", day: "numeric" }) + ", " + time;
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
        if (state === "acknowledged") {
            return "Acknowledged";
        }
        if (state === "investigating") {
            return "Investigating";
        }
        return display(state);
    }

    severityLabel(severity) {
        if (!severity) {
            return "—";
        }
        return String(severity).charAt(0).toUpperCase() + String(severity).slice(1);
    }

    categoryOf(row) {
        return row.category || "—";
    }

    fieldOf(row, key, fallback = "—") {
        return row && row[key] ? row[key] : fallback;
    }

    openModal(action) {
        this.state.extra = {
            user_id: this.props.session.uid || "",
            body: "",
            resolution: "",
            summary: "",
            severity: "medium",
            site_id: "",
        };
        this.state.modal = action;
    }

    closeModal() {
        this.state.modal = null;
    }

    async createIncident() {
        this.state.error = null;
        this.state.busy = true;
        try {
            const result = await this.orm.call("cc.ui.api", "run_incident_action", [
                false,
                "create",
                {
                    summary: this.state.extra.summary,
                    severity: this.state.extra.severity,
                    site_id: this.state.extra.site_id ? Number(this.state.extra.site_id) : false,
                },
            ]);
            this.closeModal();
            this.notification.add("Incident created.", { type: "success" });
            this.state.selectedId = result.incident && result.incident.id;
            await this.refresh();
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.busy = false;
        }
    }

    updateStatus() {
        const selected = this.displaySelected;
        if (!selected) {
            return;
        }
        if (selected.state === "open" || selected.state === "acknowledged") {
            this.runAction("investigate");
            return;
        }
        if (selected.state === "investigating") {
            this.runAction("resolve");
            return;
        }
        if (selected.state === "resolved") {
            this.runAction("close");
        }
    }

    async runAction(action) {
        if (action === "create") {
            if (this.state.modal !== "create") {
                this.openModal("create");
                return;
            }
            await this.createIncident();
            return;
        }
        if (!this.displaySelected) {
            return;
        }
        const needsModal = ["resolve", "add_note", "close", "reopen", "escalate"];
        if (action === "assign" && this.props.session.is_manager) {
            needsModal.push("assign");
        }
        if (needsModal.includes(action) && this.state.modal !== action) {
            this.openModal(action);
            return;
        }
        if (this.isPreview || typeof this.displaySelected.id !== "number") {
            this.closeModal();
            return;
        }
        const extra = {};
        if (action === "assign") {
            extra.user_id = this.props.session.is_manager
                ? Number(this.state.extra.user_id || this.props.session.uid)
                : this.props.session.uid;
        }
        if (action === "resolve") {
            extra.resolution = this.state.extra.resolution;
        }
        if (action === "add_note") {
            extra.body = this.state.extra.body;
        }
        if (action === "escalate") {
            extra.note = this.state.extra.body;
        }
        this.state.error = null;
        this.state.busy = true;
        try {
            await this.orm.call("cc.ui.api", "run_incident_action", [
                this.displaySelected.id,
                action,
                extra,
            ]);
            this.closeModal();
            this.notification.add("Incident updated.", { type: "success" });
            await this.refresh();
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.busy = false;
        }
    }
}
