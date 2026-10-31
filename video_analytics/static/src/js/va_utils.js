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

export function formatDatetime(value) {
    if (!value) {
        return "—";
    }
    const text = String(value).replace("T", " ");
    return text.length > 19 ? text.slice(0, 19) : text;
}

export function formatConfidence(value) {
    if (value === false || value === null || value === undefined || value === "") {
        return "—";
    }
    return `${value}%`;
}

export function formatPercent(value) {
    if (value === false || value === null || value === undefined || value === "") {
        return "—";
    }
    return `${value}%`;
}

export function meterWidth(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) {
        return "0%";
    }
    return `${Math.min(100, number)}%`;
}

export function formatTime(value) {
    const text = formatDatetime(value);
    if (text === "—") {
        return text;
    }
    return text.length >= 16 ? text.slice(11, 16) : text;
}

export const WORKFLOW_STEPS = [
    { id: "cctv", label: "CCTV event" },
    { id: "detection", label: "AI detection" },
    { id: "alert", label: "Alert" },
    { id: "verification", label: "Verification" },
    { id: "incident", label: "Incident" },
    { id: "resolution", label: "Resolution" },
    { id: "close", label: "Close" },
];

const WORKFLOW_STATE_INDEX = {
    open: 2,
    acknowledged: 3,
    investigating: 4,
    resolved: 5,
    closed: 6,
    false_positive: 3,
};

export function workflowInfo(event, options = {}) {
    const highlight = options.highlight || "";
    let index = -1;
    let rejected = false;
    if (event && event.state) {
        index = WORKFLOW_STATE_INDEX[event.state];
        if (index === undefined) {
            index = event.detection_id ? 1 : 2;
        }
        rejected = event.state === "false_positive";
    } else if (event && event.detection_id) {
        index = 1;
    } else if (highlight) {
        index = WORKFLOW_STEPS.findIndex((step) => step.id === highlight);
    }
    return {
        rejected,
        currentId: index >= 0 ? WORKFLOW_STEPS[index].id : "",
        steps: WORKFLOW_STEPS.map((step, i) => ({
            ...step,
            done: index >= 0 && i < index && !(rejected && i > 3),
            current: index >= 0 && i === index,
            rejected: rejected && i === 3,
        })),
    };
}

export const VaFormatMixin = {
    formatDatetime,
    formatTime,
    formatConfidence,
    formatPercent,
    meterWidth,
    workflowInfo,
};

export const VaScreenProps = {
    session: { type: Object },
    searchQuery: { type: String, optional: true },
    onNavigate: { type: Function, optional: true },
};
