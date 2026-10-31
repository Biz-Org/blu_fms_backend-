/** @odoo-module **/

/** Format a number for KPI / count display. */
export function formatCount(n) {
    const value = Number(n);
    if (!Number.isFinite(value)) {
        return "0";
    }
    return Math.trunc(value).toLocaleString();
}

/** Compact relative time for tables (e.g. "2h remaining" / "Today"). */
export function formatRelative(value) {
    if (!value) {
        return "—";
    }
    const raw = String(value).replace(" ", "T");
    const date = new Date(raw.endsWith("Z") || raw.includes("+") ? raw : `${raw}Z`);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    const diffMs = date.getTime() - Date.now();
    const absMin = Math.round(Math.abs(diffMs) / 60000);
    if (absMin < 60) {
        return diffMs >= 0 ? `${absMin}m remaining` : `${absMin}m ago`;
    }
    const absHr = Math.round(absMin / 60);
    if (absHr < 24) {
        return diffMs >= 0 ? `${absHr}h remaining` : `${absHr}h ago`;
    }
    const absDay = Math.round(absHr / 24);
    if (absDay === 1 && diffMs < 0) {
        return "Yesterday";
    }
    if (diffMs < 0 && absDay < 2) {
        return "Today";
    }
    return diffMs >= 0 ? `${absDay}d remaining` : `${absDay}d ago`;
}

/** Human duration from decimal hours. */
export function formatDurationHours(hours) {
    const value = Number(hours) || 0;
    if (value <= 0) {
        return "0m";
    }
    const h = Math.floor(value);
    const m = Math.round((value - h) * 60);
    if (!h) {
        return `${m}m`;
    }
    return m ? `${h}h ${m}m` : `${h}h`;
}

export function priorityLabel(priority) {
    const map = { "0": "Low", "1": "Medium", "2": "High", "3": "Urgent" };
    return map[String(priority)] || "Normal";
}

/** Format an Odoo date/datetime string for display. */
export function formatDate(value) {
    if (!value) {
        return "—";
    }
    const raw = String(value).replace(" ", "T");
    const date = new Date(raw.endsWith("Z") || raw.includes("+") ? raw : `${raw}Z`);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

/** CSS modifier class for a workflow status badge. */
export function statusClass(state) {
    const key = String(state || "").toLowerCase();
    const map = {
        draft: "we-badge-muted",
        active: "we-badge-success",
        inactive: "we-badge-muted",
        archived: "we-badge-muted",
        running: "we-badge-info",
        waiting_approval: "we-badge-warning",
        waiting_task: "we-badge-warning",
        waiting: "we-badge-warning",
        escalated: "we-badge-danger",
        overdue: "we-badge-danger",
        completed: "we-badge-success",
        done: "we-badge-success",
        failed: "we-badge-danger",
        pending: "we-badge-warning",
        approved: "we-badge-success",
        rejected: "we-badge-danger",
        open: "we-badge-info",
        in_progress: "we-badge-info",
        queued: "we-badge-muted",
        sent: "we-badge-success",
        notified: "we-badge-info",
        triggered: "we-badge-warning",
        skipped: "we-badge-muted",
        published: "we-badge-info",
    };
    return map[key] || "we-badge-muted";
}

/** Display label for a Many2one tuple `[id, name]` or false. */
export function userLabel(m2o) {
    if (!m2o) {
        return "—";
    }
    if (Array.isArray(m2o)) {
        return m2o[1] || String(m2o[0] || "—");
    }
    if (typeof m2o === "object" && m2o.display_name) {
        return m2o.display_name;
    }
    return String(m2o);
}

/** Extract a user-friendly message from an RPC / OWL error (no traceback dump). */
export function extractError(err) {
    if (!err) {
        return "An unexpected error occurred.";
    }
    if (typeof err === "string") {
        return err.split("\n")[0].trim() || "An unexpected error occurred.";
    }
    const data = err.data || err;
    if (data && typeof data === "object") {
        if (data.message && typeof data.message === "string") {
            return data.message.split("\n")[0].trim();
        }
        if (data.arguments && data.arguments.length) {
            const first = data.arguments[0];
            if (typeof first === "string") {
                return first.split("\n")[0].trim();
            }
        }
    }
    if (err.message && typeof err.message === "string") {
        const msg = err.message.split("\n")[0].trim();
        if (msg && !msg.includes("Traceback") && !msg.includes("odoo.exceptions")) {
            return msg;
        }
    }
    return "Request failed. Please try again.";
}

/** Node types matching `workflow.engine.node` NODE_TYPES. */
export const NODE_TYPES = [
    { id: "start", label: "Trigger", icon: "fa-play-circle" },
    { id: "action", label: "Action", icon: "fa-bolt" },
    { id: "approval", label: "Approval", icon: "fa-check-square-o" },
    { id: "task", label: "Task", icon: "fa-tasks" },
    { id: "conditional", label: "Condition", icon: "fa-code-fork" },
    { id: "notification", label: "Notification", icon: "fa-bell-o" },
    { id: "end", label: "End", icon: "fa-stop-circle" },
];

/** Rule types matching `workflow.engine.condition.rule` RULE_TYPES. */
export const RULE_TYPES = [
    { id: "approval_routing", label: "Approval Routing" },
    { id: "assignment", label: "Assignment" },
    { id: "branch", label: "Branch" },
];

/** Criteria matching backend CRITERIA. */
export const CRITERIA = [
    { id: "department", label: "Department" },
    { id: "role", label: "Role" },
    { id: "value", label: "Value" },
    { id: "property", label: "Property" },
    { id: "site", label: "Site" },
    { id: "module", label: "Module" },
];

/** Operators matching backend OPERATORS. */
export const OPERATORS = [
    { id: "=", label: "equals" },
    { id: "!=", label: "does not equal" },
    { id: "in", label: "in" },
    { id: "<", label: "is less than" },
    { id: "<=", label: "is less or equal" },
    { id: ">", label: "is greater than" },
    { id: ">=", label: "is greater or equal" },
];
