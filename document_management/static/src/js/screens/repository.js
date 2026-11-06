/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, compactFilters, display, downloadPayload, extractError, formatBytes, formatLabel } from "../dm_utils";

const PREVIEW_ITEMS = [
    { id: "city", name: "City_Water_Agreement_2023.pdf", format: "pdf", category: "Municipal" },
    { id: "q3", name: "Q3_Municipal_Compliance_Report_Draft.docx", format: "docx", category: "Municipal" },
    { id: "vendor", name: "Vendor_Pricing_Matrix_24.xlsx", format: "xlsx", category: "Municipal" },
    { id: "env", name: "Environmental_Impact_Study_Phase1.pdf", format: "pdf", category: "Municipal" },
];

const PREVIEW_DETAILS = {
    city: {
        id: "city",
        name: "City_Water_Agreement_2023.pdf",
        format: "pdf",
        current_version: "v2.1",
        size_label: "1.2 MB",
        state: "approved",
        owner: "Jane Doe",
        department_label: "Compliance",
        create_date: "Jan 08, 2023",
        write_date: "Mar 02, 2024",
        classification: "Confidential",
        tags: ["Municipal", "Legal"],
        comments: [{ id: "c1", user: "Jane Doe", body: "Filed." }],
        versions: [{ id: "v21", name: "v2.1", is_current: true, author: "Jane Doe" }],
    },
    q3: {
        id: "q3",
        name: "Q3_Municipal_Compliance_Report_Draft.docx",
        format: "docx",
        current_version: "v4.0",
        size_label: "845 KB",
        state: "in_review",
        owner: "Jane Doe",
        department_label: "Compliance",
        create_date: "Oct 15, 2023",
        write_date: "Today, 09:41 AM",
        classification: "Confidential",
        tags: ["Q3", "Audit", "Municipal"],
        comments: [
            { id: "c1", user: "Jane Doe", body: "Need legal pass." },
            { id: "c2", user: "Mike Ross", body: "Section 4 updated." },
            { id: "c3", user: "Sarah Jenkins", body: "Ready for review." },
        ],
        versions: [{ id: "v40", name: "v4.0", is_current: true, author: "Jane Doe" }],
    },
    vendor: {
        id: "vendor",
        name: "Vendor_Pricing_Matrix_24.xlsx",
        format: "xlsx",
        current_version: "v1.4",
        size_label: "220 KB",
        state: "approved",
        owner: "Jane Doe",
        department_label: "Compliance",
        create_date: "Feb 11, 2024",
        write_date: "Apr 18, 2024",
        classification: "Internal",
        tags: ["Municipal", "Vendors"],
        comments: [],
        versions: [{ id: "v14", name: "v1.4", is_current: true, author: "Jane Doe" }],
    },
    env: {
        id: "env",
        name: "Environmental_Impact_Study_Phase1.pdf",
        format: "pdf",
        current_version: "v1.0",
        size_label: "3.8 MB",
        state: "approved",
        owner: "Jane Doe",
        department_label: "Compliance",
        create_date: "May 03, 2023",
        write_date: "May 03, 2023",
        classification: "Confidential",
        tags: ["Municipal"],
        comments: [],
        versions: [{ id: "v10", name: "v1.0", is_current: true, author: "Jane Doe" }],
    },
};

export class RepositoryScreen extends Component {
    static template = "document_management.Repository";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            items: [],
            categories: [],
            types: [],
            folders: [],
            total: 0,
            view: "all",
            filters: { search: "", department: "", status: "", category_id: "municipal", type_id: "", folder_id: "" },
            selected: {},
            selectedId: "q3",
            detail: PREVIEW_DETAILS.q3,
            panelTab: "details",
            comment: "",
            confirm: null,
            showFilters: false,
            counts: {},
            contractsOpen: true,
            listMode: "list",
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const rawFilters = compactFilters({
                ...this.state.filters,
                search: this.state.filters.search || this.props.shellSearch,
            });
            if (rawFilters.category_id && Number.isNaN(Number(rawFilters.category_id))) {
                delete rawFilters.category_id;
            }
            const filters = rawFilters;
            const data = await this.orm.call("document.management.ui.api", "get_repository_data", [
                this.state.view,
                filters,
                filters.search || false,
            ]);
            this.state.items = data.items || [];
            this.state.categories = data.categories || [];
            this.state.types = data.types || [];
            this.state.folders = data.folders || [];
            this.state.total = data.total || 0;
            this.state.counts[this.state.view] = this.state.total;
            if (this.usePreview) {
                this.state.selectedId = this.state.selectedId && PREVIEW_DETAILS[this.state.selectedId]
                    ? this.state.selectedId
                    : "q3";
                this.state.detail = PREVIEW_DETAILS[this.state.selectedId];
            } else {
                const first = this.state.items[0];
                if (typeof this.state.selectedId !== "number" && first) {
                    this.state.selectedId = first.id;
                }
                if (this.state.selectedId) {
                    await this.loadDetail(this.state.selectedId);
                }
            }
        } catch (err) {
            this.state.error = extractError(err);
            this.state.items = [];
            this.state.total = 0;
            this.state.detail = PREVIEW_DETAILS.q3;
            this.state.selectedId = "q3";
        } finally {
            this.state.loading = false;
        }
    }

    get usePreview() {
        return !(this.state.items || []).length;
    }

    get rows() {
        return this.usePreview ? PREVIEW_ITEMS : this.state.items;
    }

    get selectedDoc() {
        if (this.usePreview) {
            return PREVIEW_DETAILS[this.state.selectedId] || PREVIEW_DETAILS.q3;
        }
        return this.state.detail || {
            name: "",
            tags: [],
            comments: [],
            versions: [],
        };
    }

    get isEmpty() {
        return !this.rows.length;
    }

    get hasSelection() {
        return this.selectedIds().length > 0;
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

    toggleFilters() {
        this.state.showFilters = !this.state.showFilters;
    }

    viewCount(view) {
        if (this.usePreview) {
            if (view === "all") {
                return "12k";
            }
            if (view === "my") {
                return "432";
            }
            return "";
        }
        const value = this.state.view === view ? this.state.total : this.state.counts[view];
        if (value === undefined || value === null) {
            return "";
        }
        return Number(value || 0).toLocaleString();
    }

    get viewingLabel() {
        if (this.usePreview) {
            return "Viewing 24 of 142 items in Municipal";
        }
        const shown = (this.state.items || []).length;
        const total = this.state.total || 0;
        const cat = this.categoryName;
        const base = `Viewing ${shown} of ${total} items`;
        return cat ? `${base} in ${cat}` : base;
    }

    get categoryName() {
        const id = this.state.filters.category_id;
        if (!id) {
            return "";
        }
        if (id === "municipal") {
            return "Municipal";
        }
        const row = (this.state.categories || []).find((item) => String(item.id) === String(id));
        return row ? row.name : "";
    }

    get commentCount() {
        const comments = (this.selectedDoc && this.selectedDoc.comments) || [];
        return comments.length;
    }

    get detailTags() {
        return ((this.selectedDoc && this.selectedDoc.tags) || []);
    }

    fileIcon(doc) {
        const fmt = String((doc && doc.format) || "").toLowerCase();
        if (fmt === "pdf") {
            return "fa fa-file-pdf-o dm-file-pdf";
        }
        if (fmt === "doc" || fmt === "docx") {
            return "fa fa-file-word-o dm-file-doc";
        }
        if (fmt === "xls" || fmt === "xlsx") {
            return "fa fa-file-excel-o dm-file-xls";
        }
        return "fa fa-file-o dm-file-generic";
    }

    fileMeta(doc) {
        if (!doc) {
            return "";
        }
        const version = display(doc.current_version || "", "");
        const size = doc.size_label || formatBytes(doc.file_size || 0);
        return [version, size].filter(Boolean).join(" • ");
    }

    ownerInitials(name) {
        const text = String(name || "U").trim();
        const parts = text.split(/\s+/);
        if (parts.length > 1) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return text.slice(0, 1).toUpperCase();
    }

    isRowOn(doc) {
        return String(this.state.selectedId) === String(doc.id);
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

    onFilterChange() {
        if (this.usePreview) {
            return;
        }
        this.refresh();
    }

    stopClick(ev) {
        ev.stopPropagation();
    }

    setView(ev) {
        this.state.view = ev.currentTarget.dataset.view;
        if (this.usePreview) {
            return;
        }
        this.refresh();
    }

    setCategory(ev) {
        this.state.filters.category_id = ev.currentTarget.dataset.id || "";
        if (this.usePreview) {
            return;
        }
        this.refresh();
    }

    toggleContracts(ev) {
        ev.stopPropagation();
        this.state.contractsOpen = !this.state.contractsOpen;
    }

    setListMode(ev) {
        this.state.listMode = ev.currentTarget.dataset.mode;
    }

    selectedIds() {
        return Object.entries(this.state.selected).filter(([, on]) => on).map(([id]) => Number(id));
    }

    rememberDocument(id) {
        if (this.usePreview) {
            return;
        }
        const documentId = Number(id) || false;
        if (this.props.navigate) {
            this.props.navigate("repository", { documentId });
        }
    }

    toggleSelect(ev) {
        const id = ev.currentTarget.dataset.id;
        this.state.selected[id] = ev.currentTarget.checked;
        if (ev.currentTarget.checked) {
            this.selectById(id);
        }
    }

    selectRow(ev) {
        this.selectById(ev.currentTarget.dataset.id);
    }

    async selectById(id) {
        this.state.selectedId = id;
        this.rememberDocument(id);
        await this.loadDetail(id);
    }

    async loadDetail(id) {
        if (this.usePreview || PREVIEW_DETAILS[id]) {
            this.state.detail = PREVIEW_DETAILS[id] || PREVIEW_DETAILS.q3;
            return;
        }
        try {
            this.state.detail = await this.orm.call("document.management.ui.api", "get_document", [Number(id)]);
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    setPanelTab(ev) {
        this.state.panelTab = ev.currentTarget.dataset.tab;
    }

    openSelectedDetails() {
        if (this.usePreview || !this.state.selectedId || !this.props.navigate) {
            return;
        }
        this.props.navigate("details", { documentId: Number(this.state.selectedId) });
    }

    async downloadSelected() {
        if (this.usePreview || !this.state.selectedId) {
            return;
        }
        try {
            const payload = await this.orm.call("document.management.ui.api", "download_document", [
                Number(this.state.selectedId),
            ]);
            downloadPayload(payload);
        } catch (err) {
            this.state.error = extractError(err);
        }
    }

    askArchiveBulk() {
        this.state.confirm = { ids: this.selectedIds() };
    }

    cancelConfirm() {
        this.state.confirm = null;
    }

    async confirmArchive() {
        for (const id of this.state.confirm.ids || []) {
            await this.orm.call("document.management.ui.api", "archive_document", [id]);
        }
        this.state.confirm = null;
        await this.refresh();
    }

    shareSelected() {
        if (this.usePreview || !this.state.selectedId || !this.props.navigate) {
            return;
        }
        this.props.navigate("access", { documentId: Number(this.state.selectedId) });
    }

    async bulkFavorite() {
        for (const id of this.selectedIds()) {
            await this.orm.call("document.management.ui.api", "toggle_favorite", [id]);
        }
        await this.refresh();
    }

    goUpload() {
        if (this.props.navigate) {
            this.props.navigate("upload");
        }
    }

    async addComment() {
        if (this.usePreview || !this.state.selectedId) {
            return;
        }
        await this.orm.call("document.management.ui.api", "add_comment", [Number(this.state.selectedId), this.state.comment]);
        this.state.comment = "";
        await this.loadDetail(this.state.selectedId);
    }
}
