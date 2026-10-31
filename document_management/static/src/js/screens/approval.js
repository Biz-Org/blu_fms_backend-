/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, display, extractError, formatBytes, formatLabel, readFileAsPayload } from "../dm_utils";

const PREVIEW_ROWS = [
    {
        id: "preview-vc",
        document_id: "preview-vc",
        document: "Vendor Contract v2.1",
        requester: "Sarah Jenkins",
        type: "Contract",
        submitted_at: "Oct 24, 2023",
        status: "reviewing",
        preview: true,
    },
    {
        id: "preview-q3",
        document_id: "preview-q3",
        document: "Q3 Compliance Report",
        requester: "Marcus Chen",
        type: "Report",
        submitted_at: "Oct 22, 2023",
        status: "pending",
        preview: true,
    },
    {
        id: "preview-sp",
        document_id: "preview-sp",
        document: "Safety Policy Update 2024",
        requester: "Elena Rodriguez",
        type: "Policy",
        submitted_at: "Oct 20, 2023",
        status: "pending",
        preview: true,
    },
];

const PREVIEW_PANELS = {
    "preview-vc": {
        id: "preview-vc",
        preview: true,
        document: "Vendor Contract v2.1",
        code: "DOC-9921",
        type: "Contract",
        requester: "Sarah Jenkins",
        department: "Procurement",
        submitted_at: "Oct 24, 2023, 14:30",
        size_label: "2.4 MB",
        notes: '"Please verify the penalty clauses in section 4.2 before final approval." - M. Davis',
        steps: [
            { id: "s1", name: "Legal Review", state: "approved", caption: "Approved by M. Davis - Oct 25" },
            { id: "s2", name: "Finance Review", state: "active", caption: "Pending your approval" },
            { id: "s3", name: "Final Sign-off", state: "waiting", caption: "Awaiting previous steps" },
        ],
        request: false,
    },
    "preview-q3": {
        id: "preview-q3",
        preview: true,
        document: "Q3 Compliance Report",
        code: "DOC-4408",
        type: "Report",
        requester: "Marcus Chen",
        department: "Compliance",
        submitted_at: "Oct 22, 2023, 09:15",
        size_label: "1.1 MB",
        notes: "Waiting on compliance sign-off.",
        steps: [
            { id: "s1", name: "Compliance Review", state: "active", caption: "Pending your approval" },
            { id: "s2", name: "Director Sign-off", state: "waiting", caption: "Awaiting previous steps" },
        ],
        request: false,
    },
    "preview-sp": {
        id: "preview-sp",
        preview: true,
        document: "Safety Policy Update 2024",
        code: "DOC-1184",
        type: "Policy",
        requester: "Elena Rodriguez",
        department: "Health & Safety",
        submitted_at: "Oct 20, 2023, 16:40",
        size_label: "860 KB",
        notes: "Policy wording is in legal review.",
        steps: [
            { id: "s1", name: "Policy Review", state: "active", caption: "Pending your approval" },
            { id: "s2", name: "Final Sign-off", state: "waiting", caption: "Awaiting previous steps" },
        ],
        request: false,
    },
};

export class ApprovalScreen extends Component {
    static template = "document_management.Approval";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            rows: [],
            kpis: null,
            tab: "pending",
            selected: false,
            comment: "",
            expiryDate: "",
            stepName: "",
            approverId: "",
            showRequest: false,
            showFilter: false,
            drawerClosed: false,
            needComment: false,
        });
        onWillStart(() => this.refresh());
        onWillUpdateProps((next) => {
            if (next.documentId !== this.props.documentId) {
                return this.refresh();
            }
        });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("document.management.ui.api", "get_approval_board", [
                this.state.tab,
                { document_id: this.props.documentId || false },
            ]);
            this.state.rows = data.rows || [];
            this.state.kpis = data.kpis || {};
            this.state.selected = data.selected || false;
        } catch (err) {
            this.state.error = extractError(err);
            this.state.rows = [];
            this.state.kpis = null;
        } finally {
            this.state.loading = false;
        }
        if (!this.state.error && this.state.rows.length && !this.state.selected && !this.state.drawerClosed) {
            await this.openLiveRow(this.state.rows[0]);
        }
    }

    get usePreview() {
        return !(this.state.rows || []).length;
    }

    get isEmpty() {
        return !this.displayRows.length;
    }

    get displayRows() {
        if (!this.usePreview) {
            return this.state.rows || [];
        }
        if (this.state.tab === "pending") {
            return PREVIEW_ROWS;
        }
        return [];
    }

    get pendingCount() {
        if (this.usePreview) {
            return 24;
        }
        return (this.state.kpis && this.state.kpis.pending_approval) || 0;
    }

    get approvedCount() {
        if (this.usePreview) {
            return 186;
        }
        return (this.state.kpis && this.state.kpis.approved) || 0;
    }

    get expiringCount() {
        if (this.usePreview) {
            return 18;
        }
        return (this.state.kpis && this.state.kpis.expiring_soon) || 0;
    }

    get expiredCount() {
        if (this.usePreview) {
            return 6;
        }
        return (this.state.kpis && this.state.kpis.expired) || 0;
    }

    get pendingHint() {
        return this.usePreview ? "↑ 12%" : "";
    }

    get approvedHint() {
        return this.usePreview ? "↑ 5%" : "";
    }

    get expiringHint() {
        return this.usePreview ? "↑ 3%" : "";
    }

    get expiredHint() {
        return this.usePreview ? "↓ 8%" : "";
    }

    get panel() {
        if (this.state.drawerClosed) {
            return false;
        }
        if (this.state.selected) {
            return this.state.selected;
        }
        if (this.usePreview && this.state.tab === "pending") {
            return PREVIEW_PANELS["preview-vc"];
        }
        return false;
    }

    get selectedSteps() {
        const panel = this.panel;
        return (panel && panel.steps) || [];
    }

    get panelNotes() {
        const panel = this.panel;
        if (!panel) {
            return "No reviewer notes yet.";
        }
        if (panel.notes) {
            return panel.notes;
        }
        const notes = panel.reviewer_notes || [];
        if (Array.isArray(notes) && notes.length) {
            return notes.filter(Boolean).join(" ");
        }
        const commented = (panel.steps || []).find((step) => step.comment);
        return commented ? commented.comment : "No reviewer notes yet.";
    }

    get requestId() {
        const panel = this.panel;
        return (panel && panel.request && panel.request.id) || "";
    }

    get panelSize() {
        const panel = this.panel;
        if (!panel) {
            return "—";
        }
        if (panel.size_label) {
            return panel.size_label;
        }
        return formatBytes(panel.file_size);
    }

    get panelTypeLabel() {
        const panel = this.panel;
        if (!panel) {
            return "Document";
        }
        return panel.type || "Document";
    }

    get hasPanel() {
        return Boolean(this.panel);
    }

    display(value) {
        return display(value);
    }

    label(value) {
        const raw = formatLabel(value);
        if (!raw || raw === "—") {
            return raw;
        }
        return raw.replace(/\b\w/g, (char) => char.toUpperCase());
    }

    sizeLabel(value) {
        return formatBytes(value);
    }

    get users() {
        return this.props.session.users || [];
    }

    rowKey(row) {
        return row.id || row.document_id || row.document;
    }

    isSelected(row) {
        const panel = this.panel;
        if (!panel || !row) {
            return false;
        }
        if (row.preview || panel.preview) {
            return panel.id === row.id;
        }
        return panel.document_id === row.document_id;
    }

    statusLabel(row) {
        const status = String((row && row.status) || "").toLowerCase();
        if (status === "reviewing" || status === "pending_approval") {
            return "REVIEWING";
        }
        if (status === "pending") {
            return "PENDING";
        }
        if (status === "approved") {
            return "APPROVED";
        }
        if (status === "rejected") {
            return "REJECTED";
        }
        if (status === "expired") {
            return "EXPIRED";
        }
        return this.label(row && row.status).toUpperCase();
    }

    statusClass(row) {
        const label = this.statusLabel(row);
        if (label === "REVIEWING") {
            return "dm-appr-status is-review";
        }
        if (label === "PENDING") {
            return "dm-appr-status is-pending";
        }
        if (label === "APPROVED") {
            return "dm-appr-status is-ok";
        }
        if (label === "REJECTED" || label === "EXPIRED") {
            return "dm-appr-status is-danger";
        }
        return "dm-appr-status";
    }

    dateLabel(value) {
        if (!value) {
            return "—";
        }
        if (/[A-Za-z]/.test(String(value)) && String(value).indexOf(",") !== -1) {
            return String(value);
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }

    stepClass(step) {
        if (step.state === "approved") {
            return "dm-appr-step is-done";
        }
        if (step.state === "active") {
            return "dm-appr-step is-now";
        }
        return "dm-appr-step is-wait";
    }

    stepCaption(step) {
        if (step.caption) {
            return step.caption;
        }
        if (step.state === "approved") {
            const who = step.decided_by || step.approver || "";
            const when = this.shortDate(step.decided_at);
            return `Approved by ${who}${when ? " - " + when : ""}`.trim();
        }
        if (step.state === "active") {
            return "Pending your approval";
        }
        return "Awaiting previous steps";
    }

    shortDate(value) {
        if (!value) {
            return "";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "";
        }
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }

    setTab(ev) {
        this.state.tab = ev.currentTarget.dataset.tab;
        this.state.drawerClosed = false;
        this.refresh();
    }

    toggleFilter() {
        this.state.showFilter = !this.state.showFilter;
    }

    toggleRequest() {
        this.state.showRequest = !this.state.showRequest;
    }

    closeDrawer() {
        this.state.selected = false;
        this.state.drawerClosed = true;
    }

    async openLiveRow(row) {
        if (!row) {
            return;
        }
        if (row.preview || String(row.document_id).startsWith("preview")) {
            this.state.selected = PREVIEW_PANELS[row.id] || PREVIEW_PANELS["preview-vc"];
            this.state.drawerClosed = false;
            return;
        }
        try {
            const data = await this.orm.call("document.management.ui.api", "get_approval_board", [
                this.state.tab,
                { document_id: row.document_id, request_id: row.request_id || false },
            ]);
            this.state.selected = data.selected || false;
            this.state.drawerClosed = false;
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    async selectRow(ev) {
        const rowId = ev.currentTarget.dataset.rowId;
        const documentId = ev.currentTarget.dataset.documentId;
        if (String(rowId || documentId).startsWith("preview")) {
            this.state.selected = PREVIEW_PANELS[rowId] || PREVIEW_PANELS["preview-vc"];
            this.state.drawerClosed = false;
            return;
        }
        await this.openLiveRow({
            document_id: Number(documentId),
            request_id: Number(ev.currentTarget.dataset.requestId) || false,
        });
    }

    viewDocument() {
        const panel = this.panel;
        if (!panel || panel.preview || !panel.document_id) {
            return;
        }
        if (this.props.navigate) {
            this.props.navigate("details", { documentId: panel.document_id });
        }
    }

    async submitRequest() {
        if (!this.props.documentId) {
            this.state.error = "Select a document first.";
            return;
        }
        await this.orm.call("document.management.ui.api", "submit_for_approval", [
            this.props.documentId,
            [{ name: this.state.stepName || "Review", approver_id: Number(this.state.approverId) }],
        ]);
        this.state.showRequest = false;
        await this.refresh();
        if (this.props.refreshSession) {
            await this.props.refreshSession();
        }
    }

    isPreviewAction() {
        const panel = this.panel;
        return !panel || panel.preview || !panel.request;
    }

    async approve(ev) {
        if (this.isPreviewAction()) {
            return;
        }
        const id = Number(ev.currentTarget.dataset.id);
        await this.orm.call("document.management.ui.api", "approve", [id, this.state.comment]);
        await this.refresh();
    }

    async reject(ev) {
        if (this.isPreviewAction()) {
            return;
        }
        const id = Number(ev.currentTarget.dataset.id);
        if (!this.state.comment) {
            this.state.needComment = true;
            this.state.error = "A comment is required to reject.";
            return;
        }
        await this.orm.call("document.management.ui.api", "reject", [id, this.state.comment]);
        await this.refresh();
    }

    async requestChanges(ev) {
        if (this.isPreviewAction()) {
            return;
        }
        const id = Number(ev.currentTarget.dataset.id);
        if (!this.state.comment) {
            this.state.needComment = true;
            this.state.error = "A comment is required to request changes.";
            return;
        }
        await this.orm.call("document.management.ui.api", "request_changes", [id, this.state.comment]);
        await this.refresh();
    }

    async renew() {
        const panel = this.panel;
        if (!panel || panel.preview) {
            return;
        }
        const documentId = panel.document_id || this.props.documentId;
        await this.orm.call("document.management.ui.api", "renew_document", [
            documentId,
            this.state.expiryDate || false,
            {},
        ]);
        await this.refresh();
    }

    async replace(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const panel = this.panel;
        if (!panel || panel.preview) {
            return;
        }
        const payload = await readFileAsPayload(file);
        const documentId = panel.document_id || this.props.documentId;
        await this.orm.call("document.management.ui.api", "renew_document", [
            documentId,
            this.state.expiryDate || false,
            payload,
        ]);
        await this.refresh();
    }
}
