import { Component } from "@odoo/owl";

export class FsKpiCard extends Component {
    static template = "fire_safety_management.FsKpiCard";
    static props = {
        label: String,
        value: { type: [Number, String] },
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
        hint: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };
    onClick() {
        this.props.onClick?.();
    }
}

export class FsStatusBadge extends Component {
    static template = "fire_safety_management.FsStatusBadge";
    static props = {
        state: { type: String, optional: true },
        label: { type: String, optional: true },
    };
    get tone() {
        const state = this.props.state || "";
        if (["closed", "completed", "resolved", "operational", "pass"].includes(state)) {
            return "success";
        }
        if (["active", "critical", "fail", "faulty", "expired", "cancelled"].includes(state)) {
            return "danger";
        }
        if (["pending", "overdue", "inspection_due", "service_due", "investigating", "in_progress", "done", "rescheduled"].includes(state)) {
            return "warning";
        }
        if (["open", "scheduled"].includes(state)) {
            return "info";
        }
        return "muted";
    }
    get text() {
        return this.props.label || (this.props.state || "").replace(/_/g, " ");
    }
}

export class FsEmptyState extends Component {
    static template = "fire_safety_management.FsEmptyState";
    static props = {
        title: String,
        hint: { type: String, optional: true },
    };
}

export const FS_COMPONENTS = { FsKpiCard, FsStatusBadge, FsEmptyState };
