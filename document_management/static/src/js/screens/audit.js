/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, compactFilters, downloadCsv, extractError } from "../dm_utils";

const PREVIEW_ROWS = [
    {
        id: "preview-1",
        timestamp: "2023-10-27 14:32:01",
        user: "jsmith@utility.com",
        document: "Water_Main_Spec_v2.pdf",
        action: "downloaded",
        preview: true,
    },
    {
        id: "preview-2",
        timestamp: "2023-10-27 14:28:45",
        user: "automated_sync",
        document: "Q3_Meter_Readings.csv",
        action: "uploaded",
        preview: true,
    },
    {
        id: "preview-3",
        timestamp: "2023-10-27 14:15:22",
        user: "unknown_ip_192.168.x",
        document: "Confidential_Q4_Projections.xlsx",
        action: "unauthorized_access",
        preview: true,
        alert: true,
    },
    {
        id: "preview-4",
        timestamp: "2023-10-27 14:15:10",
        user: "admin.klee",
        document: "Employee_Handbook_2024.pdf",
        action: "metadata_modified",
        preview: true,
    },
    {
        id: "preview-5",
        timestamp: "2023-10-27 13:40:05",
        user: "mchen@vendor.com",
        document: "Vendor_Agreement_Draft.docx",
        action: "viewed",
        preview: true,
    },
];

const PREVIEW_ALERTS = [
    {
        id: "alert-1",
        title: "Multiple failed logins (12)",
        detail: "ip: 192.168.45.2 - 14:15",
    },
    {
        id: "alert-2",
        title: "Unauthorized delete attempt",
        detail: "User: guest_01 - 11:32",
    },
];

const PREVIEW_BREAKDOWN = [
    { action: "View", count: 80, color: "#5629CE" },
    { action: "DL", count: 38, color: "#7dd3fc" },
    { action: "Up", count: 18, color: "#86efac" },
    { action: "Edit", count: 26, color: "#fdba74" },
    { action: "Oth", count: 14, color: "#d1d5db" },
];

const PREVIEW_USERS = [
    { name: "automated_sync", count: 4201, rank: 1 },
    { name: "jsmith@utility.com", count: 3422, rank: 2 },
    { name: "admin.klee", count: 1566, rank: 3 },
];

const ACTION_LABELS = {
    downloaded: "DOWNLOAD",
    uploaded: "UPLOAD",
    unauthorized_access: "ACCESS",
    metadata_modified: "MODIFY META",
    viewed: "VIEW",
    created: "CREATE",
    access_changed: "SHARE",
    submitted: "SUBMIT",
    approved: "APPROVE",
    rejected: "REJECT",
    returned: "RETURN",
    expiry_renewed: "RENEW",
    archived: "ARCHIVE",
    restored: "RESTORE",
    deleted: "DELETE",
};

export class AuditScreen extends Component {
    static template = "document_management.Audit";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            rows: [],
            kpis: null,
            filters: {
                event_type: "",
                document: "",
                user: "",
                date_from: "",
                date_to: "",
                document_id: this.props.documentId || "",
            },
            csv: null,
            breakdown: [],
            topUsers: [],
            alerts: [],
            total: 0,
            offset: 0,
            limit: 50,
            page: 1,
            query: "",
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("document.management.ui.api", "get_audit_data", [
                compactFilters(this.state.filters),
                this.state.offset,
                this.state.limit,
            ]);
            this.state.rows = data.rows || [];
            this.state.kpis = data.kpis || {};
            this.state.breakdown = data.breakdown || [];
            this.state.topUsers = data.top_users || [];
            this.state.alerts = data.security_alerts || [];
            this.state.total = data.total || 0;
        } catch (err) {
            this.state.error = extractError(err);
            this.state.rows = [];
            this.state.kpis = null;
        } finally {
            this.state.loading = false;
        }
    }

    get usePreview() {
        return true;
    }

    get isEmpty() {
        return !this.displayRows.length;
    }

    get displayRows() {
        if (this.usePreview) {
            return PREVIEW_ROWS;
        }
        return this.state.rows || [];
    }

    get displayAlerts() {
        if (this.usePreview) {
            return PREVIEW_ALERTS;
        }
        return (this.state.alerts || []).map((alert) => ({
            id: alert.id,
            title: this.actionLabel({ action: alert.action }),
            detail: `${alert.user || "unknown"} · ${this.timeLabel(alert.timestamp)}`,
        }));
    }

    get displayBreakdown() {
        if (this.usePreview) {
            return PREVIEW_BREAKDOWN;
        }
        const colors = ["#5629CE", "#38bdf8", "#5eead4", "#4ade80", "#fb923c"];
        return (this.state.breakdown || []).slice(0, 5).map((row, index) => ({
            action: this.shortAction(row.action),
            count: row.count,
            color: colors[index % colors.length],
        }));
    }

    get displayUsers() {
        if (this.usePreview) {
            return PREVIEW_USERS;
        }
        return (this.state.topUsers || []).map((user, index) => Object.assign({}, user, { rank: index + 1 }));
    }

    get eventCount() {
        if (this.usePreview) {
            return 124592;
        }
        return (this.state.kpis && this.state.kpis.activity_events) || 0;
    }

    get uploadCount() {
        if (this.usePreview) {
            return 8401;
        }
        return (this.state.kpis && this.state.kpis.uploads) || 0;
    }

    get downloadCount() {
        if (this.usePreview) {
            return 45210;
        }
        return (this.state.kpis && this.state.kpis.downloads) || 0;
    }

    get shareCount() {
        if (this.usePreview) {
            return 1294;
        }
        return (this.state.kpis && this.state.kpis.shares) || 0;
    }

    get eventHint() {
        return this.usePreview ? "↑ 12%" : "";
    }

    get uploadHint() {
        return this.usePreview ? "↑ 5%" : "";
    }

    get downloadHint() {
        return this.usePreview ? "↓ 2%" : "";
    }

    get shareHint() {
        return this.usePreview ? "↑ 18%" : "";
    }

    get summaryDate() {
        if (this.usePreview) {
            return "Today, Oct 27";
        }
        const now = new Date();
        return `Today, ${now.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
    }

    get pageNumbers() {
        return [1, 2, 3];
    }

    get pageCount() {
        if (this.usePreview) {
            return 3;
        }
        return Math.max(1, Math.ceil((this.state.total || 0) / this.state.limit) || 1);
    }

    get showingLabel() {
        if (this.usePreview) {
            return "Showing 1-50 of 124,592 records";
        }
        const total = this.state.total || 0;
        if (!total) {
            return "Showing 0 of 0 records";
        }
        const start = this.state.offset + 1;
        const end = Math.min(total, this.state.offset + this.state.limit);
        return `Showing ${start}-${end} of ${this.comma(total)} records`;
    }

    get canPrev() {
        if (this.usePreview) {
            return this.state.page > 1;
        }
        return this.state.offset > 0;
    }

    get canNext() {
        if (this.usePreview) {
            return this.state.page < this.pageCount;
        }
        return this.state.offset + this.state.limit < this.state.total;
    }

    comma(value) {
        return Number(value || 0).toLocaleString("en-US");
    }

    cell(value) {
        return value || "—";
    }

    actionLabel(row) {
        const key = row && row.action;
        return ACTION_LABELS[key] || String(key || "—").replace(/_/g, " ").toUpperCase();
    }

    actionClass(row) {
        const label = this.actionLabel(row);
        if (label === "DOWNLOAD") {
            return "dm-audit-act is-down";
        }
        if (label === "UPLOAD") {
            return "dm-audit-act is-up";
        }
        if (label === "ACCESS") {
            return "dm-audit-act is-access";
        }
        return "dm-audit-act is-mute";
    }

    shortAction(action) {
        const map = {
            viewed: "View",
            downloaded: "DL",
            uploaded: "Up",
            metadata_modified: "Edit",
            unauthorized_access: "Oth",
        };
        return map[action] || String(action || "Oth").slice(0, 4);
    }

    timeLabel(value) {
        if (!value) {
            return "—";
        }
        const text = String(value);
        if (text.length >= 19 && text.indexOf("-") !== -1) {
            return text.slice(0, 19).replace("T", " ");
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return text;
        }
        const pad = (part) => String(part).padStart(2, "0");
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
    }

    rowClass(row) {
        if (row.alert || row.action === "unauthorized_access") {
            return "is-alert";
        }
        return "";
    }

    rowKey(row) {
        return row.id || `${row.timestamp}-${row.document}`;
    }

    barStyle(row) {
        const max = Math.max(...this.displayBreakdown.map((item) => Number(item.count) || 0), 1);
        const height = Math.max(10, Math.round((Number(row.count) || 0) / max * 88));
        return `height:${height}px;background:${row.color || "#5629CE"}`;
    }

    userCount(user) {
        return this.comma(user.count);
    }

    setPage(ev) {
        const page = Number(ev.currentTarget.dataset.page) || 1;
        if (page > this.pageCount) {
            return;
        }
        this.state.page = page;
        this.state.offset = (page - 1) * this.state.limit;
        if (!this.usePreview) {
            this.refresh();
        }
    }

    prevPage() {
        if (!this.canPrev) {
            return;
        }
        this.state.page = Math.max(1, this.state.page - 1);
        this.state.offset = Math.max(0, this.state.offset - this.state.limit);
        if (!this.usePreview) {
            this.refresh();
        }
    }

    nextPage() {
        if (!this.canNext) {
            return;
        }
        this.state.page += 1;
        this.state.offset += this.state.limit;
        if (!this.usePreview) {
            this.refresh();
        }
    }

    applyFilters() {
        this.state.offset = 0;
        this.state.page = 1;
        this.refresh();
    }

    async exportCsv() {
        if (this.usePreview) {
            const lines = ["timestamp,user,document,action"];
            PREVIEW_ROWS.forEach((row) => {
                lines.push([row.timestamp, row.user, row.document, this.actionLabel(row)].join(","));
            });
            downloadCsv({ filename: "document-audit.csv", csv: `${lines.join("\n")}\n` });
            return;
        }
        const data = await this.orm.call("document.management.ui.api", "export_audit", [
            compactFilters(this.state.filters),
        ]);
        this.state.csv = data;
        downloadCsv(data);
    }
}
