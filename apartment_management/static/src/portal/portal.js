/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "dashboard", label: "Dashboard", icon: "fa-th-large" },
    { id: "property", label: "My Property", icon: "fa-home" },
    { id: "lease", label: "Lease", icon: "fa-file-text-o" },
    { id: "payments", label: "Payments", icon: "fa-credit-card" },
    { id: "ledger", label: "Ledger", icon: "fa-book" },
    { id: "maintenance", label: "Maintenance", icon: "fa-wrench" },
    { id: "messages", label: "Messages", icon: "fa-commenting-o" },
    { id: "documents", label: "Documents", icon: "fa-folder-o" },
    { id: "notifications", label: "Notifications", icon: "fa-bell-o" },
    { id: "settings", label: "Profile & Settings", icon: "fa-cog" },
];

const PAGE_COPY = {
    lease: ["Lease", "Lease term, rent, and eligibility."],
    payments: ["Payments", "Rent history and upcoming charges."],
    ledger: ["Ledger", "Charges, credits, and running balance."],
    maintenance: ["Maintenance", "Open, in-progress, and completed requests."],
    messages: ["Messages", "Conversations with property management."],
    documents: ["Documents", "Lease files and notices."],
    notifications: ["Notifications", "Alerts for rent, renewal, and requests."],
    settings: ["Profile & Settings", "Account details for this portal."],
};

const DOC_TABS = [
    { id: "all", label: "All" },
    { id: "lease", label: "Lease Agreements" },
    { id: "invoice", label: "Invoices & Receipts" },
    { id: "maintenance", label: "Maintenance Logs" },
    { id: "property", label: "Property Docs" },
    { id: "notice", label: "Notices" },
];

const NOTE_TABS = [
    { id: "all", label: "All" },
    { id: "payments", label: "Payments" },
    { id: "lease", label: "Lease" },
    { id: "maintenance", label: "Maintenance" },
    { id: "documents", label: "Documents" },
    { id: "messages", label: "Messages" },
];

export class ApartmentPortal extends Component {
    static template = "apartment_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            page: "dashboard",
            propertyView: "overview",
            leaseView: "overview",
            leaseSearch: "",
            leaseStatus: "all",
            leasePage: 1,
            leaseZoom: 100,
            leaseDoc: "original",
            renewing: false,
            payView: "overview",
            paySearch: "",
            payStatus: "all",
            payMethod: "all",
            payPage: 1,
            ledgerSearch: "",
            ledgerType: "all",
            ledgerPage: 1,
            ledgerFilter: false,
            maintSearch: "",
            maintPage: 1,
            maintView: "list",
            maintForm: {
                unitId: "",
                category: "",
                title: "",
                description: "",
                accessDate: "",
                accessSlot: "Morning (8am – 12pm)",
                notes: "",
                priority: "medium",
                fileNames: [],
                fileName: "",
                fileContent: "",
            },
            creatingMaint: false,
            msgSearch: "",
            msgThread: "renewal",
            msgView: "thread",
            msgReply: "",
            msgCompose: false,
            msgSubject: "",
            msgFile: "",
            msgFileContent: "",
            msgVoice: false,
            recordingVoice: false,
            sendingMsg: false,
            showNewLease: false,
            savingLease: false,
            leaseForm: { tenant: "", start: "", end: "", rent: 0, deposit: 0 },
            showClarify: false,
            clarifyNote: "",
            savingClarify: false,
            showMaintDetail: false,
            maintDetail: { id: false, issue: "", description: "", notes: "", state: "open", attachment_name: "", has_file: false, scheduled: "" },
            savingMaint: false,
            showPassword: false,
            savingPassword: false,
            passwordForm: { current: "", next: "", confirm: "" },
            showLogins: false,
            loadingLogins: false,
            loginRows: [],
            docView: "list",
            docSearch: "",
            docTab: "all",
            docPage: 1,
            docId: false,
            docZoom: 100,
            docSheet: 1,
            docSelected: {},
            uploadingDoc: false,
            noteSearch: "",
            noteTab: "all",
            editingUnit: false,
            savingUnit: false,
            unitForm: { name: "", layout: "", area: "" },
            editingTenant: false,
            savingTenant: false,
            tenantForm: {
                name: "",
                email: "",
                phone: "",
                rent: 0,
                deposit: 0,
                lease_start: "",
                lease_end: "",
                area: 0,
                auto_renew: "off",
            },
            editingProfile: false,
            savingProfile: false,
            savingPref: false,
            profileForm: {
                name: "",
                email: "",
                phone: "",
                role: "",
                address: "",
            },
            search: "",
            loading: true,
            paying: false,
            data: {},
        });
        this.navItems = NAV;
        this.docTabs = DOC_TABS;
        this.noteTabs = NOTE_TABS;
        this.maintPriorities = [
            { id: "low", title: "Low Priority", note: "Cosmetic issues, minor inconveniences. Resolvable within 1-2 weeks." },
            { id: "medium", title: "Medium Priority", note: "Standard repairs, non-critical appliance issues. Resolvable within 3-5 days." },
            { id: "high", title: "High Priority", note: "Critical fixtures, major leaks, safety issues. Resolvable within 24 hours." },
            { id: "emergency", title: "Emergency", note: "Immediate threat to health, safety, or property structure. Immediate action required." },
        ];
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "get_dashboard_data", []);
            this.syncProfile();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load the portal.", {
                title: "Apartment Management",
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        if (id === "property") {
            this.state.propertyView = "overview";
        }
        if (id === "lease") {
            this.state.leaseView = "overview";
        }
        if (id === "payments") {
            this.state.payView = "overview";
            this.state.payPage = 1;
        }
        if (id === "ledger") {
            this.state.ledgerPage = 1;
        }
        if (id === "maintenance") {
            this.state.maintPage = 1;
            this.state.maintView = "list";
        }
        if (id === "messages") {
            this.state.msgView = "thread";
            const threads = this.threads();
            if (threads.length && !threads.some((row) => row.id === this.state.msgThread)) {
                this.state.msgThread = threads[0].id;
            }
        }
        if (id === "documents") {
            this.state.docView = "list";
            this.state.docPage = 1;
        }
    }

    setLeaseView(view, doc) {
        this.state.leaseView = view;
        if (doc) {
            this.state.leaseDoc = doc;
        }
        this.state.leaseZoom = 100;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    onLeaseSearch(ev) {
        this.state.leaseSearch = ev.target.value;
        this.state.leasePage = 1;
    }

    onLeaseStatus(ev) {
        this.state.leaseStatus = ev.target.value;
        this.state.leasePage = 1;
    }

    lease() {
        return this.state.data.lease || { files: [], pages: [], history: [] };
    }

    filteredHistory() {
        const rows = this.lease().history || [];
        const q = (this.state.leaseSearch || "").trim().toLowerCase();
        const status = this.state.leaseStatus;
        return rows.filter((row) => {
            const hit = !q || `${row.code} ${row.tenant} ${row.file}`.toLowerCase().includes(q);
            return hit && (status === "all" || row.status === status);
        });
    }

    pagedHistory() {
        const start = (this.state.leasePage - 1) * 8;
        return this.filteredHistory().slice(start, start + 8);
    }

    historyPages() {
        return Math.max(1, Math.ceil(this.filteredHistory().length / 8));
    }

    setHistoryPage(page) {
        const last = this.historyPages();
        this.state.leasePage = Math.min(Math.max(page, 1), last);
    }

    bumpZoom(delta) {
        this.state.leaseZoom = Math.min(140, Math.max(80, this.state.leaseZoom + delta));
    }

    printLease() {
        window.print();
    }

    async decideRenewal(decision) {
        if (this.state.renewing) {
            return;
        }
        this.state.renewing = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "set_lease_renewal", [decision]);
            this.notification.add(
                decision === "accepted" ? "Renewal accepted. The lease term was extended." : "Renewal declined.",
                { title: "Lease", type: decision === "accepted" ? "success" : "warning" }
            );
            this.state.leaseView = "overview";
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update the renewal.", {
                title: "Lease",
                type: "danger",
            });
        } finally {
            this.state.renewing = false;
        }
    }

    setPropertyView(view) {
        this.state.propertyView = view;
        this.state.editingUnit = false;
        this.state.editingTenant = false;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    startEditTenant() {
        const data = this.state.data || {};
        this.state.tenantForm = {
            name: data.tenant_name || "",
            email: data.tenant_email || "",
            phone: data.tenant_phone || "",
            rent: data.rent_amount || 0,
            deposit: data.deposit_amount || 0,
            lease_start: data.lease_start_iso || "",
            lease_end: data.lease_end_iso || "",
            area: data.area_sqft || 0,
            auto_renew: data.auto_renew_on ? "on" : "off",
        };
        this.state.editingTenant = true;
    }

    cancelEditTenant() {
        this.state.editingTenant = false;
    }

    async saveTenant() {
        const form = this.state.tenantForm;
        if (!String(form.name || "").trim()) {
            this.notification.add("Tenant name is required.", { title: "Tenant", type: "warning" });
            return;
        }
        this.state.savingTenant = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "update_tenant_details", [form]);
            this.state.editingTenant = false;
            this.notification.add("Tenant details saved.", { title: "Tenant", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save tenant details.", {
                title: "Tenant",
                type: "danger",
            });
        } finally {
            this.state.savingTenant = false;
        }
    }

    startEditUnit() {
        const data = this.state.data || {};
        this.state.unitForm = {
            name: data.unit_short || "",
            layout: data.layout || "",
            area: data.area_sqft || "",
        };
        this.state.editingUnit = true;
    }

    cancelEditUnit() {
        this.state.editingUnit = false;
    }

    setUnitField(field, ev) {
        this.state.unitForm[field] = ev.target.value;
    }

    async saveUnit() {
        this.state.savingUnit = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "update_unit", [this.state.unitForm]);
            this.state.editingUnit = false;
            this.notification.add("Unit updated.", { title: "Unit", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save the unit.", {
                title: "Unit",
                type: "danger",
            });
        } finally {
            this.state.savingUnit = false;
        }
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
    }

    pageTitle() {
        return PAGE_COPY[this.state.page]?.[0] || "Dashboard";
    }

    pageSubtitle() {
        return PAGE_COPY[this.state.page]?.[1] || "";
    }

    ping(title, message) {
        this.notification.add(message, { title, type: "info" });
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const text = String(reader.result || "");
                resolve(text.includes(",") ? text.split(",").slice(1).join(",") : text);
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    saveDownload(payload) {
        const binary = atob(payload.content || "");
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index++) {
            bytes[index] = binary.charCodeAt(index);
        }
        const blob = new Blob([bytes], { type: payload.mimetype || "application/octet-stream" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = payload.filename || "download";
        link.click();
        URL.revokeObjectURL(link.href);
    }

    async downloadStoredDoc(doc) {
        if (!doc?.record_id && !doc?.has_file) {
            await this.downloadLease();
            return;
        }
        try {
            const payload = await this.orm.call("apartment.portal", "get_document_file", [doc.record_id || doc.id]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the file.", {
                title: "Documents",
                type: "danger",
            });
        }
    }

    async downloadLease(tenancyId) {
        try {
            const payload = await this.orm.call("apartment.portal", "download_lease", [tenancyId || false]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the lease.", {
                title: "Lease",
                type: "danger",
            });
        }
    }

    messageTenant() {
        this.onNav("messages");
        this.openCompose();
        this.state.msgSubject = `Message for ${this.state.data.tenant_name || "tenant"}`;
    }

    openNewLease() {
        const data = this.state.data || {};
        this.state.leaseForm = {
            tenant: data.tenant_name || "",
            start: data.lease_end_iso || "",
            end: "",
            rent: data.rent_amount || 0,
            deposit: data.deposit_amount || 0,
        };
        this.state.showNewLease = true;
    }

    async saveNewLease() {
        const form = this.state.leaseForm;
        if (!String(form.tenant || "").trim() || !form.start || !form.end) {
            this.notification.add("Tenant, start date, and end date are required.", { title: "Lease", type: "warning" });
            return;
        }
        this.state.savingLease = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "create_lease", [form]);
            this.state.showNewLease = false;
            this.notification.add("Lease created.", { title: "Lease", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not create the lease.", {
                title: "Lease",
                type: "danger",
            });
        } finally {
            this.state.savingLease = false;
        }
    }

    async saveClarify() {
        this.state.savingClarify = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "request_clarification", [this.state.clarifyNote]);
            this.state.showClarify = false;
            this.state.clarifyNote = "";
            const latest = this.state.data.inbox && this.state.data.inbox.threads[0];
            if (latest) {
                this.state.msgThread = latest.id;
            }
            this.notification.add("Clarification request sent.", { title: "Lease", type: "success" });
            this.onNav("messages");
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not send the request.", {
                title: "Lease",
                type: "danger",
            });
        } finally {
            this.state.savingClarify = false;
        }
    }

    filteredDocs() {
        const docs = this.state.data.docs || [];
        const q = (this.state.search || "").trim().toLowerCase();
        if (!q) {
            return docs;
        }
        return docs.filter((doc) => (doc.name || "").toLowerCase().includes(q));
    }

    async downloadDoc(doc) {
        try {
            const payload = await this.orm.call("apartment.portal", "download_card_document", [
                doc?.record_id || false,
                doc?.name || "Property Rules",
            ]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the document.", {
                title: "Documents",
                type: "danger",
            });
        }
    }

    libraryRows() {
        return this.state.data.library || [];
    }

    onDocSearch(ev) {
        this.state.docSearch = ev.target.value;
        this.state.docPage = 1;
    }

    setDocTab(tab) {
        this.state.docTab = tab;
        this.state.docPage = 1;
        this.state.docSelected = {};
    }

    filteredLibrary() {
        const q = (this.state.docSearch || "").trim().toLowerCase();
        const tab = this.state.docTab;
        return this.libraryRows().filter((row) => {
            const blob = `${row.name} ${row.property} ${row.category_label} ${row.uploaded_by} ${(row.tags || []).join(" ")}`.toLowerCase();
            const hit = !q || blob.includes(q);
            const tabOk = tab === "all" || row.category === tab;
            return hit && tabOk;
        });
    }

    pagedLibrary() {
        const start = (this.state.docPage - 1) * 10;
        return this.filteredLibrary().slice(start, start + 10);
    }

    docPages() {
        return Math.max(1, Math.ceil(this.filteredLibrary().length / 10));
    }

    docRangeLabel() {
        const total = this.filteredLibrary().length;
        if (!total) {
            return "Showing 0 documents";
        }
        const start = (this.state.docPage - 1) * 10 + 1;
        const end = Math.min(this.state.docPage * 10, total);
        return `Showing ${start} to ${end} of ${total} documents`;
    }

    setDocListPage(page) {
        this.state.docPage = Math.min(Math.max(page, 1), this.docPages());
    }

    toggleDoc(id) {
        const selected = { ...this.state.docSelected };
        if (selected[id]) {
            delete selected[id];
        } else {
            selected[id] = true;
        }
        this.state.docSelected = selected;
    }

    toggleAllDocs() {
        const rows = this.pagedLibrary();
        const allOn = rows.length && rows.every((row) => this.state.docSelected[row.id]);
        const selected = { ...this.state.docSelected };
        rows.forEach((row) => {
            if (allOn) {
                delete selected[row.id];
            } else {
                selected[row.id] = true;
            }
        });
        this.state.docSelected = selected;
    }

    allDocsChecked() {
        const rows = this.pagedLibrary();
        return rows.length > 0 && rows.every((row) => this.state.docSelected[row.id]);
    }

    activeDoc() {
        const rows = this.libraryRows();
        return rows.find((row) => row.id === this.state.docId) || rows[0] || null;
    }

    openDoc(row) {
        this.state.docId = row.id;
        this.state.docView = "viewer";
        this.state.docZoom = 100;
        this.state.docSheet = 1;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    closeDoc() {
        this.state.docView = "list";
    }

    bumpDocZoom(delta) {
        this.state.docZoom = Math.min(160, Math.max(60, this.state.docZoom + delta));
    }

    setDocSheet(page) {
        const row = this.activeDoc();
        const last = row ? row.pages || 1 : 1;
        this.state.docSheet = Math.min(Math.max(page, 1), last);
    }

    docPreview() {
        const row = this.activeDoc() || {};
        const landlord = "Apartment Management Inc.";
        if (row.category === "lease") {
            return {
                kicker: `Page ${this.state.docSheet} of ${row.pages || 12}`,
                title: "COMMERCIAL LEASE AGREEMENT",
                subtitle: "LEASE AGREEMENT",
                lines: [
                    `THIS LEASE AGREEMENT (the "Lease") is made and entered into this ${row.date_label || "24th day of October, 2023"}, by and between ${landlord} ("Landlord") and ACME Corp ("Tenant").`,
                    "1. Premises. Landlord leases to Tenant the premises described as Unit 4B, together with the right to use common areas of the building.",
                    "2. Term. The term of this Lease shall commence on the start date and continue for twelve (12) months, unless earlier terminated as provided herein.",
                    "3. Rent. Tenant shall pay monthly rent in advance on the first day of each month, without deduction or setoff.",
                    "4. Use. Tenant shall use the premises solely for lawful occupancy and shall not commit waste or nuisance.",
                    "5. Maintenance. Tenant shall keep the interior in good repair. Landlord shall maintain structural elements and building systems.",
                    "IN WITNESS WHEREOF, the parties have executed this Lease as of the date first written above.",
                ],
            };
        }
        return {
            kicker: `Page ${this.state.docSheet} of ${row.pages || 1}`,
            title: (row.name || "Document").replace(/_/g, " "),
            subtitle: row.type_label || "Document",
            lines: [
                `${row.type_label || "Document"} for ${row.property || "the property"}.`,
                `Uploaded by ${row.uploaded_by || "System"} on ${row.date_label || "—"}.`,
                `Status: ${row.status || "On file"}. Version ${row.version || "v1.0"}.`,
                "Open Download PDF to save a copy, or Print Document for a paper version.",
            ],
        };
    }

    downloadLibrary(row) {
        const current = row || this.activeDoc();
        if (!current) {
            return;
        }
        if (current.has_file && (current.record_id || current.id)) {
            this.downloadStoredDoc(current);
            return;
        }
        const preview = this.docPreview();
        const text = [preview.title, preview.subtitle, "", ...preview.lines].join("\n");
        const blob = new Blob([text], { type: "text/plain" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = current.name || "document.txt";
        link.click();
        URL.revokeObjectURL(link.href);
    }

    printLibrary() {
        window.print();
    }

    async onUploadDoc(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file || this.state.uploadingDoc) {
            return;
        }
        this.state.uploadingDoc = true;
        try {
            const content = await this.readFile(file);
            this.state.data = await this.orm.call("apartment.portal", "upload_library_doc", [
                file.name,
                this.state.docTab === "all" ? "property" : this.state.docTab,
                content,
            ]);
            this.state.docView = "list";
            this.state.docPage = 1;
            this.notification.add("Document uploaded.", { title: "Documents", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not upload the document.", {
                title: "Documents",
                type: "danger",
            });
        } finally {
            this.state.uploadingDoc = false;
        }
    }

    payments() {
        return this.state.data.payments || { rows: [] };
    }

    setPayView(view) {
        this.state.payView = view;
        this.state.payPage = 1;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    onPaySearch(ev) {
        this.state.paySearch = ev.target.value;
        this.state.payPage = 1;
    }

    onPayStatus(ev) {
        this.state.payStatus = ev.target.value;
        this.state.payPage = 1;
    }

    onPayMethod(ev) {
        this.state.payMethod = ev.target.value;
        this.state.payPage = 1;
    }

    payPageSize() {
        return this.state.payView === "history" ? 4 : 5;
    }

    filteredPayments() {
        const rows = this.payments().rows || [];
        const q = (this.state.paySearch || "").trim().toLowerCase();
        const status = this.state.payStatus;
        const method = this.state.payMethod;
        return rows.filter((row) => {
            const blob = `${row.description} ${row.reference} ${row.property} ${row.unit} ${row.method}`.toLowerCase();
            const hit = !q || blob.includes(q);
            const statusOk = status === "all" || row.status === status;
            const methodOk = method === "all" || (row.method || "").toLowerCase().includes(method.toLowerCase());
            return hit && statusOk && methodOk;
        });
    }

    pagedPayments() {
        const size = this.payPageSize();
        const start = (this.state.payPage - 1) * size;
        return this.filteredPayments().slice(start, start + size);
    }

    payPages() {
        return Math.max(1, Math.ceil(this.filteredPayments().length / this.payPageSize()));
    }

    pageNumbers() {
        return Array.from({ length: this.payPages() }, (_, index) => index + 1);
    }

    setPayPage(page) {
        this.state.payPage = Math.min(Math.max(page, 1), this.payPages());
    }

    payRangeLabel() {
        const total = this.filteredPayments().length;
        if (!total) {
            return "Showing 0 entries";
        }
        const size = this.payPageSize();
        const start = (this.state.payPage - 1) * size + 1;
        const end = Math.min(this.state.payPage * size, total);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    exportPaymentsCsv() {
        const rows = this.filteredPayments();
        const header = "Date,Reference,Property,Unit,Description,Method,Amount,Status";
        const lines = rows.map((row) =>
            [row.date_label, row.reference, row.property, row.unit, row.description, row.method, row.amount_label, row.status]
                .map((value) => `"${(value || "").toString().replaceAll('"', '""')}"`)
                .join(",")
        );
        const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "payment_history.csv";
        link.click();
        URL.revokeObjectURL(url);
        this.ping("Payments", "Payment history exported.");
    }

    async addPaymentRecord() {
        try {
            this.state.data = await this.orm.call("apartment.portal", "add_payment_record", []);
            this.notification.add("A pending payment record was added.", { title: "Payments", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not add the record.", {
                title: "Payments",
                type: "danger",
            });
        }
    }

    async receiptPing(row) {
        try {
            const payload = await this.orm.call("apartment.portal", "get_payment_receipt", [row.id]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the receipt.", {
                title: "Receipt",
                type: "danger",
            });
        }
    }

    ledger() {
        return this.state.data.ledger || { rows: [] };
    }

    onLedgerSearch(ev) {
        this.state.ledgerSearch = ev.target.value;
        this.state.ledgerPage = 1;
    }

    onLedgerType(ev) {
        this.state.ledgerType = ev.target.value;
        this.state.ledgerPage = 1;
    }

    toggleLedgerFilter() {
        this.state.ledgerFilter = !this.state.ledgerFilter;
    }

    filteredLedger() {
        const rows = this.ledger().rows || [];
        const q = (this.state.ledgerSearch || "").trim().toLowerCase();
        const type = this.state.ledgerType;
        return rows.filter((row) => {
            const hit = !q || `${row.description} ${row.type}`.toLowerCase().includes(q);
            return hit && (type === "all" || row.type === type);
        });
    }

    pagedLedger() {
        const start = (this.state.ledgerPage - 1) * 5;
        return this.filteredLedger().slice(start, start + 5);
    }

    ledgerPages() {
        return Math.max(1, Math.ceil(this.filteredLedger().length / 5));
    }

    ledgerPageNumbers() {
        return Array.from({ length: this.ledgerPages() }, (_, index) => index + 1);
    }

    setLedgerPage(page) {
        this.state.ledgerPage = Math.min(Math.max(page, 1), this.ledgerPages());
    }

    ledgerRangeLabel() {
        const total = this.filteredLedger().length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.ledgerPage - 1) * 5 + 1;
        const end = Math.min(this.state.ledgerPage * 5, total);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    exportLedgerCsv() {
        const rows = this.filteredLedger();
        const header = "Date,Type,Description,Debit,Credit,Balance";
        const lines = rows.map((row) =>
            [row.date_label, row.type, row.description, row.debit_label, row.credit_label, row.balance_label]
                .map((value) => `"${(value || "").toString().replaceAll('"', '""')}"`)
                .join(",")
        );
        const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "ledger.csv";
        link.click();
        URL.revokeObjectURL(url);
        this.ping("Ledger", "Ledger exported.");
    }

    maintPageData() {
        return this.state.data.maint_page || { rows: [] };
    }

    unitOptions() {
        return this.state.data.units || [];
    }

    onMaintSearch(ev) {
        this.state.maintSearch = ev.target.value;
        this.state.maintPage = 1;
    }

    filteredMaint() {
        const rows = this.maintPageData().rows || [];
        const q = (this.state.maintSearch || "").trim().toLowerCase();
        if (!q) {
            return rows;
        }
        return rows.filter((row) => `${row.code} ${row.issue} ${row.category} ${row.status}`.toLowerCase().includes(q));
    }

    pagedMaint() {
        const start = (this.state.maintPage - 1) * 4;
        return this.filteredMaint().slice(start, start + 4);
    }

    maintPages() {
        return Math.max(1, Math.ceil(this.filteredMaint().length / 4));
    }

    maintPageNumbers() {
        return Array.from({ length: this.maintPages() }, (_, index) => index + 1);
    }

    setMaintPage(page) {
        this.state.maintPage = Math.min(Math.max(page, 1), this.maintPages());
    }

    maintRangeLabel() {
        const total = this.filteredMaint().length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.maintPage - 1) * 4 + 1;
        const end = Math.min(this.state.maintPage * 4, total);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    openMaintModal() {
        this.state.maintView = "create";
        this.state.maintForm.unitId = this.state.data.unit_id || "";
        this.state.maintForm.category = "";
        this.state.maintForm.title = "";
        this.state.maintForm.description = "";
        this.state.maintForm.accessDate = "";
        this.state.maintForm.accessSlot = "Morning (8am – 12pm)";
        this.state.maintForm.notes = "";
        this.state.maintForm.priority = "medium";
        this.state.maintForm.fileNames = [];
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    closeMaintModal() {
        this.state.maintView = "list";
    }

    setMaintForm(field, ev) {
        this.state.maintForm[field] = ev.target.value;
    }

    setMaintPriority(id) {
        this.state.maintForm.priority = id;
    }

    async onMaintFiles(ev) {
        const files = [...(ev.target.files || [])];
        this.state.maintForm.fileNames = files.map((file) => file.name);
        const first = files[0];
        if (first) {
            this.state.maintForm.fileName = first.name;
            this.state.maintForm.fileContent = await this.readFile(first);
        } else {
            this.state.maintForm.fileName = "";
            this.state.maintForm.fileContent = "";
        }
    }

    async submitMaint() {
        if (this.state.creatingMaint) {
            return;
        }
        if (!this.state.maintForm.title.trim()) {
            this.ping("Maintenance", "Enter an issue title.");
            return;
        }
        this.state.creatingMaint = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "create_maintenance_request", [{
                title: this.state.maintForm.title,
                category: this.state.maintForm.category,
                unit_id: this.state.maintForm.unitId,
                description: this.state.maintForm.description,
                priority: this.state.maintForm.priority,
                access_date: this.state.maintForm.accessDate || false,
                access_slot: this.state.maintForm.accessSlot,
                notes: this.state.maintForm.notes || "",
                file_name: this.state.maintForm.fileName || false,
                file_content: this.state.maintForm.fileContent || false,
            }]);
            this.state.maintForm.fileNames = [];
            this.state.maintForm.fileName = "";
            this.state.maintForm.fileContent = "";
            this.state.maintView = "list";
            this.notification.add("Maintenance request submitted.", { title: "Maintenance", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not create the request.", {
                title: "Maintenance",
                type: "danger",
            });
        } finally {
            this.state.creatingMaint = false;
        }
    }

    viewMaint(row) {
        this.state.maintDetail = {
            id: row.id,
            code: row.code,
            issue: row.issue,
            description: row.description || "",
            notes: row.notes || "",
            state: row.state || "open",
            attachment_name: row.attachment_name || "",
            has_file: row.has_file,
            scheduled: "",
        };
        this.state.showMaintDetail = true;
    }

    async saveMaintDetail() {
        const detail = this.state.maintDetail;
        this.state.savingMaint = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "update_maintenance", [detail.id, {
                state: detail.state,
                notes: detail.notes,
                scheduled_date: detail.scheduled || false,
            }]);
            this.state.showMaintDetail = false;
            this.notification.add("Maintenance request updated.", { title: "Maintenance", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update the request.", {
                title: "Maintenance",
                type: "danger",
            });
        } finally {
            this.state.savingMaint = false;
        }
    }

    async downloadMaintFile() {
        try {
            const payload = await this.orm.call("apartment.portal", "get_maintenance_file", [this.state.maintDetail.id]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the file.", {
                title: "Maintenance",
                type: "danger",
            });
        }
    }

    inbox() {
        return this.state.data.inbox || { threads: [], unread: 0 };
    }

    inboxUnread() {
        return this.inbox().unread || 0;
    }

    threads() {
        const q = (this.state.msgSearch || "").trim().toLowerCase();
        const rows = this.inbox().threads || [];
        if (!q) {
            return rows;
        }
        return rows.filter((row) => `${row.author} ${row.subject} ${row.preview} ${row.tag}`.toLowerCase().includes(q));
    }

    activeThread() {
        return this.threads().find((row) => row.id === this.state.msgThread) || this.threads()[0] || null;
    }

    replyPlaceholder() {
        const thread = this.activeThread();
        return thread ? `Type your reply to ${thread.author}...` : "Type your reply...";
    }

    threadInitials() {
        const thread = this.activeThread();
        if (!thread) {
            return "AM";
        }
        return (thread.author || "AM").split(" ").slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
    }

    onMsgSearch(ev) {
        this.state.msgSearch = ev.target.value;
    }

    onMsgReply(ev) {
        this.state.msgReply = ev.target.value;
    }

    onReplyKey(ev) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            this.sendReply();
        }
    }

    openInbox() {
        this.state.msgView = "inbox";
        this.state.msgCompose = false;
    }

    openThread(id) {
        this.state.msgThread = id;
        this.state.msgView = "thread";
        this.state.msgCompose = false;
        this.state.msgReply = "";
        this.state.msgFile = "";
    }

    openCompose() {
        this.state.msgView = "thread";
        this.state.msgCompose = true;
        this.state.msgSubject = "";
        this.state.msgReply = "";
        this.state.msgFile = "";
        this.state.msgFileContent = "";
        this.state.msgVoice = false;
    }

    focusComposer() {
        this.state.msgCompose = false;
        const input = document.querySelector(".o_apartment_portal .am-composer-input");
        if (input) {
            input.focus();
        }
    }

    wrapBold() {
        const text = this.state.msgReply || "";
        this.state.msgReply = text ? `**${text}**` : "** **";
        this.focusComposer();
    }

    async toggleVoice() {
        if (this._recorder && this._recorder.state === "recording") {
            this._recorder.stop();
            return;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            const chunks = [];
            recorder.ondataavailable = (event) => {
                if (event.data && event.data.size) {
                    chunks.push(event.data);
                }
            };
            recorder.onstop = async () => {
                stream.getTracks().forEach((track) => track.stop());
                const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
                this.state.msgFile = "Voice note.webm";
                this.state.msgVoice = true;
                this.state.msgFileContent = await this.readFile(blob);
                this.state.recordingVoice = false;
                this._recorder = null;
            };
            this._recorder = recorder;
            this.state.recordingVoice = true;
            recorder.start();
        } catch (error) {
            this.state.recordingVoice = false;
            this.notification.add("Allow microphone access to record a voice note.", { title: "Messages", type: "warning" });
        }
    }

    async onMsgFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        this.state.msgVoice = false;
        if (!file) {
            this.state.msgFile = "";
            this.state.msgFileContent = "";
            return;
        }
        this.state.msgFile = file.name;
        this.state.msgFileContent = await this.readFile(file);
    }

    async downloadMessageFile(note) {
        try {
            const payload = await this.orm.call("apartment.portal", "get_message_file", [note.id]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the file.", {
                title: "Messages",
                type: "danger",
            });
        }
    }

    printThread() {
        window.print();
    }

    async deleteThread() {
        const thread = this.activeThread();
        if (!thread) {
            return;
        }
        this.state.data = await this.orm.call("apartment.portal", "delete_thread", [thread.id]);
        this.state.msgView = "inbox";
        this.notification.add("Conversation removed.", { title: "Messages", type: "warning" });
    }

    async sendReply() {
        const thread = this.activeThread();
        if (this.state.sendingMsg || (!this.state.msgReply.trim() && !this.state.msgFile && !this.state.msgCompose)) {
            return;
        }
        this.state.sendingMsg = true;
        try {
            if (this.state.msgCompose) {
                this.state.data = await this.orm.call("apartment.portal", "start_thread", [
                    this.state.msgSubject,
                    this.state.msgReply,
                    this.state.msgFile || false,
                    this.state.msgFileContent || false,
                    this.state.msgVoice,
                ]);
                const latest = (this.state.data.inbox && this.state.data.inbox.threads[0]) || null;
                this.state.msgThread = latest ? latest.id : this.state.msgThread;
                this.state.msgCompose = false;
            } else if (thread) {
                this.state.data = await this.orm.call("apartment.portal", "send_message", [
                    thread.id,
                    this.state.msgReply,
                    this.state.msgFile || false,
                    this.state.msgFileContent || false,
                    this.state.msgVoice,
                ]);
            }
            this.state.msgReply = "";
            this.state.msgFile = "";
            this.state.msgFileContent = "";
            this.state.msgVoice = false;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not send the message.", {
                title: "Messages",
                type: "danger",
            });
        } finally {
            this.state.sendingMsg = false;
        }
    }

    async payNow() {
        if (this.state.paying) {
            return;
        }
        this.state.paying = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "pay_next_rent", []);
            this.notification.add("Payment recorded.", { title: "Payments", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not record the payment.", {
                title: "Payments",
                type: "danger",
            });
        } finally {
            this.state.paying = false;
        }
    }

    logout() {
        window.location = "/web/session/logout";
    }

    notices() {
        return this.state.data.notices || { rows: [], unread: 0 };
    }

    noticeUnread() {
        return this.notices().unread || 0;
    }

    filteredNotices() {
        const q = (this.state.noteSearch || "").trim().toLowerCase();
        const tab = this.state.noteTab;
        return (this.notices().rows || []).filter((row) => {
            const hit = !q || `${row.title} ${row.body}`.toLowerCase().includes(q);
            return hit && (tab === "all" || row.category === tab);
        });
    }

    onNoteSearch(ev) {
        this.state.noteSearch = ev.target.value;
    }

    setNoteTab(tab) {
        this.state.noteTab = tab;
    }

    openNotice(row) {
        const target = {
            payments: "payments",
            lease: "lease",
            maintenance: "maintenance",
            documents: "documents",
            messages: "messages",
        }[row.category];
        if (target) {
            this.onNav(target);
        }
    }

    async markNoticesRead() {
        this.state.data = await this.orm.call("apartment.portal", "mark_notices_read", []);
        this.notification.add("All notifications marked as read.", { title: "Notifications", type: "success" });
    }

    async archiveNotice(row, ev) {
        ev.stopPropagation();
        this.state.data = await this.orm.call("apartment.portal", "archive_notice", [row.id]);
    }

    async dismissNotice(row, ev) {
        ev.stopPropagation();
        this.state.data = await this.orm.call("apartment.portal", "dismiss_notice", [row.id]);
    }

    profile() {
        return this.state.data.profile || {};
    }

    prefs() {
        return this.state.data.prefs || {};
    }

    syncProfile() {
        const profile = this.profile();
        this.state.profileForm = {
            name: profile.name || "",
            email: profile.email || "",
            phone: profile.phone || "",
            role: profile.role || "",
            address: profile.address || "",
        };
    }

    setProfileField(field, ev) {
        this.state.profileForm[field] = ev.target.value;
    }

    startEditProfile() {
        this.syncProfile();
        this.state.editingProfile = true;
    }

    cancelEditProfile() {
        this.syncProfile();
        this.state.editingProfile = false;
    }

    async saveProfile() {
        this.state.savingProfile = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "update_profile", [this.state.profileForm]);
            this.state.editingProfile = false;
            this.syncProfile();
            this.notification.add("Profile updated.", { title: "Profile", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save the profile.", {
                title: "Profile",
                type: "danger",
            });
        } finally {
            this.state.savingProfile = false;
        }
    }

    async togglePref(field) {
        if (this.state.savingPref) {
            return;
        }
        const next = !this.prefs()[field];
        this.state.savingPref = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "update_pref", [field, next]);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update that setting.", {
                title: "Profile",
                type: "danger",
            });
        } finally {
            this.state.savingPref = false;
        }
    }

    async changePhoto(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        try {
            const content = await this.readFile(file);
            this.state.data = await this.orm.call("apartment.portal", "update_photo", [content]);
            this.notification.add("Photo updated.", { title: "Profile", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update the photo.", {
                title: "Profile",
                type: "danger",
            });
        }
    }

    async savePassword() {
        const form = this.state.passwordForm;
        if (!form.current || !form.next) {
            this.notification.add("Enter the current password and a new password.", { title: "Security", type: "warning" });
            return;
        }
        if (form.next !== form.confirm) {
            this.notification.add("The new password and confirmation do not match.", { title: "Security", type: "warning" });
            return;
        }
        this.state.savingPassword = true;
        try {
            this.state.data = await this.orm.call("apartment.portal", "change_own_password", [form.current, form.next]);
            this.state.showPassword = false;
            this.state.passwordForm = { current: "", next: "", confirm: "" };
            this.notification.add("Password updated.", { title: "Security", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not change the password.", {
                title: "Security",
                type: "danger",
            });
        } finally {
            this.state.savingPassword = false;
        }
    }

    async loginHistory() {
        this.state.showLogins = true;
        this.state.loadingLogins = true;
        try {
            this.state.loginRows = await this.orm.call("apartment.portal", "get_login_history", []);
        } catch (error) {
            this.state.loginRows = [];
            this.notification.add(error?.data?.message || error?.message || "Could not load login history.", {
                title: "Security",
                type: "danger",
            });
        } finally {
            this.state.loadingLogins = false;
        }
    }
}

registry.category("actions").add("apartment_management.portal", ApartmentPortal);
