/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, display, downloadPayload, extractError, formatBytes, formatLabel, readFileAsPayload } from "../dm_utils";

const PREVIEW_DOC = {
    preview: true,
    name: "Fire Safety Policy",
    code: "POL-FS-2023-004",
    format: "pdf",
    format_label: "PDF/A",
    current_version: "v3.2",
    state: "approved",
    department_label: "Facilities",
    write_date: "Today, 09:41 AM",
    file_size: 4404019,
    size_label: "4.2 MB",
    expiry_date: "Dec 31, 2024",
    access_level: "restricted",
    access_badge: "Restricted - L2",
    author: "Sarah Jenkins",
    page_count: 42,
    versions: [
        {
            id: "v32",
            name: "v3.2",
            is_current: true,
            create_date: "Today, 09:41 AM",
            note: "Updated emergency assembly points for Building B.",
            author: "Sarah Jenkins",
        },
        {
            id: "v31",
            name: "v3.1",
            is_current: false,
            create_date: "Oct 12, 2023",
            note: "Annual review and minor formatting changes.",
            author: "Mike Ross",
        },
        {
            id: "v30",
            name: "v3.0",
            is_current: false,
            create_date: "Jan 05, 2022",
            note: "Major revision integrating new local safety regulations.",
            author: "Sarah Jenkins",
        },
    ],
};

export class DetailsScreen extends Component {
    static template = "document_management.Details";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            document: null,
            tab: "versions",
            note: "",
            restoreId: false,
        });
        onWillStart(() => this.refresh());
        onWillUpdateProps((next) => {
            if (next.documentId !== this.props.documentId) {
                return this.refresh(next.documentId);
            }
        });
    }

    async refresh(documentId) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("document.management.ui.api", "get_document", [
                documentId || this.props.documentId || false,
            ]);
            this.state.document = data || null;
        } catch (err) {
            this.state.error = extractError(err);
            this.state.document = null;
        } finally {
            this.state.loading = false;
        }
    }

    get usePreview() {
        return !this.state.document;
    }

    get doc() {
        return this.state.document || PREVIEW_DOC;
    }

    get isEmpty() {
        return this.usePreview;
    }

    display(value) {
        return display(value);
    }

    label(value) {
        const raw = formatLabel(value);
        if (!raw || raw === "—") {
            return raw;
        }
        return raw.replace(/\b\w/g, (char) => char.toUpperCase());
    }

    sizeLabel(value) {
        const doc = this.doc;
        if (doc && doc.size_label) {
            return doc.size_label;
        }
        return formatBytes(value);
    }

    fileFormat(doc) {
        if (doc && doc.format_label) {
            return doc.format_label;
        }
        const fmt = display(doc && doc.format);
        return fmt === "—" ? fmt : String(fmt).toUpperCase();
    }

    accessBadge(doc) {
        if (doc && doc.access_badge) {
            return doc.access_badge;
        }
        return this.label(doc && doc.access_level);
    }

    authorInitials(name) {
        const text = String(name || "U").trim();
        const parts = text.split(/\s+/);
        if (parts.length > 1) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return text.slice(0, 1).toUpperCase();
    }

    get versionRows() {
        const versions = (this.doc && this.doc.versions) || [];
        if (this.state.tab === "overview") {
            return versions.slice(0, 3);
        }
        return versions;
    }

    get pageCaption() {
        const pages = (this.doc && this.doc.page_count) || 1;
        return `Page 1 of ${pages}`;
    }

    fileIcon(doc) {
        const fmt = String((doc && doc.format) || "").toLowerCase();
        if (fmt === "pdf" || fmt === "pdf/a") {
            return "fa fa-file-pdf-o";
        }
        if (fmt === "doc" || fmt === "docx") {
            return "fa fa-file-word-o";
        }
        if (fmt === "xls" || fmt === "xlsx") {
            return "fa fa-file-excel-o";
        }
        return "fa fa-file-o";
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }
        if (/[A-Za-z]/.test(String(value))) {
            return String(value);
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        if (String(value).indexOf("Today") === 0 || /[A-Za-z]/.test(String(value))) {
            return String(value);
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        const now = new Date();
        const time = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
        if (date.toDateString() === now.toDateString()) {
            return `Today, ${time}`;
        }
        return `${this.formatDate(value)}, ${time}`;
    }

    setTab(ev) {
        this.state.tab = ev.currentTarget.dataset.tab;
    }

    async download() {
        if (this.usePreview || !this.state.document) {
            return;
        }
        const payload = await this.orm.call("document.management.ui.api", "download_document", [
            this.state.document.id,
        ]);
        downloadPayload(payload);
    }

    share() {
        if (this.usePreview || !this.state.document || !this.props.navigate) {
            return;
        }
        this.props.navigate("access", { documentId: this.state.document.id });
    }

    async onNewVersion(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file || this.usePreview || !this.state.document) {
            return;
        }
        try {
            const payload = await readFileAsPayload(file);
            await this.orm.call("document.management.ui.api", "upload_new_version", [
                this.state.document.id,
                payload,
                this.state.note,
            ]);
            await this.refresh();
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    askRestore(ev) {
        if (this.usePreview) {
            return;
        }
        this.state.restoreId = Number(ev.currentTarget.dataset.id);
    }

    cancelRestore() {
        this.state.restoreId = false;
    }

    async restoreVersion() {
        await this.orm.call("document.management.ui.api", "restore_version", [
            this.state.document.id,
            this.state.restoreId,
        ]);
        this.state.restoreId = false;
        await this.refresh();
    }
}
