/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, compactFilters, downloadCsv, extractError } from "../dm_utils";

const PREVIEW_QUERY = "What are the latest compliance requirements for water quality testing";

const PREVIEW_SOURCES = [
    {
        id: "preview-epa",
        name: "EPA Directive 2023-A_Final.pdf",
        type: "Policy",
        date: "Oct 12, 2023",
        department: "Compliance",
        relevance: 98,
        icon: "fa fa-file-pdf-o",
        kind: "pdf",
    },
    {
        id: "preview-manual",
        name: "Methodology Manual V4.docx",
        type: "Manual",
        date: "Sep 28, 2023",
        department: "Engineering",
        relevance: 94,
        icon: "fa fa-file-word-o",
        kind: "doc",
    },
    {
        id: "preview-sop",
        name: "Compliance SOP 9.2.pdf",
        type: "SOP",
        date: "Aug 05, 2023",
        department: "Compliance",
        relevance: 87,
        icon: "fa fa-file-pdf-o",
        kind: "pdf",
    },
    {
        id: "preview-q3",
        name: "Q3 Quality Report Draft.txt",
        type: "Report",
        date: "Oct 01, 2023",
        department: "Engineering",
        relevance: 72,
        icon: "fa fa-file-text-o",
        kind: "txt",
    },
];

const PREVIEW_CITATIONS = [
    { id: 1, label: "EPA Directive 2023-A" },
    { id: 2, label: "Methodology Manual V4" },
    { id: 3, label: "Compliance SOP 9.2" },
];

export class SearchScreen extends Component {
    static template = "document_management.Search";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            hits: [],
            ai: null,
            query: this.props.shellSearch || PREVIEW_QUERY,
            filters: { department: "", property: "", asset: "", date_from: "", date_to: "" },
            csv: null,
            tab: "ai",
            property: "all",
            datePreset: "12",
            departments: {
                engineering: true,
                compliance: true,
                procurement: false,
            },
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const query = this.state.tab === "all" ? "" : (this.state.query || this.props.shellSearch || "");
            const filters = compactFilters(this.state.filters);
            const data = await this.orm.call("document.management.ui.api", "keyword_search", [query, filters]);
            const ai = await this.orm.call("document.management.ui.api", "ai_search", [query, filters]);
            this.state.hits = data.hits || [];
            this.state.ai = ai || { configured: false, available: false, message: "AI Search is not configured" };
        } catch (err) {
            this.state.error = extractError(err);
            this.state.hits = [];
            this.state.ai = null;
        } finally {
            this.state.loading = false;
        }
    }

    get usePreview() {
        return !(this.state.ai && this.state.ai.configured);
    }

    get isAiTab() {
        return this.state.tab === "ai";
    }

    get isEmpty() {
        if (this.isAiTab && this.usePreview) {
            return false;
        }
        return !(this.state.hits || []).length;
    }

    get displayHits() {
        return this.state.hits || [];
    }

    get sourceRows() {
        if (this.isAiTab && this.usePreview) {
            return PREVIEW_SOURCES;
        }
        return this.displayHits;
    }

    get sourceCount() {
        if (this.isAiTab && this.usePreview) {
            return 12;
        }
        return this.sourceRows.length;
    }

    get citations() {
        if (this.state.ai && this.state.ai.configured && (this.state.ai.citations || []).length) {
            return this.state.ai.citations;
        }
        return PREVIEW_CITATIONS;
    }

    get suggestions() {
        return [
            "Show me recent equipment failures",
            "Summarize Q3 procurement guidelines",
        ];
    }

    get properties() {
        return [{ id: "all", label: "All Properties" }];
    }

    get datePresets() {
        return [
            { id: "12", label: "Last 12 Months" },
            { id: "6", label: "Last 6 Months" },
            { id: "30", label: "Last 30 Days" },
            { id: "all", label: "All dates" },
        ];
    }

    get departmentList() {
        return [
            { id: "engineering", label: "Engineering" },
            { id: "compliance", label: "Compliance" },
            { id: "procurement", label: "Procurement" },
        ];
    }

    get sourceTitle() {
        return `Source Documents (${this.sourceCount})`;
    }

    setTab(ev) {
        this.state.tab = ev.currentTarget.dataset.tab;
        this.refresh();
    }

    applySuggestion(ev) {
        this.state.query = ev.currentTarget.dataset.query;
        this.refresh();
    }

    toggleDept(ev) {
        const key = ev.currentTarget.dataset.dept;
        this.state.departments[key] = ev.currentTarget.checked;
    }

    deptLabel(row) {
        return row.department || row.department_label || "—";
    }

    cell(value) {
        return value || "—";
    }

    isDeptOn(dept) {
        return Boolean(this.state.departments[dept]);
    }

    clearAll() {
        this.state.departments.engineering = false;
        this.state.departments.compliance = false;
        this.state.departments.procurement = false;
        this.state.property = "all";
        this.state.datePreset = "12";
        this.state.filters.department = "";
        this.state.filters.property = "";
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
    }

    onSearch(ev) {
        if (ev && ev.key && ev.key !== "Enter") {
            return;
        }
        this.refresh();
    }

    relevanceClass(row) {
        const value = Number(row.relevance) || 0;
        if (value >= 80) {
            return "dm-search-rel is-high";
        }
        return "dm-search-rel";
    }

    relevanceLabel(row) {
        if (row.relevance === undefined || row.relevance === null || row.relevance === false) {
            return "";
        }
        return `${row.relevance}%`;
    }

    fileClass(row) {
        if (row.kind === "pdf") {
            return "dm-search-file is-pdf";
        }
        if (row.kind === "doc") {
            return "dm-search-file is-doc";
        }
        return "dm-search-file";
    }

    fileIcon(row) {
        return row.icon || "fa fa-file-text-o";
    }

    rowKey(row) {
        return row.id || row.name;
    }

    openDetails(ev) {
        const id = ev.currentTarget.dataset.id;
        if (!id || String(id).startsWith("preview")) {
            return;
        }
        if (this.props.navigate) {
            this.props.navigate("details", { documentId: Number(id) });
        }
    }

    async exportCsv() {
        if (this.isAiTab && this.usePreview) {
            const lines = ["relevance,name,type,date,department"];
            PREVIEW_SOURCES.forEach((row) => {
                lines.push([row.relevance, row.name, row.type, row.date, row.department].join(","));
            });
            downloadCsv({ filename: "document-search.csv", csv: `${lines.join("\n")}\n` });
            return;
        }
        const data = await this.orm.call("document.management.ui.api", "export_search_csv", [
            this.state.query || this.props.shellSearch || "",
            compactFilters(this.state.filters),
        ]);
        this.state.csv = data;
        downloadCsv(data);
    }
}
