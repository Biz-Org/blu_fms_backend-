/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SCREENS = [
    { id: "dashboard", label: "Dashboard", title: "Procurement Dashboard" },
    { id: "requisitions", label: "Purchase Requisitions", title: "Purchase Requisitions" },
    { id: "rfqs", label: "RFQs & Quotations", title: "RFQs & Quotations" },
    { id: "comparison", label: "Quotation Comparison", title: "Quotation Comparison & Supplier Selection" },
    { id: "approval_matrix", label: "Approval Matrix", title: "Approval Matrix" },
    { id: "purchase_orders", label: "Purchase Orders", title: "Purchase Orders" },
    { id: "goods_receipts", label: "Goods Receipts", title: "Goods Receipts" },
    { id: "invoice_matching", label: "Invoice Matching", title: "Invoice Matching" },
    { id: "suppliers", label: "Supplier Management", title: "Supplier Management" },
    { id: "reports", label: "Procurement Reports", title: "Procurement Reports" },
    { id: "report_builder", label: "Report Builder & Export", title: "Report Builder & Export" },
    { id: "audit", label: "Procurement Activity / Audit", title: "Procurement Activity / Audit" },
];

const STATUS = {
    draft: "Draft",
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
    returned: "Returned",
    cancelled: "Cancelled",
    converted: "Converted",
    issued: "Issued",
    supplier_responded: "Supplier Responded",
    partially_responded: "Partially Responded",
    under_evaluation: "Under Evaluation",
    closed: "Closed",
    review: "Under Review",
    active: "Active",
    inactive: "Inactive",
    acknowledged: "Acknowledged",
    partial: "Partial",
    overdue: "Overdue",
    expected: "Expected",
    pending_receipt: "Pending Receipt",
    receiving: "Receiving",
    pending_inspection: "Pending Inspection",
    inspection: "Inspection",
    completed: "Completed",
    matched: "Matched",
    mismatch: "Mismatch",
    under_review: "Under Review",
    preferred: "Preferred",
    suspended: "Suspended",
    none: "None",
    effective: "Effective",
    invited: "Invited",
    responded: "Responded",
    pass: "Pass",
    hold_qa: "Hold for QA",
    success: "Success",
    denied: "Denied",
    created: "Created",
    modified: "Modified",
    deleted: "Deleted",
    synced: "Synced",
    ready: "Ready",
    generating: "Generating",
    exported: "Exported",
    failed: "Failed",
    sequential: "Sequential",
    parallel: "Parallel",
    shortlisted: "Shortlisted",
    recommended: "Recommended",
    selected: "Selected",
};

const EMPTY = {
    dashboard: "No procurement activity yet",
    requisitions: "No requisitions yet",
    rfqs: "No RFQs yet",
    comparison: "No quotations to compare yet",
    approval_matrix: "No approval matrices yet",
    purchase_orders: "No purchase orders yet",
    goods_receipts: "No goods receipts yet",
    invoice_matching: "No invoice matches yet",
    suppliers: "No supplier records yet",
    reports: "No reports yet",
    report_builder: "No saved report configuration yet",
    audit: "No audit activity yet",
};

const PAGE = 20;

const RFQ_STATUSES = [
    { key: "draft", label: "Draft" },
    { key: "issued", label: "Issued" },
    { key: "supplier_responded", label: "Supplier Responded" },
    { key: "under_evaluation", label: "Under Evaluation" },
    { key: "closed", label: "Closed" },
];

export class ProcurementManagementApp extends Component {
    static template = "procurement_management.App";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        const requested =
            this.props.action?.context?.pm_screen ||
            this.props.action?.params?.screen ||
            "dashboard";
        this.screens = SCREENS;
        this.rfqStatuses = RFQ_STATUSES;
        this.state = useState({
            screen: SCREENS.some((item) => item.id === requested) ? requested : "dashboard",
            loading: true,
            error: "",
            notice: "",
            busy: false,
            query: "",
            filter: "",
            offset: 0,
            rows: [],
            total: 0,
            counts: {},
            data: {},
            detail: null,
            drawer: false,
            drawerTab: "details",
            form: {},
            nav: { approval_matrix: false, audit: false, reports_run: false },
            focusId: false,
            partnerHits: [],
        });
        onWillStart(async () => {
            await this.loadNavigation();
            await this.reload();
        });
        onMounted(() => document.body.classList.add("pm-suite"));
        onWillUnmount(() => document.body.classList.remove("pm-suite"));
    }

    userInitial() {
        const menu = document.querySelector(".o_user_menu");
        const name = (menu && menu.textContent) || "";
        const letter = String(name).replace(/\s+/g, " ").trim().charAt(0);
        return letter ? letter.toUpperCase() : "A";
    }

    openOdooHome() {
        window.location.assign("/odoo");
    }

    get showFlow() {
        return [
            "requisitions",
            "rfqs",
            "comparison",
            "purchase_orders",
            "goods_receipts",
            "invoice_matching",
        ].includes(this.state.screen);
    }

    get flowSteps() {
        return [
            { screen: "requisitions", label: "PR" },
            { screen: "requisitions", label: "Approval" },
            { screen: "rfqs", label: "RFQ" },
            { screen: "rfqs", label: "Quotation" },
            { screen: "comparison", label: "Comparison" },
            { screen: "purchase_orders", label: "PO" },
            { screen: "goods_receipts", label: "GRN" },
            { screen: "invoice_matching", label: "Invoice" },
        ];
    }

    get flowIndex() {
        if (this.state.screen === "requisitions" && this.state.detail && this.state.detail.state === "pending") {
            return 1;
        }
        if (this.state.screen === "rfqs" && this.state.drawerTab === "quotations") {
            return 3;
        }
        return {
            requisitions: 0,
            rfqs: 2,
            comparison: 4,
            purchase_orders: 5,
            goods_receipts: 6,
            invoice_matching: 7,
        }[this.state.screen] || 0;
    }

    openFlow(ev) {
        const screen = ev.currentTarget.dataset.screen;
        if (screen && screen !== this.state.screen) {
            this.openScreen(screen);
        }
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
    }

    get emptyText() {
        return EMPTY[this.state.screen] || "Nothing to show yet";
    }

    get pageFrom() {
        return this.state.total ? this.state.offset + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.offset + this.state.rows.length, this.state.total);
    }

    get pageStep() {
        return this.state.screen === "purchase_orders" ? 6 : PAGE;
    }

    get pageNumber() {
        return Math.floor(this.state.offset / this.pageStep) + 1;
    }

    get pageButtons() {
        const count = Math.max(1, Math.ceil((this.state.total || 0) / this.pageStep));
        const current = this.pageNumber;
        const start = Math.max(1, Math.min(current - 1, Math.max(count - 2, 1)));
        const buttons = [];
        for (let number = start; number <= Math.min(count, start + 2); number += 1) {
            buttons.push(number);
        }
        return buttons;
    }

    countFor(key) {
        return (this.state.counts && this.state.counts[key]) || 0;
    }

    get matrixRows() {
        const query = String(this.state.query || "").trim().toLowerCase();
        return (this.state.rows || []).filter((row) => {
            if (!query) {
                return true;
            }
            return [row.name, row.department, row.property_location, row.category]
                .join(" ")
                .toLowerCase()
                .includes(query);
        });
    }

    band(row) {
        const min = this.money(row.min_value);
        if (!Number(row.max_value)) {
            return Number(row.min_value) ? "> " + min : min;
        }
        return min + " – " + this.money(row.max_value);
    }

    matrixStatus(value) {
        return value === "review" ? "Review" : this.label(value);
    }

    orderStatus(value) {
        if (value === "partial") {
            return "Partial Rec.";
        }
        if (value === "pending") {
            return "Pending App.";
        }
        return this.label(value);
    }

    focusOrderSearch() {
        const input = document.querySelector(".pm-order-search");
        if (input) {
            input.focus();
        }
    }

    focusReceiptSearch() {
        const input = document.querySelector(".pm-top-search input");
        if (input) {
            input.focus();
        }
    }

    focusInvoiceSearch() {
        const input = document.querySelector(".pm-top-search input");
        if (input) {
            input.focus();
        }
    }

    invoiceStatus(detail) {
        if (detail && detail.state === "mismatch" && Number(detail.variance)) {
            return "Price Mismatch";
        }
        return this.label(detail && detail.state);
    }

    lineMatch(line, kind) {
        const value = kind === "amount" ? line.variance_amount : line.variance_qty;
        return Number(value) ? "no" : "yes";
    }

    get supplierTotal() {
        return this.countFor("active") + this.countFor("preferred") + this.countFor("suspended");
    }

    get activeContracts() {
        return ((this.state.detail && this.state.detail.contracts) || []).filter((row) => row.state === "active");
    }

    supplierScore(value) {
        return Math.round(Number(value) || 0) + "/100";
    }

    supplierMoney(value, currency) {
        const amount = Number(value || 0);
        const code = String(currency || "").trim();
        if (/^[A-Z]{3}$/.test(code)) {
            try {
                return new Intl.NumberFormat(undefined, {
                    style: "currency",
                    currency: code,
                    maximumFractionDigits: 0,
                }).format(amount);
            } catch (error) {
                return this.money(value, currency);
            }
        }
        return this.money(value, currency);
    }

    contractExpiry(value) {
        const match = String(value || "").match(/^(\d{4})-(\d{2})/);
        if (!match) {
            return "";
        }
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return "exp: " + months[Number(match[2]) - 1] + " " + match[1];
    }

    supplierInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        const letters = parts.slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("");
        return letters || "S";
    }

    supplierPlace(detail) {
        if (!detail) {
            return "";
        }
        return [detail.city, detail.state_name].filter(Boolean).join(", ");
    }

    focusSupplierSearch() {
        const input = document.querySelector(".pm-top-search input");
        if (input) {
            input.focus();
        }
    }

    get receiptSubtitle() {
        const detail = this.state.detail || {};
        const lines = (this.state.form && this.state.form.lines) || detail.lines || [];
        const description = lines[0] && lines[0].description;
        if (detail.supplier && description && description !== detail.supplier) {
            return detail.supplier + " - " + description;
        }
        return detail.supplier || description || "";
    }

    orderCreate() {
        this.state.notice = "Purchase orders are created when a quotation is selected.";
    }

    seedMatrixPolicy() {
        const first = (this.state.form.levels || [])[0] || {};
        const hours = Number(first.escalation_hours || 0);
        const groupId = first.escalation_group_id || false;
        this.state.form.escalate = Boolean(groupId) || hours > 0;
        this.state.form.escalation_hours = hours || 48;
        this.state.form.escalation_group_id = groupId || false;
    }

    matrixLevelsForSave() {
        const hours = this.state.form.escalate ? Number(this.state.form.escalation_hours || 0) : 0;
        const groupId = this.state.form.escalate ? (this.state.form.escalation_group_id || false) : false;
        return (this.state.form.levels || []).map((level, index) => ({
            ...level,
            sequence: level.sequence || (index + 1) * 10,
            escalation_hours: hours,
            escalation_group_id: groupId || false,
            mode: this.state.form.mode || "sequential",
        }));
    }

    focusRfqSearch() {
        const input = document.querySelector(".pm-rfq-search");
        if (input) {
            input.focus();
        }
    }

    navAllowed(screenId) {
        if (screenId === "approval_matrix" || screenId === "audit") {
            return Boolean(this.state.nav[screenId]);
        }
        return true;
    }

    label(value) {
        return STATUS[value] || value || "";
    }

    money(value, currency) {
        const amount = Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return currency ? `${amount} ${currency}` : amount;
    }

    rpcMessage(error) {
        return (
            error?.data?.message ||
            error?.message ||
            "The server could not complete this action."
        );
    }

    async rpc(method, args = [], kwargs = {}) {
        return this.orm.call("procurement.management.ui.api", method, args, kwargs);
    }

    async loadNavigation() {
        try {
            this.state.nav = await this.rpc("get_navigation");
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        }
    }

    async onNavClick(ev) {
        const screen = ev.currentTarget.dataset.screen;
        if (!this.screens.some((item) => item.id === screen) || !this.navAllowed(screen)) {
            return;
        }
        await this.openScreen(screen);
    }

    async openScreen(screen, focusId = false) {
        this.state.screen = screen;
        this.state.focusId = focusId;
        this.state.drawer = false;
        this.state.detail = null;
        this.state.query = "";
        this.state.filter = "";
        this.state.offset = 0;
        this.state.notice = "";
        this.state.form = {};
        await this.reload();
        if (focusId) {
            await this.openRecord(focusId);
        }
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            await this.loadScreen(false);
        } catch (error) {
            this.state.error = this.rpcMessage(error);
            this.state.rows = [];
            this.state.data = {};
        } finally {
            this.state.loading = false;
        }
    }

    async refreshKeepingForm() {
        try {
            await this.loadScreen(true);
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        }
    }

    async loadScreen(keepForm) {
        const screen = this.state.screen;
        const kwargs = {
            search: this.state.query || false,
            state: this.state.filter || false,
            limit: PAGE,
            offset: this.state.offset,
        };
        const metaKw = {
            search: this.state.query || false,
            state: this.state.filter || false,
        };
        if (screen === "dashboard") {
            this.state.data = await this.rpc("get_dashboard");
            this.state.rows = this.state.data.recent_orders || [];
            return;
        }
        if (screen === "requisitions") {
            this.state.data = await this.rpc("get_requisition_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_requisitions", [], kwargs);
            return;
        }
        if (screen === "rfqs") {
            this.state.data = await this.rpc("get_rfq_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_rfqs", [], kwargs);
            return;
        }
        if (screen === "comparison") {
            const data = await this.rpc("get_comparison_screen", [this.state.focusId || false]);
            this.state.data = data;
            this.state.rows = data.rows || [];
            if (!keepForm) {
                this.state.form = {
                    commercial_weight: data.commercial_weight || 0,
                    technical_weight: data.technical_weight || 0,
                    justification: "",
                    focusId: data.recommended_quotation_id || false,
                    rows: (data.rows || []).map((row) => ({ ...row })),
                };
            }
            return;
        }
        if (screen === "approval_matrix") {
            this.state.data = await this.rpc("get_matrix_meta");
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_approval_matrices");
            return;
        }
        if (screen === "purchase_orders") {
            this.state.data = await this.rpc("get_purchase_order_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_purchase_orders", [], { ...kwargs, limit: 6 });
            return;
        }
        if (screen === "goods_receipts") {
            this.state.data = await this.rpc("get_receipt_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_goods_receipts", [], kwargs);
            return;
        }
        if (screen === "invoice_matching") {
            this.state.data = await this.rpc("get_invoice_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_invoice_matches", [], kwargs);
            return;
        }
        if (screen === "suppliers") {
            this.state.data = await this.rpc("get_supplier_meta", [], metaKw);
            this.state.counts = this.state.data.counts || {};
            this.state.total = this.state.data.total || 0;
            this.state.rows = await this.rpc("get_suppliers", [], kwargs);
            if (!keepForm && this.state.rows.length) {
                await this.openRecord(this.state.rows[0].id);
            }
            return;
        }
        if (screen === "reports") {
            this.state.data = await this.rpc("get_report_home");
            this.state.rows = this.state.data.recent || [];
            return;
        }
        if (screen === "report_builder") {
            this.state.data = await this.rpc("get_report_builder");
            if (!keepForm) {
                this.state.form = this.blankReport();
                this.state.detail = null;
            }
            return;
        }
        if (screen === "audit") {
            this.state.data = await this.rpc("get_audit_meta", [], {
                search: this.state.query || false,
            });
            this.state.rows = await this.rpc("get_audit", [], {
                search: this.state.query || false,
                limit: PAGE,
                offset: this.state.offset,
            });
            this.state.total = this.state.data.total || 0;
        }
    }

    async runAction(work) {
        this.state.busy = true;
        this.state.error = "";
        this.state.notice = "";
        try {
            await work();
        } catch (error) {
            this.state.error = this.rpcMessage(error);
            await this.refreshKeepingForm();
        } finally {
            this.state.busy = false;
        }
    }

    async search() {
        this.state.offset = 0;
        await this.reload();
    }

    async setFilter(ev) {
        this.state.filter = ev.target.value;
        this.state.offset = 0;
        await this.reload();
    }

    async setChip(ev) {
        this.state.filter = ev.currentTarget.dataset.state || "";
        this.state.offset = 0;
        await this.reload();
    }

    async onSearchKey(ev) {
        if (ev.key === "Enter") {
            await this.search();
        }
    }

    async goPage(page) {
        const next = (Number(page) - 1) * this.pageStep;
        if (next < 0 || (this.state.total && next >= this.state.total) || next === this.state.offset) {
            return;
        }
        this.state.offset = next;
        await this.reload();
    }

    async page(step) {
        const next = this.state.offset + step * this.pageStep;
        if (next < 0 || (this.state.total && next >= this.state.total)) {
            return;
        }
        this.state.offset = next;
        await this.reload();
    }

    async openRecord(idOrEvent) {
        const id = typeof idOrEvent === "number" ? idOrEvent : Number(idOrEvent.currentTarget?.dataset?.id);
        const loaders = {
            requisitions: ["get_requisition_detail", id],
            rfqs: ["get_rfq_detail", id],
            approval_matrix: ["get_matrix_detail", id],
            purchase_orders: ["get_purchase_order_detail", id],
            goods_receipts: ["get_receipt_detail", id],
            invoice_matching: ["get_invoice_detail", id],
            suppliers: ["get_supplier_detail", id],
        };
        const spec = loaders[this.state.screen];
        if (!spec || !id) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            this.state.detail = await this.rpc(spec[0], [id]);
            this.state.form = this.formFromDetail(this.state.detail);
            if (this.state.screen === "approval_matrix") {
                this.seedMatrixPolicy();
                await this.loadMatrixLookups();
            }
            if (this.state.screen === "goods_receipts" && this.state.detail.inspection_result) {
                this.state.form.inspection = this.state.detail.inspection_result;
            }
            this.state.drawer = true;
            this.state.drawerTab = "details";
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        } finally {
            this.state.busy = false;
        }
    }

    formFromDetail(detail) {
        return {
            ...detail,
            lines: (detail.lines || []).map((line) => ({ ...line })),
            levels: (detail.levels || []).map((level) => ({ ...level })),
            partner_ids: (detail.suppliers || []).map((row) => row.partner_id),
            quote_lines: [{ description: "", quantity: 1, unit_text: "", price_unit: 0 }],
            amount_tax: 0,
            freight_amount: 0,
            quantities: Object.fromEntries((detail.lines || []).map((line) => [line.id, line.received_qty])),
            inspection: "pass",
            comment: "",
            note: "",
            contact_name: "",
            contact_email: "",
            contact_phone: "",
            contact_function: "",
            supplier_invoice_number: "",
        };
    }

    blankRequisition() {
        return {
            title: "",
            description: "",
            justification: "",
            department: "",
            property_project: "",
            category: "",
            cost_center: "",
            required_date: "",
            lines: [],
            comment: "",
        };
    }

    reportTypeLabel(kind) {
        return {
            spend: "Spend Analysis",
            performance: "Supplier Performance Summary",
            requisitions: "Requisitions",
            rfq: "RFQs & Quotations",
            custom: "Custom",
        }[kind] || kind;
    }

    metricOn(key) {
        return String(this.state.form.metrics || "")
            .split(",")
            .map((item) => item.trim())
            .includes(key);
    }

    toggleMetric(ev) {
        const key = ev.currentTarget.dataset.metric;
        const current = String(this.state.form.metrics || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
        const next = ev.target.checked
            ? current.concat(key)
            : current.filter((item) => item !== key);
        this.state.form.metrics = [...new Set(next)].join(",");
    }

    blankReport() {
        return {
            name: "",
            report_type: "spend",
            date_from: "",
            date_to: "",
            department: "",
            partner_id: false,
            category: "",
            status: "",
            metrics: "amount,status,date",
            group_by: "",
            sort_by: "",
            schedule: "none",
            weekday: 0,
            month_day: 1,
            recipient_emails: "",
            preview: null,
        };
    }

    openCreate() {
        this.state.error = "";
        this.state.detail = null;
        this.state.drawer = true;
        this.state.drawerTab = "details";
        if (this.state.screen === "requisitions") {
            this.state.form = this.blankRequisition();
        } else if (this.state.screen === "rfqs") {
            this.state.form = {
                description: "",
                department: "",
                property_project: "",
                category: "",
                deadline: "",
                estimated_value: 0,
                commercial_weight: 40,
                technical_weight: 60,
                partner_ids: [],
                partner_term: "",
                quote_lines: [{ description: "", quantity: 1, unit_text: "", price_unit: 0 }],
                amount_tax: 0,
                freight_amount: 0,
            };
        } else if (this.state.screen === "approval_matrix") {
            this.state.form = {
                name: "",
                company_id: false,
                min_value: 0,
                max_value: 0,
                department: "",
                property_location: "",
                category: "",
                sequence: 10,
                mode: "sequential",
                levels: [{
                    sequence: 10,
                    approver_group_id: false,
                    required_signoff: true,
                    escalation_hours: 48,
                    escalation_group_id: false,
                }],
                escalate: true,
                escalation_hours: 48,
                escalation_group_id: false,
                group_term: "",
                companies: [],
                groups: [],
            };
            this.loadMatrixLookups();
        } else if (this.state.screen === "suppliers") {
            this.state.form = {
                partner_name: "",
                email: "",
                phone: "",
                vendor_code: "",
                category: "",
                score: 0,
                state: "active",
                contact_name: "",
                contact_email: "",
                contact_phone: "",
                contact_function: "",
                contract_name: "",
            };
        } else if (this.state.screen === "invoice_matching") {
            this.state.form = {
                order_id: false,
                supplier_invoice_number: "",
                invoice_amount: 0,
                invoice_date: "",
                lines: [],
            };
        }
    }

    closeDrawer() {
        if (this.state.busy) {
            return;
        }
        this.state.drawer = false;
    }

    setTab(ev) {
        this.state.drawerTab = ev.currentTarget.dataset.tab;
    }

    addLine() {
        this.state.form.lines.push({
            description: "",
            quantity: 1,
            unit_text: "",
            price_unit: 0,
            cost_center: "",
        });
    }

    removeLine(ev) {
        const index = Number(ev.currentTarget.dataset.index);
        this.state.form.lines.splice(index, 1);
    }

    async saveRequisition(submit) {
        await this.runAction(async () => {
            const detail = await this.rpc("save_requisition", [this.state.form]);
            if (submit) {
                this.state.detail = await this.rpc("requisition_command", [detail.id, "submit"]);
            } else {
                this.state.detail = detail;
            }
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = submit ? "Requisition submitted." : "Requisition saved.";
            await this.refreshKeepingForm();
        });
    }

    async requisitionAction(ev) {
        const command = ev.currentTarget.dataset.command;
        await this.runAction(async () => {
            this.state.detail = await this.rpc("requisition_command", [
                this.state.detail.id,
                command,
                this.state.form.comment || "",
                this.state.form.partner_id || false,
            ]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Requisition updated.";
            await this.refreshKeepingForm();
        });
    }

    async saveRfq() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_rfq", [this.state.form]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "RFQ saved.";
            await this.refreshKeepingForm();
        });
    }

    async rfqAction(ev) {
        const command = ev.currentTarget.dataset.command;
        await this.runAction(async () => {
            this.state.detail = await this.rpc("rfq_command", [this.state.detail.id, command]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "RFQ updated.";
            await this.refreshKeepingForm();
        });
    }

    async saveQuotation() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_quotation", [{
                rfq_id: this.state.detail.id,
                partner_id: this.state.form.quote_partner_id,
                amount_tax: this.state.form.amount_tax,
                freight_amount: this.state.form.freight_amount,
                lines: this.state.form.quote_lines,
            }]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Quotation recorded.";
            await this.refreshKeepingForm();
        });
    }

    async findPartners(ev) {
        const term = ev.target.value;
        this.state.form.partner_term = term;
        if (!term) {
            this.state.partnerHits = [];
            return;
        }
        try {
            this.state.partnerHits = await this.rpc("search_partners", [term]);
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        }
    }

    pickPartner(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        if (!this.state.form.partner_ids.includes(id)) {
            this.state.form.partner_ids.push(id);
        }
        this.state.form.partner_id = id;
        this.state.form.quote_partner_id = id;
        this.state.partnerHits = [];
    }

    async selectComparisonRfq(ev) {
        this.state.focusId = Number(ev.target.value) || false;
        await this.reload();
    }

    async comparisonSave() {
        await this.runAction(async () => {
            this.state.data = await this.rpc("comparison_save", [
                this.state.data.rfq_id,
                Number(this.state.form.commercial_weight),
                Number(this.state.form.technical_weight),
                this.state.form.rows,
            ]);
            this.state.rows = this.state.data.rows || [];
            this.state.form.rows = (this.state.data.rows || []).map((row) => ({ ...row }));
            this.state.form.commercial_weight = this.state.data.commercial_weight;
            this.state.form.technical_weight = this.state.data.technical_weight;
            this.state.notice = "Comparison saved.";
        });
    }

    async comparisonReject() {
        await this.runAction(async () => {
            this.state.data = await this.rpc("comparison_reject", [
                this.state.form.focusId,
                this.state.form.justification || "",
            ]);
            this.state.rows = this.state.data.rows || [];
            this.state.form.rows = (this.state.data.rows || []).map((row) => ({ ...row }));
            this.state.notice = this.state.data.selection_status === "pending"
                ? "Selection is waiting for approval."
                : "Quotation updated.";
        });
    }

    async comparisonSelect() {
        await this.runAction(async () => {
            this.state.data = await this.rpc("comparison_select", [
                this.state.form.focusId,
                this.state.form.justification || "",
            ]);
            this.state.rows = this.state.data.rows || [];
            this.state.form.rows = (this.state.data.rows || []).map((row) => ({ ...row }));
            if (this.state.data.purchase_order) {
                this.state.notice = "Purchase order " + this.state.data.purchase_order + " created.";
            } else if (this.state.data.selection_result === "pending") {
                this.state.notice = "Supplier selection is waiting for approval. The purchase order is created when it is approved.";
            } else {
                this.state.notice = "Supplier selection recorded.";
            }
        });
    }

    async loadMatrixLookups() {
        try {
            this.state.form.companies = await this.rpc("list_companies");
            this.state.form.groups = await this.rpc("list_groups", [], { search: false });
            if (!this.state.form.company_id && this.state.form.companies.length) {
                this.state.form.company_id = this.state.form.companies[0].id;
            }
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        }
    }

    addLevel() {
        this.state.form.levels.push({
            sequence: (this.state.form.levels.length + 1) * 10,
            approver_group_id: false,
            required_signoff: true,
            escalation_hours: 48,
            escalation_group_id: false,
        });
    }

    async saveMatrix(command) {
        await this.runAction(async () => {
            const payload = {
                ...this.state.form,
                levels: this.matrixLevelsForSave(),
                command: command || false,
            };
            this.state.detail = await this.rpc("save_matrix", [payload]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.seedMatrixPolicy();
            await this.loadMatrixLookups();
            this.state.notice = "Matrix saved.";
            await this.refreshKeepingForm();
        });
    }

    async purchaseAction(ev) {
        const command = ev.currentTarget.dataset.command;
        await this.runAction(async () => {
            this.state.detail = await this.rpc("purchase_order_command", [
                this.state.detail.id,
                command,
                this.state.form.comment || "",
            ]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Purchase order updated.";
            await this.refreshKeepingForm();
        });
    }

    async saveOrderLines() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_purchase_order_lines", [
                this.state.detail.id,
                this.state.form.lines,
            ]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Purchase order lines saved.";
            await this.refreshKeepingForm();
        });
    }

    async printOrder() {
        await this.runAction(async () => {
            const result = await this.rpc("print_purchase_order", [this.state.detail.id]);
            if (!result.ok) {
                this.state.error = result.error || "PDF export is unavailable.";
                return;
            }
            this.download(result);
        });
    }

    async receiveOrder() {
        const receipt = (this.state.detail.receipts || []).find((row) => row.state !== "completed");
        if (!receipt) {
            this.state.error = "There is no open receipt for this purchase order.";
            return;
        }
        await this.openScreen("goods_receipts", receipt.id);
    }

    async receiptAction(ev) {
        const command = ev.currentTarget.dataset.command;
        await this.runAction(async () => {
            this.state.detail = await this.rpc("receipt_command", [], {
                receipt_id: this.state.detail.id,
                command,
                quantities: this.state.form.quantities || {},
                result: this.state.form.inspection || "pass",
                notes: this.state.form.note || "",
                delivery_notes: this.state.form.delivery_notes || "",
                lines: this.state.form.lines || [],
            });
            this.state.form = this.formFromDetail(this.state.detail);
            if (this.state.detail.inspection_result) {
                this.state.form.inspection = this.state.detail.inspection_result;
            }
            this.state.notice = "Receipt updated.";
            await this.refreshKeepingForm();
        });
    }

    async receiptInvoice() {
        const number = this.state.form.supplier_invoice_number || "";
        await this.runAction(async () => {
            const detail = await this.rpc("invoice_from_receipt", [
                this.state.detail.id,
                number,
            ]);
            await this.openScreen("invoice_matching");
            this.state.notice = "Invoice " + detail.name + " created from the goods receipt.";
        });
    }

    async invoiceAction(ev) {
        const command = ev.currentTarget.dataset.command;
        await this.runAction(async () => {
            if (command === "batch") {
                const result = await this.rpc("invoice_auto_match_batch");
                this.state.notice = `Auto-match processed ${result.processed} invoice(s).`;
            } else {
                this.state.detail = await this.rpc("invoice_command", [
                    this.state.detail.id,
                    command,
                    this.state.form.note || "",
                ]);
                this.state.form = this.formFromDetail(this.state.detail);
                this.state.notice = "Invoice match updated.";
            }
            await this.refreshKeepingForm();
        });
    }

    async saveInvoice() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_invoice", [this.state.form]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Invoice recorded.";
            await this.refreshKeepingForm();
        });
    }

    async saveSupplier() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_supplier", [this.state.form]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Supplier saved.";
            await this.refreshKeepingForm();
        });
    }

    async saveContact() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_supplier_contact", [
                this.state.detail.id,
                this.state.form.contact_name,
                this.state.form.contact_email || "",
                this.state.form.contact_phone || "",
                this.state.form.contact_function || "",
            ]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Contact added.";
            await this.refreshKeepingForm();
        });
    }

    async saveContract() {
        await this.runAction(async () => {
            this.state.detail = await this.rpc("save_contract", [{
                profile_id: this.state.detail.id,
                name: this.state.form.contract_name,
                date_start: this.state.form.contract_start || false,
                date_end: this.state.form.contract_end || false,
                payment_terms: this.state.form.payment_terms || "",
            }]);
            this.state.form = this.formFromDetail(this.state.detail);
            this.state.notice = "Contract saved.";
            await this.refreshKeepingForm();
        });
    }

    async saveReport(preview) {
        await this.runAction(async () => {
            const definitionId = await this.rpc("save_report_definition", [this.state.form]);
            this.state.form.id = definitionId;
            if (preview) {
                this.state.form.preview = await this.rpc("report_preview", [definitionId]);
                this.state.notice = "Preview ready.";
            } else {
                this.state.notice = "Report configuration saved.";
            }
            await this.refreshKeepingForm();
        });
    }

    async exportReport(ev) {
        const fileFormat = ev.currentTarget.dataset.format;
        await this.runAction(async () => {
            let definitionId = this.state.form.id;
            if (!definitionId) {
                definitionId = await this.rpc("save_report_definition", [this.state.form]);
                this.state.form.id = definitionId;
            }
            const result = await this.rpc("report_export", [definitionId, fileFormat]);
            if (!result.ok) {
                this.state.error = result.error || "Report export failed.";
                return;
            }
            this.download(result);
            this.state.notice = "Export ready.";
            await this.refreshKeepingForm();
        });
    }

    async exportAudit() {
        await this.runAction(async () => {
            const result = await this.rpc("export_audit");
            if (!result.ok) {
                this.state.error = result.error || "Audit export failed.";
                return;
            }
            this.download(result);
        });
    }

    async onAttachment(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file || !this.state.detail) {
            return;
        }
        const datas = await this.readFile(file);
        await this.runAction(async () => {
            const model = {
                requisitions: "procurement.management.requisition",
                rfqs: "procurement.management.rfq",
                purchase_orders: "procurement.management.purchase.order",
                goods_receipts: "procurement.management.receipt",
                invoice_matching: "procurement.management.invoice.match",
            }[this.state.screen];
            this.state.detail.attachments = await this.rpc("add_attachment", [
                model,
                this.state.detail.id,
                file.name,
                datas,
            ]);
            this.state.notice = "Attachment added.";
        });
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const value = String(reader.result || "");
                resolve(value.includes(",") ? value.split(",")[1] : value);
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    download(result) {
        const binary = atob(result.datas || "");
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index++) {
            bytes[index] = binary.charCodeAt(index);
        }
        const blob = new Blob([bytes], { type: result.mimetype || "application/octet-stream" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = result.filename || "download";
        link.click();
        URL.revokeObjectURL(url);
    }

    async goRequisition() {
        await this.openScreen("requisitions");
        this.openCreate();
    }

    async goReports() {
        await this.openScreen("reports");
    }

    async goBuilder(ev) {
        const reportType = ev?.currentTarget?.dataset?.type;
        await this.openScreen("report_builder");
        if (reportType && reportType !== "custom") {
            this.state.form.report_type = reportType;
        }
    }

    async openPriority(ev) {
        const screen = ev.currentTarget.dataset.screen;
        const id = Number(ev.currentTarget.dataset.id);
        if (screen) {
            await this.openScreen(screen, id || false);
        }
    }

    countEntries(counts) {
        return Object.entries(counts || {}).map(([key, value]) => ({ key, value }));
    }

    lineQty(row) {
        return (row.lines || []).reduce((sum, line) => sum + (Number(line.quantity) || 0), 0);
    }

    recommendedRow() {
        const id = this.state.data.recommended_quotation_id;
        return (this.state.data.rows || []).find((row) => row.id === id);
    }

    chartHeight(amount) {
        const series = this.state.data.spend_series || [];
        const max = Math.max(...series.map((row) => Number(row.spend) || 0), 0);
        if (!max) {
            return 0;
        }
        return Math.round((Number(amount) / max) * 100);
    }

    setQuantity(ev) {
        const id = ev.currentTarget.dataset.id;
        this.state.form.quantities[id] = Number(ev.target.value);
    }
}
registry.category("actions").add("procurement_management_app", ProcurementManagementApp);
