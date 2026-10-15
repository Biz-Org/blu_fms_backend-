import { Component } from "@odoo/owl";

export class CaKpiCard extends Component {
    static template = "compliance_audit_management.CaKpiCard";
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

export class CaStatusBadge extends Component {
    static template = "compliance_audit_management.CaStatusBadge";
    static props = {
        state: { type: String, optional: true },
        label: { type: String, optional: true },
    };
    get tone() {
        const state = this.props.state || "";
        if (["closed", "completed", "resolved", "verified", "submitted", "active", "compliant"].includes(state)) {
            return "success";
        }
        if (["overdue", "expired", "failed", "critical", "high"].includes(state)) {
            return "danger";
        }
        if (["pending", "pending_review", "pending_verification", "in_progress", "expiring_soon", "renewal_due", "under_renewal"].includes(state)) {
            return "warning";
        }
        if (["open", "scheduled", "assigned", "draft"].includes(state)) {
            return "info";
        }
        return "muted";
    }
    get text() {
        return this.props.label || (this.props.state || "").replace(/_/g, " ");
    }
}

export class CaEmptyState extends Component {
    static template = "compliance_audit_management.CaEmptyState";
    static props = {
        title: String,
        hint: { type: String, optional: true },
    };
}

export class CaProgressBar extends Component {
    static template = "compliance_audit_management.CaProgressBar";
    static props = {
        label: String,
        value: Number,
        tone: { type: String, optional: true },
    };
    get width() {
        const value = Math.max(0, Math.min(100, this.props.value || 0));
        return `${value}%`;
    }
    get percentLabel() {
        return `${Math.round(this.props.value || 0)}%`;
    }
    get toneClass() {
        const value = this.props.value || 0;
        if (this.props.tone) {
            return this.props.tone;
        }
        if (value >= 95) {
            return "success";
        }
        if (value < 80) {
            return "danger";
        }
        return "primary";
    }
}

export const CA_COMPONENTS = { CaKpiCard, CaStatusBadge, CaEmptyState, CaProgressBar };
