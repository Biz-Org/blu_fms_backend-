import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const PAGE_SIZE = 20;

const STATE_LABELS = {
    scheduled: "Scheduled",
    in_progress: "In Progress",
    pending: "Pending",
    pending_review: "Pending Review",
    pending_verification: "Pending Verification",
    completed: "Completed",
    failed: "Failed",
    closed: "Closed",
    open: "Open",
    assigned: "Assigned",
    resolved: "Resolved",
    draft: "Draft",
    in_preparation: "In Preparation",
    submitted: "Submitted",
    active: "Active",
    expiring_soon: "Expiring Soon",
    renewal_due: "Renewal Due",
    under_renewal: "Under Renewal",
    expired: "Expired",
    archived: "Archived",
    verified: "Verified",
};

function csvCell(value) {
    const text = String(value ?? "").replace(/"/g, '""');
    return `"${text}"`;
}

export class ComplianceReports extends Component {
    static template = "compliance_audit_management.Reports";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.state = useState({
            loading: true,
            error: "",
            dataset: "checks",
            propertyId: "",
            dateFrom: "",
            dateTo: "",
            page: 1,
            total: 0,
            records: [],
            kpis: {},
            health: [],
            statusBlocks: [],
            datasets: [],
            datasetLabel: "Activities",
            asOf: "",
            lookups: { properties: [] },
        });
        onWillStart(async () => {
            this.state.lookups.properties = await this.orm.searchRead(
                "compliance.property",
                [],
                ["name"],
                { order: "name", limit: 200 }
            );
            await this.reload();
        });
    }

    get pageCount() {
        return Math.max(1, Math.ceil((this.state.total || 0) / this.pageSize));
    }

    get pageFrom() {
        return this.state.total ? (this.state.page - 1) * this.pageSize + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.total, this.state.page * this.pageSize);
    }

    get overallCompliance() {
        return `${this.state.kpis.overall_compliance_rate ?? 0}%`;
    }

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ") || "—";
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return String(value).slice(0, 10);
        }
        return date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const payload = await this.orm.call("compliance.dashboard", "get_compliance_reports", [
                this.state.dataset,
                this.state.propertyId ? Number(this.state.propertyId) : false,
                this.state.dateFrom || false,
                this.state.dateTo || false,
                (this.state.page - 1) * this.pageSize,
                this.pageSize,
            ]);
            this.state.kpis = payload.kpis || {};
            this.state.health = payload.health_by_category || [];
            this.state.statusBlocks = payload.status_blocks || [];
            this.state.records = payload.records || [];
            this.state.total = payload.total || 0;
            this.state.datasets = payload.datasets || [];
            this.state.datasetLabel = payload.dataset_label || "Dataset";
            this.state.dataset = payload.dataset || this.state.dataset;
            this.state.asOf = payload.as_of || "";
        } catch (error) {
            this.state.error =
                error?.data?.message || error?.message || "Could not load compliance reports.";
        } finally {
            this.state.loading = false;
        }
    }

    onDataset(id) {
        this.state.dataset = id;
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

    openRecord(rec) {
        if (!rec?.action_xmlid) {
            return;
        }
        this.action.doAction(rec.action_xmlid, {
            additionalContext: {
                ca_mode: "detail",
                ca_res_id: rec.id,
                active_id: rec.id,
            },
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    printReport() {
        window.print();
    }

    exportCsv() {
        const rows = [
            ["Name", "Detail", "Status", "When", "Property", "Assignee", "Overdue"],
            ...this.state.records.map((rec) => [
                rec.name,
                rec.secondary,
                this.stateLabel(rec.state),
                rec.when || "",
                rec.property || "",
                rec.assignee || "",
                rec.is_overdue ? "Yes" : "No",
            ]),
        ];
        const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `compliance_${this.state.dataset}_report.csv`;
        link.click();
        URL.revokeObjectURL(url);
        this.notification.add("CSV exported.", { type: "success" });
    }
}

registry.category("actions").add("compliance_audit_management.action_reports", ComplianceReports);
