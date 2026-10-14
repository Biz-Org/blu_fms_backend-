/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "dashboard", label: "Dashboard", icon: "fa-th-large" },
    { id: "property", label: "My Property", icon: "fa-building-o" },
    { id: "lease", label: "Lease", icon: "fa-file-text-o" },
    { id: "payments", label: "Payments", icon: "fa-credit-card" },
    { id: "ledger", label: "Ledger", icon: "fa-list-alt" },
    { id: "maintenance", label: "Maintenance", icon: "fa-wrench" },
    { id: "messages", label: "Messages", icon: "fa-envelope-o" },
    { id: "documents", label: "Documents", icon: "fa-folder-o" },
    { id: "notifications", label: "Notifications", icon: "fa-bell-o" },
    { id: "profile", label: "Profile & Settings", icon: "fa-cog" },
];

export class OtPortal extends Component {
    static template = "owner_tenant_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.navItems = NAV;
        this.docInput = useRef("docInput");
        this.maintInput = useRef("maintInput");
        this.state = useState({
            page: "dashboard",
            view: "list",
            loading: true,
            data: {},
            search: "",
            leaseFilter: "all",
            payFilter: "all",
            docTab: "all",
            noteTab: "all",
            selectedLease: false,
            selectedMaint: false,
            selectedDoc: false,
            selectedThread: false,
            maintForm: { title: "", category: "", unit_id: "", description: "", priority: "medium", access_date: "", access_slot: "Morning (8am - 12pm)", notes: "", attachment: "", file_data: "" },
            payForm: { name: "Payment", amount: "", method: "Bank ACH", status: "paid", description: "", unit_id: "" },
            leaseForm: { name: "", rent: "", start: "", end: "", unit_id: "" },
            profileForm: {},
            msgBody: "",
            maintMsg: "",
            newSubject: "",
            newBody: "",
            editingProfile: false,
            saving: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("ot.portal", "get_dashboard_data", []);
            this.state.profileForm = { ...(this.state.data.profile || {}) };
            const threads = this.threads();
            if (!this.state.selectedThread && threads.length) {
                this.state.selectedThread = threads[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || "Could not load portal.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async call(method, args = []) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("ot.portal", method, args);
            this.state.profileForm = { ...(this.state.data.profile || {}) };
        } catch (error) {
            this.notification.add(error?.data?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        this.state.view = "list";
    }

    unit() {
        return this.state.data.unit || {};
    }

    tenant() {
        return this.state.data.tenant || {};
    }

    lease() {
        return this.state.data.lease || {};
    }

    threads() {
        return this.state.data.threads || [];
    }

    selectedThread() {
        return this.threads().find((t) => t.id === this.state.selectedThread) || this.threads()[0] || {};
    }

    selectedMaint() {
        return (this.state.data.maints || []).find((m) => m.id === this.state.selectedMaint) || {};
    }

    selectedDoc() {
        return (this.state.data.docs || []).find((d) => d.id === this.state.selectedDoc) || {};
    }

    filteredLeases() {
        let rows = this.state.data.leases || [];
        if (this.state.leaseFilter !== "all") {
            rows = rows.filter((r) => r.status === this.state.leaseFilter);
        }
        const q = (this.state.search || "").toLowerCase();
        if (q) {
            rows = rows.filter((r) => `${r.name} ${r.tenant}`.toLowerCase().includes(q));
        }
        return rows;
    }

    filteredPays() {
        let rows = this.state.data.payments || [];
        if (this.state.payFilter !== "all") {
            rows = rows.filter((r) => r.status === this.state.payFilter);
        }
        return rows;
    }

    filteredDocs() {
        let rows = this.state.data.docs || [];
        if (this.state.docTab !== "all") {
            rows = rows.filter((r) => r.category === this.state.docTab);
        }
        return rows;
    }

    filteredNotes() {
        let rows = this.state.data.notifications || [];
        if (this.state.noteTab !== "all") {
            rows = rows.filter((r) => r.category === this.state.noteTab);
        }
        return rows;
    }

    badge(status) {
        return {
            active: "ok",
            paid: "ok",
            verified: "ok",
            done: "ok",
            completed: "ok",
            pending: "warn",
            open: "bad",
            failed: "bad",
            expired: "muted",
            terminated: "bad",
            renewed: "info",
            scheduled: "info",
            progress: "info",
            due: "warn",
        }[status] || "muted";
    }

    async payNow() {
        await this.call("pay_now", []);
        this.notification.add("Payment recorded.", { type: "success" });
    }

    async addPayment() {
        await this.call("add_payment", [this.state.payForm]);
        this.state.view = "list";
        this.notification.add("Payment saved.", { type: "success" });
    }

    async exportKind(kind) {
        const file = await this.orm.call("ot.portal", "export_csv", [kind]);
        const blob = new Blob([file.csv || ""], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.filename || `${kind}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    openLeaseDoc() {
        this.state.page = "lease";
        this.state.view = "viewer";
    }

    openHistory() {
        this.state.page = "lease";
        this.state.view = "history";
    }

    openRenewal() {
        this.state.page = "lease";
        this.state.view = "renewal";
    }

    async doRenew(action) {
        await this.call("renew_lease", [this.lease().id, action]);
        this.notification.add("Renewal updated.", { type: "success" });
        if (action !== "start") {
            this.state.view = "list";
        }
    }

    async createLease() {
        await this.call("create_lease", [this.state.leaseForm]);
        this.state.view = "history";
    }

    openPropertyDetail() {
        this.state.page = "property";
        this.state.view = "unit";
    }

    openTenant() {
        this.state.page = "property";
        this.state.view = "tenant";
    }

    messageTenant() {
        this.state.newSubject = `Message for ${this.tenant().name}`;
        this.state.newBody = "";
        this.state.page = "messages";
        this.state.view = "compose";
    }

    openMaint(row) {
        this.state.selectedMaint = row.id;
        this.state.page = "maintenance";
        this.state.view = "detail";
    }

    async submitMaint() {
        await this.call("create_maintenance", [this.state.maintForm]);
        this.state.view = "list";
        this.notification.add("Request submitted.", { type: "success" });
    }

    async setMaintState(state) {
        await this.call("update_maintenance", [this.state.selectedMaint, state]);
    }

    async sendMaintMsg() {
        if (!this.state.maintMsg) {
            return;
        }
        await this.call("send_maint_message", [this.state.selectedMaint, this.state.maintMsg]);
        this.state.maintMsg = "";
    }

    async sendThread() {
        if (!this.state.msgBody) {
            return;
        }
        await this.call("send_message", [this.selectedThread().id, this.state.msgBody]);
        this.state.msgBody = "";
    }

    async startThread() {
        await this.call("start_thread", [this.state.newSubject, this.state.newBody]);
        this.state.view = "list";
        const threads = this.threads();
        this.state.selectedThread = threads[0]?.id;
    }

    async deleteThread() {
        await this.call("delete_thread", [this.selectedThread().id]);
    }

    openDoc(row) {
        this.state.selectedDoc = row.id;
        this.state.page = "documents";
        this.state.view = "viewer";
    }

    triggerDoc() {
        this.docInput.el?.click();
    }

    async onDocFile(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        const data = await this.readBase64(file);
        await this.call("upload_document", [{
            name: file.name,
            category: "property",
            file_data: data,
            mimetype: file.type,
            size: `${Math.round(file.size / 1024)} KB`,
        }]);
        this.notification.add("Document uploaded.", { type: "success" });
    }

    async downloadDoc() {
        const file = await this.orm.call("ot.portal", "get_document_file", [this.state.selectedDoc]);
        if (file?.data) {
            const binary = atob(file.data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            const url = URL.createObjectURL(new Blob([bytes], { type: file.mimetype }));
            const a = document.createElement("a");
            a.href = url;
            a.download = file.filename;
            a.click();
            URL.revokeObjectURL(url);
        } else if (file?.html) {
            const blob = new Blob([file.html], { type: "text/html" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = file.filename || "document.html";
            a.click();
            URL.revokeObjectURL(url);
        }
    }

    printDoc() {
        window.print();
    }

    async markNotes(action, id = false) {
        await this.call("mark_notifications", [action, id]);
    }

    async saveProfile() {
        await this.call("update_profile", [this.state.profileForm]);
        this.state.editingProfile = false;
        this.notification.add("Profile saved.", { type: "success" });
    }

    togglePref(field) {
        this.state.profileForm[field] = !this.state.profileForm[field];
        this.call("update_profile", [this.state.profileForm]);
    }

    readBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    logout() {
        window.location = "/web/session/logout";
    }
}

registry.category("actions").add("owner_tenant_management.portal", OtPortal);
