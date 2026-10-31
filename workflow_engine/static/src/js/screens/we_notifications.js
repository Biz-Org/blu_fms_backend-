/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, formatDate, statusClass, userLabel } from "../we_utils";
import { MOCK_NOTIFICATIONS } from "../we_mockup";

const APPROVAL_FIELDS = [
    "id", "name", "state", "user_id", "level_id", "execution_id",
    "date_requested", "date_decided", "comment", "decided_by",
];
const NOTIF_FIELDS = [
    "id", "name", "channel", "state", "user_id", "execution_id",
    "date_sent", "error_message", "reminder", "escalation", "create_date",
];

export class WeNotifications extends Component {
    static template = "workflow_engine.Notifications";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            tab: "approvals",
            loading: true,
            error: null,
            pending: [],
            history: [],
            notifications: [],
            filterPendingOnly: false,
            search: "",
            selectedId: null,
            modalOpen: false,
            modalAction: null,
            modalRecord: null,
            comment: "",
            busy: false,
        });
        onWillStart(() => this.load());
    }

    get uid() {
        return this.props.session?.uid;
    }

    get filteredPending() {
        const source = this.state.pending.length ? this.state.pending : MOCK_NOTIFICATIONS.pending;
        const q = (this.state.search || "").trim().toLowerCase();
        return source.filter((rec) => {
            if (!q) {
                return true;
            }
            const name = rec.name || "";
            const requester = rec.requester || userLabel(rec.user_id);
            return name.toLowerCase().includes(q) || requester.toLowerCase().includes(q);
        });
    }

    get selectedPending() {
        return this.filteredPending.find((r) => r.id === this.state.selectedId) || this.filteredPending[0] || null;
    }

    get filteredNotifications() {
        if (!this.state.filterPendingOnly) {
            return this.state.notifications;
        }
        return this.state.notifications.filter((n) => n.state === "queued");
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    selectRecord(rec) {
        this.state.selectedId = rec.id;
    }

    requestCode(rec) {
        return rec.code || `REQ-${String(rec.id).padStart(4, "0")}`;
    }

    requesterName(rec) {
        return rec.requester || userLabel(rec.user_id);
    }

    requesterRole(rec) {
        return rec.role || userLabel(rec.level_id);
    }

    priorityOf(rec) {
        if (rec.priority) {
            return rec.priority;
        }
        const n = rec.id % 3;
        return n === 0 ? "High" : n === 1 ? "Medium" : "Low";
    }

    priorityClass(rec) {
        const p = this.priorityOf(rec);
        return p === "High" ? "we-badge-danger" : p === "Medium" ? "we-badge-warning" : "we-badge-muted";
    }

    slaHoursLeft(rec) {
        if (!rec?.date_requested) {
            return 24;
        }
        const raw = String(rec.date_requested).replace(" ", "T");
        const start = new Date(raw.endsWith("Z") || raw.includes("+") ? raw : `${raw}Z`).getTime();
        return Math.round((start + 24 * 3600 * 1000 - Date.now()) / 3600000);
    }

    slaLabel(rec) {
        if (rec.sla) {
            return rec.sla;
        }
        const h = this.slaHoursLeft(rec);
        if (h < 0) {
            return `${Math.abs(h)}h Overdue`;
        }
        if (h < 24) {
            return `${h}h Remaining`;
        }
        return `${Math.ceil(h / 24)}d Remaining`;
    }

    slaTone(rec) {
        if (rec.slaTone) {
            return rec.slaTone;
        }
        const h = this.slaHoursLeft(rec);
        return h < 4 ? "we-sla-danger" : h < 24 ? "we-sla-warn" : "we-sla-ok";
    }

    timelineSteps(rec) {
        if (rec?.timeline?.length) {
            return rec.timeline;
        }
        return [
            { kind: "current", title: "Current review", meta: "Assigned to: You", tag: "Current" },
            { kind: "start", title: "Request Submitted", meta: rec?.date || this.formatDate(rec?.date_requested) },
        ];
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [pending, history, notifications] = await Promise.all([
                this.orm.call("workflow.engine.ui.api", "search_approvals", [[["state", "=", "pending"]], 0, 100]),
                this.orm.call("workflow.engine.ui.api", "search_approvals", [[["state", "in", ["approved", "rejected"]]], 0, 100]),
                this.orm.call("workflow.engine.ui.api", "search_notifications", [[], 0, 100]),
            ]);
            this.state.pending = pending.records || [];
            this.state.history = history.records || [];
            this.state.notifications = notifications.records || [];
            if (!this.state.selectedId && this.state.pending.length) {
                this.state.selectedId = this.state.pending[0].id;
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    openDecide(rec, action) {
        if (typeof rec?.id === "string") {
            return;
        }
        this.state.modalRecord = rec;
        this.state.modalAction = action;
        this.state.comment = "";
        this.state.modalOpen = true;
    }

    closeModal() {
        this.state.modalOpen = false;
        this.state.modalRecord = null;
        this.state.modalAction = null;
        this.state.comment = "";
    }

    async confirmDecide() {
        if (!this.state.modalRecord || !this.state.modalAction || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const method = this.state.modalAction === "approve" ? "approve_request" : "reject_request";
            await this.orm.call(
                "workflow.engine.ui.api",
                method,
                [this.state.modalRecord.id, this.state.comment || false]
            );
            this.notification.add(
                this.state.modalAction === "approve" ? "Approval approved." : "Approval rejected.",
                { type: "success" }
            );
            this.closeModal();
            await this.load();
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    formatDate = formatDate;
    statusClass = statusClass;
    userLabel = userLabel;
}
