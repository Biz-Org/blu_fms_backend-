/** @odoo-module **/

export function statusTone(state) {
    const map = {
        submitted: "info",
        assigned: "info",
        in_progress: "warning",
        pending: "warning",
        completed: "success",
        closed: "muted",
        approved: "success",
        denied: "danger",
        verified: "success",
        checked_in: "success",
        checked_out: "muted",
        cancelled: "danger",
        requested: "info",
        confirmed: "success",
        successful: "success",
        failed: "danger",
    };
    return map[state] || "muted";
}

export function formatLabel(state) {
    if (!state) {
        return "";
    }
    return state.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
