/** Shared helpers for Community OWL screens. */

export const PAGE_SIZE = 8;

export const STATUS_TONE = {
    published: "success",
    active: "success",
    confirmed: "success",
    resolved: "success",
    member: "success",
    scheduled: "warning",
    pending: "warning",
    submitted: "warning",
    waitlisted: "warning",
    in_progress: "info",
    draft: "draft",
    closed: "muted",
    expired: "danger",
    cancelled: "danger",
    archived: "muted",
    locked: "warning",
    removed: "danger",
};

export const ANNOUNCEMENT_CATEGORIES = [
    ["general", "General"],
    ["community", "Community"],
    ["maintenance", "Maintenance Updates"],
    ["events", "Events"],
    ["security", "Security"],
    ["safety", "Safety"],
    ["utilities", "Utilities"],
    ["policy", "Policy Updates"],
    ["facility", "Facility Updates"],
    ["emergency", "Emergency"],
    ["other", "Other"],
];

export const DISCUSSION_CATEGORIES = [
    ["general", "General Discussion"],
    ["suggestions", "Community Suggestions"],
    ["events", "Events"],
    ["neighborhood", "Neighborhood"],
    ["lost_found", "Lost & Found"],
    ["recommendations", "Recommendations"],
    ["facilities", "Facilities"],
    ["activities", "Community Activities"],
    ["environment", "Environment"],
    ["other", "Other"],
];

export const POLL_CATEGORIES = [
    ["events", "Events & Activities"],
    ["facilities", "Facilities"],
    ["operations", "Operations"],
    ["other", "Other"],
];

export const EVENT_CATEGORIES = [
    ["fitness", "Fitness"],
    ["meetings", "Meetings"],
    ["sports", "Sports"],
    ["activities", "Activities"],
    ["dates", "Important Dates"],
    ["other", "Other"],
];

export const NOTICE_CATEGORIES = [
    ["general", "General"],
    ["maintenance", "Maintenance"],
    ["security", "Security"],
    ["events", "Events"],
];

export const FEEDBACK_CATEGORIES = [
    ["facility", "Facility Maintenance"],
    ["amenities", "Amenities"],
    ["events", "Events"],
    ["communication", "Communication"],
    ["other", "Other"],
];

export const GROUP_CATEGORIES = [
    ["building", "Building / Tower"],
    ["association", "Resident Association"],
    ["sports", "Sports"],
    ["hobby", "Hobby"],
    ["cultural", "Cultural"],
    ["fitness", "Fitness"],
    ["parents", "Parents"],
    ["senior", "Senior Citizen"],
    ["volunteer", "Volunteer"],
    ["event", "Event-specific"],
    ["professional", "Professional"],
    ["other", "Other"],
];

export function labelOf(pairs, key) {
    const found = pairs.find((item) => item[0] === key);
    return found ? found[1] : key || "";
}

export function statusTone(state) {
    return STATUS_TONE[state] || "muted";
}

export function audienceLabel(record) {
    if (!record) {
        return "All Residents";
    }
    if (record.audience_type === "buildings") {
        return "Specific Buildings";
    }
    if (record.audience_type === "groups") {
        return "Resident Groups";
    }
    if (record.audience_type === "residents") {
        return "Specific Residents";
    }
    if (record.audience_type === "users") {
        return "Specific Users";
    }
    return "All Residents";
}

export function formatWhen(value) {
    if (!value) {
        return "—";
    }
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function formatDay(value) {
    if (!value) {
        return "—";
    }
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function stripHtml(html) {
    return (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

export function toDatetimeLocal(value) {
    if (!value) {
        return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fromDatetimeLocal(value) {
    if (!value) {
        return false;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? false : date.toISOString().slice(0, 19).replace("T", " ");
}

export function actionParams(props) {
    const action = props.action || {};
    return {
        ...(action.params || {}),
        ...(action.context || {}),
    };
}

export function pageCount(total, size = PAGE_SIZE) {
    return Math.max(1, Math.ceil((total || 0) / size));
}

export function m2mIds(value) {
    if (!value) {
        return [];
    }
    if (!Array.isArray(value)) {
        return [value];
    }
    return value.map((item) => (Array.isArray(item) ? item[0] : item)).filter(Boolean);
}

export function htmlHasText(html) {
    return Boolean(stripHtml(html));
}

export const ALLOWED_UPLOAD_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
];

export const ALLOWED_UPLOAD_EXT = [".pdf", ".png", ".jpg", ".jpeg", ".svg", ".docx", ".doc"];
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export function guessMimetype(name, type) {
    if (type === "image/jpg") {
        return "image/jpeg";
    }
    if (type) {
        return type;
    }
    const lower = (name || "").toLowerCase();
    if (lower.endsWith(".pdf")) {
        return "application/pdf";
    }
    if (lower.endsWith(".png")) {
        return "image/png";
    }
    if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
        return "image/jpeg";
    }
    if (lower.endsWith(".svg")) {
        return "image/svg+xml";
    }
    if (lower.endsWith(".docx")) {
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    }
    if (lower.endsWith(".doc")) {
        return "application/msword";
    }
    return "";
}

export function validateUploadFile(file) {
    const mimetype = guessMimetype(file.name, file.type);
    if (file.size > MAX_UPLOAD_BYTES) {
        return `${file.name} is larger than 10MB.`;
    }
    if (!mimetype || !ALLOWED_UPLOAD_TYPES.includes(mimetype)) {
        return `${file.name} is not an allowed type. Use PDF, PNG, JPG, SVG, or DOCX.`;
    }
    return "";
}

export function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            resolve(result.includes(",") ? result.split(",")[1] : result);
        };
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

export function formatFileSize(bytes) {
    if (!bytes) {
        return "0 B";
    }
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
        return `${Math.round(bytes / 1024)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function fileIcon(mimetype) {
    if ((mimetype || "").includes("pdf")) {
        return "fa-file-pdf-o";
    }
    if ((mimetype || "").startsWith("image/")) {
        return "fa-file-image-o";
    }
    if ((mimetype || "").includes("word")) {
        return "fa-file-word-o";
    }
    return "fa-file-o";
}
