/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import {
    REPORT_SOURCES,
    SEVERITIES,
    SHELL_PROPS,
    STATES,
    applyShellFilters,
    compactFilters,
    display,
    extractError,
    fromDatetimeLocal,
} from "../cc_utils";

const PREVIEW_FEATURED = [
    { id: "r1", name: "Weekly Command Center Summary", category: "Operational", generated: "Today, 09:30 AM", owner: "System", status: "generated", icon: "fa-file-text-o" },
    { id: "r2", name: "Site Alpha Incident Log", category: "Incident Analysis", generated: "Yesterday, 4:15 PM", owner: "M. Rossi", status: "generated", icon: "fa-list-alt" },
    { id: "r3", name: "Monthly KPI Review", category: "KPI Performance", generated: "Oct 01, 00:00 AM", owner: "System", status: "scheduled", icon: "fa-bar-chart" },
];

const CATEGORY_META = [
    { id: "all", label: "All Reports", source: "alerts", previewCount: 128 },
    { id: "summary", label: "Command Center Summary", source: "alerts", previewCount: 45 },
    { id: "alerts", label: "Alert Analysis", source: "alerts", previewCount: 32 },
    { id: "incidents", label: "Incident Analysis", source: "incidents", previewCount: 18 },
    { id: "emergency", label: "Emergency Response", source: "emergency", previewCount: 9 },
    { id: "sites", label: "Site Performance", source: "sites", previewCount: 14 },
    { id: "kpi", label: "KPI Performance", source: "alerts", previewCount: 6 },
    { id: "ops", label: "Operational Status", source: "sites", previewCount: 4 },
];

function previewRows() {
    const extras = [];
    const cats = ["Operational", "Alert Analysis", "Incident Analysis", "Emergency Response", "Site Performance", "KPI Performance", "Operational Status"];
    for (let index = 4; index <= 128; index++) {
        extras.push({
            id: "r" + index,
            name: "Operational Report " + index,
            category: cats[index % cats.length],
            generated: "Sep 20, 08:00 AM",
            owner: "System",
            status: index % 7 === 0 ? "scheduled" : "generated",
            icon: "fa-file-o",
        });
    }
    return PREVIEW_FEATURED.concat(extras);
}

export class ReportsScreen extends Component {
    static template = "command_center.Reports";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.sources = REPORT_SOURCES;
        this.severities = SEVERITIES;
        this.states = STATES;
        this.display = display;
        this.state = useState({
            loading: true,
            error: null,
            kpis: {},
            rows: [],
            source: "alerts",
            category: "all",
            range: "7",
            status: "",
            page: 1,
            filters: {
                source: "alerts",
                date_from: "",
                date_to: "",
                site_id: "",
                state: "",
                severity: "",
                alert_type: "",
                search: "",
            },
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
        const kpis = this.state.kpis || {};
        const total = Number(kpis.alerts || 0) + Number(kpis.incidents || 0) + Number(kpis.sites || 0) + Number(kpis.emergency || 0);
        return !total && !(this.state.rows || []).length;
    }

    get categories() {
        const kpis = this.state.kpis || {};
        return CATEGORY_META.map((item) => {
            let count = item.previewCount;
            if (!this.isPreview) {
                if (item.id === "all") {
                    count = Number(kpis.alerts || 0) + Number(kpis.incidents || 0) + Number(kpis.sites || 0) + Number(kpis.emergency || 0);
                } else if (item.id === "alerts") {
                    count = Number(kpis.alerts || 0);
                } else if (item.id === "incidents") {
                    count = Number(kpis.incidents || 0);
                } else if (item.id === "emergency") {
                    count = Number(kpis.emergency || 0);
                } else if (item.id === "sites" || item.id === "ops") {
                    count = Number(kpis.sites || 0);
                } else {
                    count = 0;
                }
            }
            return { ...item, count };
        });
    }

    get reportKpis() {
        if (this.isPreview) {
            return [
                { key: "generated", label: "Reports Generated", value: 128, icon: "fa-file-text-o" },
                { key: "scheduled", label: "Scheduled", value: 18, icon: "fa-clock-o" },
                { key: "exported", label: "Exported", value: 94, icon: "fa-download" },
                { key: "recent", label: "Recent Reports", value: 12, icon: "fa-history" },
            ];
        }
        const kpis = this.state.kpis || {};
        const total = Number(kpis.alerts || 0) + Number(kpis.incidents || 0) + Number(kpis.sites || 0) + Number(kpis.emergency || 0);
        return [
            { key: "generated", label: "Reports Generated", value: total, icon: "fa-file-text-o" },
            { key: "scheduled", label: "Scheduled", value: 0, icon: "fa-clock-o" },
            { key: "exported", label: "Exported", value: 0, icon: "fa-download" },
            { key: "recent", label: "Recent Reports", value: (this.state.rows || []).length, icon: "fa-history" },
        ];
    }

    get rawRows() {
        if (this.isPreview) {
            return previewRows();
        }
        const source = this.state.source;
        return (this.state.rows || []).map((row) => ({
            id: row.id,
            name: row.name,
            category: this.categoryLabel(source),
            generated: this.formatWhen(row.create_date || row.write_date || row.opened_at),
            owner: row.user_name || "System",
            status: "generated",
            icon: "fa-file-o",
        }));
    }

    get displayRows() {
        const category = this.state.category;
        const status = this.state.status;
        const search = (this.state.filters.search || "").toLowerCase();
        const selected = this.categories.find((item) => item.id === category);
        return this.rawRows.filter((row) => {
            if (category !== "all" && selected && row.category !== selected.label && row.category !== selected.id) {
                if (category === "summary" && row.category !== "Operational") {
                    return false;
                }
                if (category !== "summary" && row.category !== selected.label) {
                    return false;
                }
            }
            if (status && row.status !== status) {
                return false;
            }
            if (search && ![row.name, row.category, row.owner].join(" ").toLowerCase().includes(search)) {
                return false;
            }
            return true;
        });
    }

    get pagedRows() {
        const start = (this.state.page - 1) * 3;
        return this.displayRows.slice(start, start + 3);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.displayRows.length / 3));
    }

    get pageStart() {
        return this.displayRows.length ? (this.state.page - 1) * 3 + 1 : 0;
    }

    get pageEnd() {
        return Math.min(this.state.page * 3, this.displayRows.length);
    }

    get columns() {
        const source = this.state.source;
        if (source === "incidents") {
            return ["name", "severity", "state", "site_name", "summary"];
        }
        if (source === "sites") {
            return ["name", "code", "operational_status"];
        }
        if (source === "emergency") {
            return ["name", "alert_type", "state", "site_name", "is_overdue"];
        }
        return ["name", "alert_type", "severity", "state", "site_name"];
    }

    categoryLabel(source) {
        if (source === "incidents") {
            return "Incident Analysis";
        }
        if (source === "emergency") {
            return "Emergency Response";
        }
        if (source === "sites") {
            return "Site Performance";
        }
        return "Alert Analysis";
    }

    formatWhen(value) {
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
        return date.toLocaleDateString([], { month: "short", day: "2-digit" }) + ", " + time;
    }

    statusLabel(status) {
        if (status === "generated") {
            return "Generated";
        }
        if (status === "scheduled") {
            return "Scheduled";
        }
        return display(status);
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const filters = compactFilters({
                ...this.state.filters,
                search: "",
                date_from: fromDatetimeLocal(this.state.filters.date_from),
                date_to: fromDatetimeLocal(this.state.filters.date_to),
                site_id: this.state.filters.site_id ? Number(this.state.filters.site_id) : "",
            });
            const data = await this.orm.call("cc.ui.api", "get_reports_data", [filters]);
            this.state.kpis = data.kpis || {};
            this.state.source = this.state.filters.source || "alerts";
            const key = this.state.source === "emergency" ? "emergency" : this.state.source;
            this.state.rows = data[key] || [];
        } catch (err) {
            this.state.error = extractError(err);
            this.state.rows = [];
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange() {
        this.state.page = 1;
        this.refresh();
    }

    selectSource(source) {
        this.state.filters.source = source;
        this.refresh();
    }

    selectCategory(item) {
        this.state.category = item.id;
        this.state.page = 1;
        if (!this.isPreview && item.source !== this.state.filters.source) {
            this.state.filters.source = item.source;
            this.refresh();
        }
    }

    pagePrev() {
        this.state.page = Math.max(1, this.state.page - 1);
    }

    pageNext() {
        this.state.page = Math.min(this.pageCount, this.state.page + 1);
    }

    cellValue(row, column) {
        const value = row[column];
        if (typeof value === "boolean") {
            return value ? "Yes" : "No";
        }
        return display(value);
    }

    openBuilder() {
        if (this.props.navigate) {
            this.props.navigate("report_builder");
        }
    }
}
