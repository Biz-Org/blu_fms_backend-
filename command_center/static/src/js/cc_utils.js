/** @odoo-module **/

export function extractError(err) {
    const data = err && err.data;
    if (data && data.message) {
        return data.message;
    }
    if (err && err.message) {
        return String(err.message).replace(/^RPC_ERROR:?\s*/i, "");
    }
    return "The request could not be completed.";
}

export function compactFilters(filters) {
    const out = {};
    Object.entries(filters || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") {
            return;
        }
        if (value === false) {
            return;
        }
        out[key] = value;
    });
    return out;
}

export function display(value, fallback = "—") {
    if (value === undefined || value === null || value === false || value === "") {
        return fallback;
    }
    return value;
}

export function fromDatetimeLocal(value) {
    if (!value) {
        return "";
    }
    return value.replace("T", " ") + (value.length === 16 ? ":00" : "");
}

export const SEVERITIES = ["low", "medium", "high", "critical"];
export const STATES = ["open", "acknowledged", "investigating", "resolved", "closed"];
export const SOURCES = ["manual", "command_center", "video_analytics", "other"];
export const SITE_STATUSES = ["normal", "degraded", "emergency", "offline"];
export const REPORT_SOURCES = ["alerts", "incidents", "sites", "emergency"];

export function alertActions(session, alert) {
    if (!alert) {
        return [];
    }
    const state = alert.state;
    const actions = [];
    if (state === "open") {
        actions.push("acknowledge", "investigate");
    }
    if (state === "acknowledged") {
        actions.push("investigate");
    }
    if (["open", "acknowledged", "investigating"].includes(state)) {
        actions.push("assign");
        if (session.is_manager) {
            actions.push("escalate");
            if (!alert.incident_id) {
                actions.push("to_incident");
            }
        }
    }
    if (["acknowledged", "investigating"].includes(state) && session.is_manager) {
        actions.push("resolve");
    }
    if (state === "resolved" && session.is_manager) {
        actions.push("close");
    }
    if (["resolved", "closed"].includes(state) && session.is_admin) {
        actions.push("reopen");
    }
    actions.push("add_note");
    return actions;
}

export function incidentActions(session, incident) {
    if (!incident) {
        return [];
    }
    const state = incident.state;
    const actions = [];
    if (state === "open") {
        actions.push("acknowledge", "investigate");
    }
    if (state === "acknowledged") {
        actions.push("investigate");
    }
    if (["open", "acknowledged", "investigating"].includes(state)) {
        actions.push("assign");
        if (session.is_manager) {
            actions.push("escalate");
        }
    }
    if (["acknowledged", "investigating"].includes(state) && session.is_manager) {
        actions.push("resolve");
    }
    if (state === "resolved" && session.is_manager) {
        actions.push("close");
    }
    if (["resolved", "closed"].includes(state) && session.is_admin) {
        actions.push("reopen");
    }
    actions.push("add_note");
    return actions;
}

export function emergencyActions(session, alert) {
    if (!alert) {
        return [];
    }
    const state = alert.state;
    const actions = [];
    if (state === "open") {
        actions.push("acknowledge");
    }
    if (["open", "acknowledged", "investigating"].includes(state) && session.is_manager) {
        actions.push("escalate");
        if (alert.is_overdue) {
            actions.push("handle_overdue");
        }
    }
    if (["acknowledged", "investigating"].includes(state) && session.is_manager) {
        actions.push("resolve");
    }
    if (["resolved", "closed"].includes(state) && session.is_admin) {
        actions.push("reopen");
    }
    return actions;
}

export function actionClass(action) {
    if (action === "close" || action === "reopen") {
        return "cc-btn cc-btn-warn";
    }
    if (action === "acknowledge" || action === "resolve" || action === "create") {
        return "cc-btn cc-btn-primary";
    }
    return "cc-btn";
}

export const SHELL_PROPS = {
    session: { type: Object },
    navigate: { type: Function, optional: true },
    shellSearch: { type: String, optional: true },
    shellSiteId: { type: [String, Number, Boolean], optional: true },
};

export function applyShellFilters(filters, props) {
    if (!filters || !props) {
        return filters;
    }
    if (Object.prototype.hasOwnProperty.call(filters, "search") && props.shellSearch !== undefined) {
        filters.search = props.shellSearch || "";
    }
    if (Object.prototype.hasOwnProperty.call(filters, "site_id") && props.shellSiteId !== undefined && props.shellSiteId !== false) {
        filters.site_id = props.shellSiteId || "";
    }
    return filters;
}

export const WORKFLOW_STEPS = [
    { key: "event", label: "Event" },
    { key: "alert", label: "Alert" },
    { key: "incident", label: "Incident" },
    { key: "assign", label: "Assign" },
    { key: "escalate", label: "Escalate" },
    { key: "resolve", label: "Resolve" },
    { key: "close", label: "Close" },
];

export function workflowIndex(record, kind) {
    if (!record || kind === "module") {
        return -1;
    }
    if (record.state === "closed") {
        return 6;
    }
    if (record.state === "resolved") {
        return 5;
    }
    const assigned = Boolean(record.user_id || record.user_name);
    const escalated = Boolean(
        record.history_count ||
        (record.history || []).length ||
        record.state === "investigating" ||
        record.is_emergency ||
        kind === "emergency"
    );
    if (kind === "incident" || kind === "emergency" || record.incident_id || record.is_emergency) {
        if (escalated) {
            return 4;
        }
        if (assigned) {
            return 3;
        }
        return kind === "emergency" || record.is_emergency ? 4 : 2;
    }
    return 1;
}

export function workflowSteps(record, kind) {
    const current = workflowIndex(record, kind);
    return WORKFLOW_STEPS.map((step, index) => ({
        key: step.key,
        label: step.label,
        done: current >= 0 && index < current,
        current: index === current,
        last: index === WORKFLOW_STEPS.length - 1,
    }));
}

const SCREEN_WORKFLOW_INDEX = {
    dashboard: -1,
    alerts: 1,
    incidents: 2,
    emergency: 4,
};

export function workflowStepsForScreen(screen) {
    const current = Object.prototype.hasOwnProperty.call(SCREEN_WORKFLOW_INDEX, screen)
        ? SCREEN_WORKFLOW_INDEX[screen]
        : -1;
    return WORKFLOW_STEPS.map((step, index) => ({
        key: step.key,
        label: step.label,
        done: current >= 0 && index < current,
        current: index === current,
        last: index === WORKFLOW_STEPS.length - 1,
    }));
}

export function countBy(rows, key, value) {
    return (rows || []).filter((row) => row[key] === value).length;
}

export function actionLabel(action) {
    const labels = {
        acknowledge: "Acknowledge",
        investigate: "Investigate",
        assign: "Assign",
        escalate: "Escalate",
        resolve: "Resolve",
        close: "Close",
        add_note: "Add note",
        reopen: "Reopen",
        handle_overdue: "Handle overdue",
        create: "Create",
        to_incident: "Create Incident",
    };
    return labels[action] || action;
}
