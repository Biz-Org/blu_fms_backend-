import { Component } from "@odoo/owl";

export class RaKpiCard extends Component {
    static template = "reports_analytics.RaKpiCard";
    static props = {
        label: String,
        value: { type: [Number, String], optional: true },
        hint: { type: String, optional: true },
        tone: { type: String, optional: true },
        available: { type: Boolean, optional: true },
        change: { optional: true },
    };
    get display() {
        if (this.props.available === false || this.props.value === null || this.props.value === undefined || this.props.value === "") {
            return "No Data";
        }
        return this.props.value;
    }
    get tone() {
        if (this.props.available === false) {
            return "muted";
        }
        return this.props.tone || "";
    }
}

export class RaStatusBadge extends Component {
    static template = "reports_analytics.RaStatusBadge";
    static props = { state: { type: String, optional: true }, label: { type: String, optional: true } };
    get tone() {
        const state = (this.props.state || "").toLowerCase();
        if (["active", "success", "ready", "healthy", "on_target", "ok"].includes(state)) {
            return "success";
        }
        if (["failed", "critical", "danger", "triggered"].includes(state)) {
            return "danger";
        }
        if (["warning", "high", "paused", "below", "above", "draft"].includes(state)) {
            return "warning";
        }
        if (["info", "informational"].includes(state)) {
            return "info";
        }
        return "muted";
    }
    get text() {
        return this.props.label || (this.props.state || "").replace(/_/g, " ");
    }
}

export class RaEmptyState extends Component {
    static template = "reports_analytics.RaEmptyState";
    static props = { title: String, hint: { type: String, optional: true } };
}

export class RaBarChart extends Component {
    static template = "reports_analytics.RaBarChart";
    static props = { labels: Array, data: Array };
    get max() {
        return Math.max(1, ...this.props.data.map((value) => Number(value) || 0));
    }
    height(value) {
        return `${Math.max(6, (Number(value) / this.max) * 100)}%`;
    }
}

export class RaLineChart extends Component {
    static template = "reports_analytics.RaLineChart";
    static props = {
        labels: Array,
        current: Array,
        previous: { type: Array, optional: true },
    };
    points(series) {
        const values = series || [];
        if (!values.length) {
            return "";
        }
        const max = Math.max(1, ...values.map((value) => Number(value) || 0));
        const width = 600;
        const height = 200;
        return values
            .map((value, index) => {
                const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
                const y = height - ((Number(value) || 0) / max) * (height - 16) - 8;
                return `${x},${y}`;
            })
            .join(" ");
    }
}

export const RA_COMPONENTS = { RaKpiCard, RaStatusBadge, RaEmptyState, RaBarChart, RaLineChart };
