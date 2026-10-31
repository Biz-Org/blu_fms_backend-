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

export const SHELL_PROPS = {
    session: { type: Object },
    navigate: { type: Function, optional: true },
    shellSearch: { type: String, optional: true },
    documentId: { type: [Number, Boolean, String], optional: true },
    refreshSession: { type: Function, optional: true },
};

export function downloadPayload(payload) {
    if (!payload || !payload.datas) {
        return;
    }
    const binary = atob(payload.datas);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: payload.mimetype || "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = payload.name || "document";
    link.click();
    URL.revokeObjectURL(url);
}

export function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    }
    if (bytes < 1024 * 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function formatLabel(value) {
    if (!value) {
        return "—";
    }
    return String(value).replace(/_/g, " ");
}

export function downloadCsv(payload) {
    if (!payload || !payload.csv) {
        return;
    }
    const blob = new Blob([payload.csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = payload.filename || "export.csv";
    link.click();
    URL.revokeObjectURL(url);
}

export function readFileAsPayload(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            const datas = result.includes(",") ? result.split(",")[1] : result;
            resolve({
                filename: file.name,
                mimetype: file.type,
                datas,
                size: file.size,
            });
        };
        reader.onerror = () => reject(reader.error || new Error("Unable to read file"));
        reader.readAsDataURL(file);
    });
}
