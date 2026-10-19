/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "overview", label: "Overview", icon: "fa-th-large" },
    { id: "directory", label: "Resident Directory", icon: "fa-users" },
    { id: "onboarding", label: "Digital Onboarding", icon: "fa-user-plus" },
    { id: "kyc", label: "KYC / Documents", icon: "fa-shield" },
    { id: "household", label: "Household Members", icon: "fa-home" },
    { id: "profile", label: "Resident Profile", icon: "fa-id-card-o" },
    { id: "move", label: "Move-In / Move-Out", icon: "fa-exchange" },
    { id: "emergency", label: "Emergency Contacts", icon: "fa-phone" },
    { id: "communication", label: "Communication", icon: "fa-commenting-o" },
    { id: "status", label: "Resident Status", icon: "fa-flag-o" },
    { id: "history", label: "Resident History", icon: "fa-clock-o" },
];

const PAGE = 10;

export class ResidentPortal extends Component {
    static template = "resident_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.navItems = NAV;
        this.importInput = useRef("importInput");
        this.kycInput = useRef("kycInput");
        this.commFileInput = useRef("commFileInput");
        this.state = useState({
            page: "overview",
            loading: true,
            data: {},
            search: "",
            dirSearch: "",
            dirPage: 1,
            dirStatus: "all",
            view: "list",
            selectedId: false,
            selectedKyc: false,
            selectedMove: false,
            selectedComm: false,
            selectedHist: false,
            profileTab: "overview",
            moveTab: "in",
            kycFile: false,
            form: this.emptyForm(),
            memberForm: { id: "", resident_id: "", name: "", relation: "Spouse", email: "", phone: "", status: "active" },
            emForm: { resident_id: "", name: "", relation: "", phone: "", email: "", priority: "primary" },
            commForm: { subject: "", body: "", audience: "All Residents", audience_type: "all", audience_id: "", push: true, email: true, sms: false, schedule: false, attachment: "", attachment_data: "", attachment_mimetype: "" },
            statusForm: { resident_id: "", status: "", reason: "", notes: "", date: "" },
            saving: false,
        });
        onWillStart(() => this.load());
    }

    emptyForm() {
        return {
            id: false,
            first_name: "",
            last_name: "",
            preferred_name: "",
            dob: "",
            gender: "",
            marital_status: "",
            nationality: "",
            resident_type: "Primary Tenant",
            mobile: "",
            email: "",
            alt_phone: "",
            street: "",
            city: "",
            state_name: "",
            zip: "",
            country: "",
            unit_id: "",
            building_id: "",
            move_in: "",
            lease_term: "12 Months",
            id_type: "Passport",
            id_number: "",
            em_name: "",
            em_relation: "",
            em_phone: "",
            em_email: "",
        };
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("resident.portal", "get_dashboard_data", []);
            const rows = this.residents();
            if (!this.state.selectedId && rows.length) {
                this.state.selectedId = rows[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load residents.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async call(method, args = []) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("resident.portal", method, args);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        this.state.view = "list";
        this.state.dirPage = 1;
        if (id === "directory") {
            this.state.view = "list";
        }
        if (id === "communication") {
            this.state.view = "list";
        }
    }

    residents() {
        return this.state.data.residents || [];
    }

    selected() {
        return this.residents().find((r) => r.id === this.state.selectedId) || this.residents()[0] || {};
    }

    kycSelected() {
        return (this.state.data.kycs || []).find((r) => r.id === this.state.selectedKyc) || {};
    }

    moveSelected() {
        return (this.state.data.moves || []).find((r) => r.id === this.state.selectedMove) || {};
    }

    commSelected() {
        return (this.state.data.comms || []).find((r) => r.id === this.state.selectedComm) || {};
    }

    histSelected() {
        return (this.state.data.history || []).find((r) => r.id === this.state.selectedHist) || {};
    }

    filteredResidents() {
        const q = (this.state.dirSearch || this.state.search || "").toLowerCase();
        let rows = this.residents();
        if (this.state.dirStatus !== "all") {
            rows = rows.filter((r) => r.status === this.state.dirStatus);
        }
        if (q) {
            rows = rows.filter((r) => `${r.name} ${r.code} ${r.email} ${r.mobile} ${r.unit}`.toLowerCase().includes(q));
        }
        return rows;
    }

    paged(rows, page) {
        const start = (page - 1) * PAGE;
        return rows.slice(start, start + PAGE);
    }

    dirRows() {
        return this.paged(this.filteredResidents(), this.state.dirPage);
    }

    openResident(row, page = "profile") {
        this.state.selectedId = row.id;
        this.state.page = page;
        this.state.profileTab = "overview";
        this.state.view = "detail";
    }

    openAdd() {
        this.state.form = this.emptyForm();
        this.state.page = "directory";
        this.state.view = "add";
    }

    openEdit(row) {
        const r = row || this.selected();
        this.state.selectedId = r.id;
        this.state.form = {
            ...this.emptyForm(),
            id: r.id,
            first_name: r.first_name || "",
            last_name: r.last_name || "",
            preferred_name: r.preferred_name || "",
            dob: r.dob || "",
            gender: r.gender || "",
            marital_status: r.marital_status || "",
            nationality: r.nationality || "",
            resident_type: r.resident_type || "Primary Tenant",
            mobile: r.mobile || "",
            email: r.email || "",
            alt_phone: r.alt_phone || "",
            street: r.street || "",
            city: r.city || "",
            state_name: r.state_name || "",
            zip: r.zip || "",
            country: r.country || "",
            unit_id: r.unit_id || "",
            building_id: r.building_id || "",
            move_in: r.move_in_raw || "",
            lease_term: r.lease_term || "12 Months",
            id_type: r.id_type || "Passport",
            id_number: r.id_number || "",
        };
        this.state.page = "directory";
        this.state.view = "add";
    }

    async createResident(draft) {
        if (this.state.form.id) {
            await this.call("update_resident", [this.state.form]);
            this.state.page = "profile";
            this.state.view = "detail";
            this.notification.add("Resident updated.", { type: "success" });
            return;
        }
        await this.call("create_resident", [{ ...this.state.form, draft: !!draft }]);
        this.state.view = "list";
        this.notification.add(draft ? "Draft saved." : "Resident created.", { type: "success" });
    }

    async deleteResident(row) {
        const person = row || { id: this.state.form.id, name: `${this.state.form.first_name || ""} ${this.state.form.last_name || ""}`.trim() };
        if (!person.id) {
            return;
        }
        if (!window.confirm(`Delete ${person.name || "this resident"}?`)) {
            return;
        }
        try {
            this.state.data = await this.orm.call("resident.portal", "delete_resident", [person.id]);
            this.state.view = "list";
            this.state.page = "directory";
            this.state.selectedId = false;
            this.notification.add("Resident deleted.", { type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || "Could not delete the resident.", { type: "danger" });
        }
    }

    async exportResidents() {
        try {
            const file = await this.orm.call("resident.portal", "export_residents", []);
            this.downloadText(file.filename || "residents.csv", file.csv || "", "text/csv");
        } catch (error) {
            this.notification.add(error?.data?.message || "Export failed.", { type: "danger" });
        }
    }

    triggerImport() {
        this.importInput.el?.click();
    }

    async onImportFile(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        const text = await file.text();
        await this.call("import_residents", [text]);
        this.notification.add("Residents imported.", { type: "success" });
    }

    async createOnboard() {
        this.openAdd();
    }

    onboardSteps() {
        const stage = this.selected().onboarding_stage || "submitted";
        const steps = [
            { label: "Personal Information", key: "submitted" },
            { label: "Residency", key: "submitted" },
            { label: "Documents", key: "docs" },
            { label: "KYC", key: "kyc" },
            { label: "Review", key: "review" },
            { label: "Approval", key: "approved" },
        ];
        const order = ["submitted", "docs", "kyc", "review", "approved"];
        const current = stage === "rejected" ? order.indexOf("review") : order.indexOf(stage);
        return steps.map((step) => {
            const at = order.indexOf(step.key);
            let state = "";
            if (stage === "rejected" && step.key === "approved") {
                state = "is-bad";
            } else if (at < current) {
                state = "is-done";
            } else if (at === current) {
                state = "is-on";
            }
            return { label: step.label, state };
        });
    }

    async onboard(action) {
        const resident = this.selected();
        if (!resident.id) {
            this.notification.add("Select an application first.", { type: "warning" });
            return;
        }
        const before = this.state.data;
        await this.call("onboard_action", [resident.id, action]);
        if (this.state.data === before) {
            return;
        }
        const labels = { approve: "approved", reject: "rejected", changes: "sent back for documents", start: "started" };
        this.notification.add(`${resident.name} is ${labels[action] || "updated"}. Status: ${this.selected().onboarding_label}.`, { type: "success" });
    }

    async openKyc(row) {
        this.state.selectedKyc = row.id;
        this.state.page = "kyc";
        this.state.view = "verify";
        this.state.kycFile = false;
        if (row.has_file) {
            try {
                this.state.kycFile = await this.orm.call("resident.portal", "get_kyc_file", [row.id]);
            } catch {
                this.state.kycFile = false;
            }
        }
    }

    triggerKycUpload() {
        this.kycInput.el?.click();
    }

    async onKycFile(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        const residentId = this.selected().id;
        if (!residentId) {
            this.notification.add("Select a resident first.", { type: "warning" });
            return;
        }
        const data = await this.readBase64(file);
        await this.call("upload_kyc_document", [{
            resident_id: residentId,
            name: file.name,
            file_name: file.name,
            document_type: "Uploaded Document",
            file_data: data,
            mimetype: file.type,
            size: file.size,
        }]);
        this.notification.add("Document uploaded.", { type: "success" });
    }

    async reviewKyc(action) {
        const row = this.kycSelected();
        await this.call("review_kyc", [row.id, action, {
            identity_match: row.identity_match,
            document_readable: row.document_readable,
            document_valid: row.document_valid,
            not_expired: row.not_expired,
            information_match: row.information_match,
        }]);
        this.state.view = "list";
        this.notification.add("KYC review saved.", { type: "success" });
    }

    toggleCheck(field) {
        const row = (this.state.data.kycs || []).find((r) => r.id === this.state.selectedKyc);
        if (row) {
            row[field] = !row[field];
        }
    }

    openHousehold(row) {
        this.state.selectedId = row.resident_id || row.id;
        this.state.page = "household";
        this.state.view = "detail";
    }

    openMemberEdit(row) {
        this.state.memberForm = {
            id: row.id,
            resident_id: row.resident_id,
            name: row.name,
            relation: row.relation,
            email: row.email,
            phone: row.phone,
            status: row.status,
        };
        this.state.page = "household";
        this.state.view = "add";
    }

    openMemberAdd() {
        this.state.memberForm = { id: "", resident_id: this.selected().id || "", name: "", relation: "Spouse", email: "", phone: "", status: "active" };
        this.state.view = "add";
    }

    async addMember() {
        await this.call("add_household_member", [this.state.memberForm]);
        this.state.view = "list";
        this.notification.add(this.state.memberForm.id ? "Member updated." : "Member added.", { type: "success" });
    }

    messageHousehold() {
        const r = this.selected();
        this.state.commForm = {
            subject: `Message for ${r.name || "resident"}`,
            body: "",
            audience: r.name || "Resident",
            audience_type: "resident",
            audience_id: r.id,
            push: true,
            email: true,
            sms: false,
            schedule: false,
            attachment: "",
            attachment_data: "",
            attachment_mimetype: "",
        };
        this.state.page = "communication";
        this.state.view = "compose";
    }

    async addEmergency() {
        await this.call("add_emergency_contact", [this.state.emForm]);
        this.state.view = "list";
        this.notification.add("Emergency contact saved.", { type: "success" });
    }

    openMove(row) {
        this.state.selectedMove = row.id;
        this.state.page = "move";
        this.state.view = "detail";
        this.state.moveTab = row.move_type || "in";
    }

    async toggleItem(id) {
        await this.call("toggle_checklist", [id]);
    }

    async doMove(action) {
        await this.call("move_action", [this.state.selectedMove, action]);
        if (action === "clearance") {
            try {
                const file = await this.orm.call("resident.portal", "get_clearance_file", [this.state.selectedMove]);
                if (file) {
                    this.downloadBase64(file.filename, file.data, file.mimetype);
                }
            } catch (error) {
                this.notification.add(error?.data?.message || "Could not download clearance.", { type: "danger" });
            }
            this.notification.add("Clearance certificate generated.", { type: "success" });
        }
        if (action === "complete") {
            this.state.view = "list";
        }
    }

    openComm(row) {
        this.state.selectedComm = row.id;
        this.state.page = "communication";
        this.state.view = "detail";
    }

    composeComm() {
        this.state.commForm = { subject: "", body: "", audience: "All Residents", audience_type: "all", audience_id: "", push: true, email: true, sms: false, schedule: false, attachment: "", attachment_data: "", attachment_mimetype: "" };
        this.state.page = "communication";
        this.state.view = "compose";
    }

    setAudience(kind) {
        this.state.commForm.audience_type = kind;
        if (kind === "all") {
            this.state.commForm.audience = "All Residents";
            this.state.commForm.audience_id = "";
        }
    }

    triggerCommFile() {
        this.commFileInput.el?.click();
    }

    async onCommFile(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        this.state.commForm.attachment = file.name;
        this.state.commForm.attachment_mimetype = file.type;
        this.state.commForm.attachment_data = await this.readBase64(file);
    }

    async sendComm(schedule) {
        await this.call("send_communication", [{ ...this.state.commForm, schedule: !!schedule }]);
        this.state.view = "list";
        this.notification.add(schedule ? "Saved as draft/schedule." : "Communication sent.", { type: "success" });
    }

    openStatusChange(row) {
        if (!row || !row.id) {
            this.notification.add("Select a resident first.", { title: "Resident Status", type: "warning" });
            return;
        }
        this.state.selectedId = row.id;
        this.state.statusForm = {
            resident_id: row.id,
            status: row.status || "",
            reason: row.status_reason || "",
            notes: "",
            date: "",
        };
        this.state.page = "status";
        this.state.view = "change";
    }

    async saveStatus() {
        const form = this.state.statusForm;
        if (!form.resident_id || !form.status) {
            this.notification.add("Choose a new status.", { title: "Resident Status", type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("resident.portal", "update_resident_status", [
                form.resident_id,
                form.status,
                form.reason,
                form.notes,
            ]);
            this.state.view = "list";
            this.notification.add("Status updated.", { title: "Resident Status", type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update the status.", {
                title: "Resident Status",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    openHistory(row) {
        this.state.selectedHist = row.id;
        this.state.page = "history";
        this.state.view = "activity";
    }

    openLifecycle(row) {
        this.state.selectedId = row.resident_id || row.id;
        this.state.page = "history";
        this.state.view = "lifecycle";
    }

    kpis() {
        return this.state.data.kpis || {};
    }

    onboardingColumns() {
        return this.state.data.onboarding_columns || [];
    }

    pipeline() {
        return this.state.data.pipeline || {};
    }

    badge(status) {
        return {
            active: "ok",
            pending: "warn",
            verification: "info",
            notice: "warn",
            moved_out: "muted",
            suspended: "bad",
            inactive: "muted",
            verified: "ok",
            review: "info",
            rejected: "bad",
            expiring: "warn",
            delivered: "ok",
            scheduled: "info",
            partial: "bad",
            failed: "bad",
            ready: "ok",
            progress: "info",
            done: "ok",
            approved: "ok",
            submitted: "info",
            docs: "warn",
            kyc: "info",
        }[status] || "muted";
    }

    moves(type) {
        return (this.state.data.moves || []).filter((m) => m.move_type === (type || this.state.moveTab));
    }

    householdOfSelected() {
        const id = this.selected().id;
        return (this.state.data.members || []).filter((m) => m.resident_id === id);
    }

    logout() {
        window.location = "/web/session/logout";
    }

    pages(count) {
        return Math.max(1, Math.ceil(count / PAGE));
    }

    kycPreviewSrc() {
        const file = this.state.kycFile;
        if (!file?.data) {
            return "";
        }
        return `data:${file.mimetype || "application/octet-stream"};base64,${file.data}`;
    }

    isImage(mimetype) {
        return (mimetype || "").startsWith("image/");
    }

    isPdf(mimetype) {
        return (mimetype || "") === "application/pdf";
    }

    downloadKyc() {
        const file = this.state.kycFile;
        if (file) {
            this.downloadBase64(file.filename, file.data, file.mimetype);
        }
    }

    readBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    downloadText(name, text, mime) {
        const blob = new Blob([text], { type: mime || "text/plain" });
        this._saveBlob(name, blob);
    }

    downloadBase64(name, data, mime) {
        const binary = atob(data || "");
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        this._saveBlob(name, new Blob([bytes], { type: mime || "application/octet-stream" }));
    }

    _saveBlob(name, blob) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = name;
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("resident_management.portal", ResidentPortal);
