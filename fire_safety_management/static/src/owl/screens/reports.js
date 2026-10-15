import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const PAGE_SIZE = 20;

const DATASETS = {
    inspections: {
        label: "Inspections",
        model: "fire.safety.inspection",
        dateField: "scheduled_date",
        fields: ["name", "inspection_type", "state", "scheduled_date", "property_id", "assigned_user_id", "is_overdue"],
    },
    findings: {
        label: "Findings",
        model: "fire.safety.finding",
        dateField: "create_date",
        fields: ["name", "severity", "state", "create_date", "property_id", "inspection_id", "incident_id", "action_count"],
    },
    actions: {
        label: "Corrective Actions",
        model: "fire.safety.action",
        dateField: "deadline",
        fields: ["name", "state", "deadline", "is_overdue", "property_id", "finding_id", "assigned_user_id"],
    },
    incidents: {
        label: "Incidents",
        model: "fire.safety.incident",
        dateField: "incident_datetime",
        fields: ["name", "incident_type", "severity", "state", "incident_datetime", "property_id", "reported_by_id"],
    },
    equipment: {
        label: "Equipment",
        model: "fire.safety.equipment",
        dateField: "inspection_due_date",
        fields: ["name", "code", "equipment_type", "condition", "state", "inspection_due_date", "property_id"],
    },
    drills: {
        label: "Mock Drills",
        model: "fire.safety.drill",
        dateField: "scheduled_datetime",
        fields: ["name", "drill_type", "state", "scheduled_datetime", "property_id", "participation_rate"],
    },
    emergencies: {
        label: "Emergencies",
        model: "fire.safety.emergency",
        dateField: "activation_datetime",
        fields: ["name", "emergency_type", "severity", "state", "activation_datetime", "property_id", "activated_by_id"],
    },
};

const STATE_LABELS = {
    scheduled: "Scheduled",
    in_progress: "In Progress",
    pending: "Pending",
    completed: "Completed",
    closed: "Closed",
    open: "Open",
    investigating: "Investigating",
    resolved: "Resolved",
    done: "Awaiting Verification",
    operational: "Operational",
    inspection_due: "Inspection Due",
    service_due: "Service Due",
    under_maintenance: "Under Maintenance",
    faulty: "Faulty",
    expired: "Expired",
    replaced: "Replaced",
    rescheduled: "Rescheduled",
    cancelled: "Cancelled",
    active: "Active",
};

function csvCell(value) {
    const text = String(value ?? "").replace(/"/g, '""');
    return `"${text}"`;
}

export class FireSafetyReports extends Component {
    static template = "fire_safety_management.Reports";
    static components = { FsAppShell, ...FS_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = user;
        this.pageSize = PAGE_SIZE;
        this.state = useState({
            loading: true,
            error: "",
            dataset: "inspections",
            propertyId: "",
            dateFrom: "",
            dateTo: "",
            page: 1,
            total: 0,
            records: [],
            dashboard: null,
            compliance: false,
            lookups: { properties: [] },
        });
        onWillStart(async () => {
            await this.reload();
        });
    }

    rpcMessage(error) {
        return error?.data?.message || error?.message || "Request failed.";
    }

    m2oName(value) {
        return Array.isArray(value) ? value[1] || "" : value || "";
    }

    toId(value) {
        const number = Number(value);
        return number ? number : false;
    }

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ") || "—";
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return String(value).slice(0, 16);
        }
        return date.toLocaleString();
    }

    formatDate(value) {
        return value ? String(value).slice(0, 10) : "—";
    }

    get datasets() {
        return Object.entries(DATASETS).map(([id, row]) => ({ id, label: row.label }));
    }

    get currentDataset() {
        return DATASETS[this.state.dataset] || DATASETS.inspections;
    }

    get compliance() {
        return this.state.compliance || false;
    }

    get hasCompliance() {
        return Boolean(this.compliance);
    }

    get belowTarget() {
        return this.hasCompliance && this.compliance.compliance < this.compliance.target;
    }

    get countRows() {
        const data = this.state.dashboard || {};
        return [
            { id: "inspections", label: "Inspections", counts: data.inspection_counts || {} },
            { id: "incidents", label: "Incidents", counts: data.incident_counts || {} },
            { id: "drills", label: "Drills", counts: data.drill_counts || {} },
            { id: "equipment", label: "Equipment", counts: data.equipment_counts || {} },
            { id: "emergencies", label: "Emergencies", counts: data.emergency_counts || {} },
        ].filter((row) => Object.keys(row.counts).length).map((row) => ({
            ...row,
            pairs: Object.entries(row.counts).map(([state, count]) => ({ state, count })),
        }));
    }

    get pageFrom() {
        return this.state.total ? (this.state.page - 1) * this.pageSize + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.page * this.pageSize, this.state.total);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.state.total / this.pageSize));
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            await Promise.all([this.loadSummary(), this.loadLookups(), this.loadRows()]);
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    async loadLookups() {
        try {
            this.state.lookups.properties = await this.orm.searchRead(
                "fire.safety.property",
                [["active", "=", true]],
                ["name"],
                { order: "name" }
            );
        } catch {
            this.state.lookups.properties = [];
        }
    }

    async loadSummary() {
        const dashboard = await this.orm.call("fire.safety.dashboard", "get_dashboard_data", []);
        this.state.dashboard = dashboard;
        if (dashboard?.compliance) {
            this.state.compliance = dashboard.compliance;
            return;
        }
        try {
            this.state.compliance = await this.orm.call("fire.safety.dashboard", "compute_compliance", []);
        } catch {
            this.state.compliance = false;
        }
    }

    rowDomain() {
        const spec = this.currentDataset;
        const domain = [];
        const propertyId = this.toId(this.state.propertyId);
        if (propertyId) {
            domain.push(["property_id", "=", propertyId]);
        }
        if (spec.dateField && this.state.dateFrom) {
            domain.push([spec.dateField, ">=", this.state.dateFrom]);
        }
        if (spec.dateField && this.state.dateTo) {
            const toValue = spec.dateField.endsWith("datetime") || spec.dateField === "create_date"
                ? `${this.state.dateTo} 23:59:59`
                : this.state.dateTo;
            domain.push([spec.dateField, "<=", toValue]);
        }
        return domain;
    }

    async loadRows() {
        const spec = this.currentDataset;
        const domain = this.rowDomain();
        try {
            const [total, records] = await Promise.all([
                this.orm.searchCount(spec.model, domain),
                this.orm.searchRead(spec.model, domain, spec.fields, {
                    limit: this.pageSize,
                    offset: (this.state.page - 1) * this.pageSize,
                    order: `${spec.dateField || "id"} desc, id desc`,
                }),
            ]);
            this.state.total = total;
            this.state.records = records;
        } catch (error) {
            this.state.total = 0;
            this.state.records = [];
            this.state.error = this.rpcMessage(error);
        }
    }

    onDataset(dataset) {
        this.state.dataset = dataset;
        this.state.page = 1;
        this.reload();
    }

    onProperty(ev) {
        this.state.propertyId = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onDateFrom(ev) {
        this.state.dateFrom = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onDateTo(ev) {
        this.state.dateTo = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onPage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.pageCount) {
            return;
        }
        this.state.page = next;
        this.reload();
    }

    rowPrimary(rec) {
        if (rec.code) {
            return rec.code;
        }
        return rec.name || "—";
    }

    rowSecondary(rec) {
        return rec.name && rec.code ? rec.name : (this.m2oName(rec.property_id) || rec.inspection_type || rec.incident_type || rec.equipment_type || rec.drill_type || rec.emergency_type || "");
    }

    rowWhen(rec) {
        const spec = this.currentDataset;
        return spec.dateField ? rec[spec.dateField] : false;
    }

    exportCsv() {
        const spec = this.currentDataset;
        const headers = ["Record", "Status", "When", "Property"];
        const lines = [headers.map(csvCell).join(",")];
        for (const rec of this.state.records) {
            lines.push([
                this.rowPrimary(rec),
                this.stateLabel(rec.state),
                this.formatWhen(this.rowWhen(rec)),
                this.m2oName(rec.property_id) || "—",
            ].map(csvCell).join(","));
        }
        const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `fire-safety-${spec.model.replace(/\./g, "-")}.csv`;
        link.click();
        URL.revokeObjectURL(url);
        this.notification.add(`Exported ${this.state.records.length} ${spec.label.toLowerCase()} row(s).`, { type: "success" });
    }

    printReport() {
        window.print();
    }
}

registry.category("actions").add("fire_safety_management.action_reports", FireSafetyReports);
