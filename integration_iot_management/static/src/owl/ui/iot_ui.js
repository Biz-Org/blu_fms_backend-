import { Component } from "@odoo/owl";

export class IotKpiCard extends Component {
    static template = "integration_iot_management.IotKpiCard";
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

export class IotStatusBadge extends Component {
    static template = "integration_iot_management.IotStatusBadge";
    static props = {
        state: { type: String, optional: true },
        label: { type: String, optional: true },
    };
    get tone() {
        const state = this.props.state || "";
        if (["online", "on", "ok", "normal", "applied", "valid", "connected", "success", "active"].includes(state)) {
            return "success";
        }
        if (["offline", "faulty", "alarm", "fault", "critical", "high", "failed", "missing", "communication_failure"].includes(state)) {
            return "danger";
        }
        if (["warning", "medium", "abnormal", "acknowledged", "maintenance"].includes(state)) {
            return "warning";
        }
        if (["open", "simulated", "configured", "draft"].includes(state)) {
            return "info";
        }
        return "muted";
    }
    get text() {
        return this.props.label || (this.props.state || "").replace(/_/g, " ");
    }
}

export class IotEmptyState extends Component {
    static template = "integration_iot_management.IotEmptyState";
    static props = {
        title: String,
        hint: { type: String, optional: true },
    };
}

export const IOT_COMPONENTS = { IotKpiCard, IotStatusBadge, IotEmptyState };
