/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { REPORT_SOURCES, SHELL_PROPS, compactFilters, display, extractError } from "../cc_utils";

const REPORT_TYPES = [
    { id: "summary", label: "Command Center Summary", source: "alerts" },
    { id: "alerts", label: "Alert Analysis", source: "alerts" },
    { id: "incidents", label: "Incident Analysis", source: "incidents" },
    { id: "emergency", label: "Emergency Response", source: "emergency" },
    { id: "sites", label: "Site Performance", source: "sites" },
];

const PREVIEW_ROWS = [
    { id: "p1", date: "Oct 01", site: "Site Alpha", alerts: "45", critical: "2" },
    { id: "p2", date: "Oct 02", site: "Site Alpha", alerts: "38", critical: "0" },
    { id: "p3", date: "Oct 01", site: "Site Beta", alerts: "62", critical: "5" },
];

const PREVIEW_BARS = [18, 22, 16, 28, 20, 24, 18, 32, 26, 48, 36, 58];

export class ReportBuilderScreen extends Component {
    static template = "command_center.ReportBuilder";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.sources = REPORT_SOURCES;
        this.types = REPORT_TYPES;
        this.display = display;
        this.state = useState({
            loading: true,
            error: null,
            info: null,
            definitions: [],
            exports: [],
            filters: { source: "", active: "" },
            selectedId: false,
            result: null,
            specSource: "alerts",
            reportType: "summary",
            dateFrom: "2023-10-01",
            dateTo: "2023-10-31",
            siteScope: "",
            department: "",
            statusChip: "all",
            metricAlerts: true,
            metricIncidents: true,
            metricResources: false,
            groupBy: "date",
            comparison: "",
            exportFormat: "csv",
        });
        onWillStart(() => this.refresh());
    }

    get isPreview() {
        return !(this.state.result && (this.state.result.rows || []).length);
    }

    get previewTitle() {
        const type = REPORT_TYPES.find((item) => item.id === this.state.reportType);
        return (type && type.label ? type.label : "Command Center Summary") + " Report";
    }

    get previewKpis() {
        if (this.isPreview) {
            return [
                { key: "alerts", label: "Total Alerts", value: "1,248" },
                { key: "critical", label: "Critical Incidents", value: "42" },
                { key: "avg", label: "Avg Resolution Time", value: "4h 12m" },
            ];
        }
        const rows = this.state.result.rows || [];
        const critical = rows.filter((row) => row.severity === "critical" || row.is_emergency).length;
        return [
            { key: "alerts", label: "Total Alerts", value: String(rows.length) },
            { key: "critical", label: "Critical Incidents", value: String(critical) },
            { key: "avg", label: "Avg Resolution Time", value: "—" },
        ];
    }

    get previewRows() {
        if (this.isPreview) {
            return PREVIEW_ROWS;
        }
        return (this.state.result.rows || []).slice(0, 8).map((row, index) => ({
            id: row.id || index,
            date: display(row.create_date || row.opened_at || row.write_date),
            site: row.site_name || row.name || "—",
            alerts: display(row.alert_type || row.severity || "—"),
            critical: row.severity === "critical" || row.is_emergency ? "1" : "0",
        }));
    }

    get previewBars() {
        return PREVIEW_BARS;
    }

    get dateRangeLabel() {
        return this.formatDate(this.state.dateFrom) + " - " + this.formatDate(this.state.dateTo);
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value + "T00:00:00");
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleDateString([], { month: "short", day: "2-digit", year: "numeric" });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const filters = compactFilters({
                source: this.state.filters.source,
            });
            if (this.state.filters.active !== "") {
                filters.active = this.state.filters.active === "true";
            }
            const data = await this.orm.call("cc.ui.api", "get_report_definitions", [filters]);
            this.state.definitions = data.definitions || [];
            this.state.exports = data.exports || [];
        } catch (err) {
            this.state.error = extractError(err);
            this.state.definitions = [];
            this.state.exports = [];
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange() {
        this.refresh();
    }

    onTypeChange() {
        const type = REPORT_TYPES.find((item) => item.id === this.state.reportType);
        this.state.specSource = type ? type.source : "alerts";
    }

    setChip(value) {
        this.state.statusChip = value;
    }

    setExportFormat(format) {
        this.state.exportFormat = format;
    }

    async runSaved(id) {
        this.state.error = null;
        this.state.info = null;
        this.state.selectedId = id;
        try {
            this.state.result = await this.orm.call("cc.ui.api", "run_report", [id]);
        } catch (err) {
            this.state.error = extractError(err);
            this.state.result = null;
        }
    }

    async runAdhoc() {
        this.state.error = null;
        this.state.info = null;
        try {
            this.state.result = await this.orm.call("cc.ui.api", "run_report", [
                false,
                { source: this.state.specSource },
            ]);
        } catch (err) {
            this.state.error = extractError(err);
            this.state.result = null;
        }
    }

    async exportReport() {
        this.state.error = null;
        this.state.info = null;
        try {
            await this.orm.call("cc.ui.api", "export_report", [
                this.state.selectedId || false,
                { source: this.state.specSource },
                this.state.exportFormat || "csv",
            ]);
        } catch (err) {
            this.state.info = extractError(err);
        }
    }

    saveConfig() {
        this.notification.add("Saving report definitions is not available from this screen.", { type: "warning" });
    }

    scheduleReport() {
        this.notification.add("Scheduling is not available yet.", { type: "warning" });
    }

    resultColumns() {
        const rows = (this.state.result && this.state.result.rows) || [];
        if (!rows.length) {
            return [];
        }
        return Object.keys(rows[0]).filter((key) => typeof rows[0][key] !== "object");
    }
}
