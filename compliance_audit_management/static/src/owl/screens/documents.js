import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const MODEL = "compliance.document";
const HISTORY_MODEL = "compliance.document.history";
const PAGE_SIZE = 10;

const DOC_FIELDS = [
    "name",
    "document_type",
    "issuing_authority",
    "requirement_id",
    "issue_date",
    "expiry_date",
    "renewal_reminder_days",
    "state",
    "property_id",
    "building_id",
    "area_id",
    "assigned_user_id",
    "attachment_ids",
];

const HISTORY_FIELDS = [
    "event_type",
    "previous_expiry_date",
    "new_expiry_date",
    "note",
    "user_id",
    "create_date",
];

const TYPE_LABELS = {
    license: "License",
    certificate: "Certificate",
    permit: "Permit",
    approval: "Approval",
    other: "Other",
};

const STATE_LABELS = {
    active: "Active",
    expiring_soon: "Expiring Soon",
    renewal_due: "Renewal Due",
    under_renewal: "Under Renewal",
    expired: "Expired",
    renewed: "Renewed",
    archived: "Archived",
};

const REMINDER_OPTIONS = [
    { value: "7", label: "7 days before expiry" },
    { value: "15", label: "15 days before expiry" },
    { value: "30", label: "30 days before expiry" },
    { value: "60", label: "60 days before expiry" },
    { value: "90", label: "90 days before expiry" },
];

function todayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
}

function m2oId(value) {
    if (Array.isArray(value)) {
        return value[0] || "";
    }
    return value || "";
}

function m2oName(value) {
    if (Array.isArray(value)) {
        return value[1] || "";
    }
    return value || "";
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            resolve(result.includes(",") ? result.split(",")[1] : result);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

export class ComplianceDocuments extends Component {
    static template = "compliance_audit_management.Documents";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.typeOptions = Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));
        this.reminderOptions = REMINDER_OPTIONS;
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            showCreate: false,
            showRenew: false,
            search: "",
            filter: "all",
            typeFilter: "",
            propertyFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { active: 0, expiring_soon: 0, renewal_due: 0, expired: 0 },
            record: null,
            history: [],
            attachments: [],
            isManager: false,
            form: this.emptyForm(),
            renewForm: { new_expiry_date: "", files: [] },
            pendingFiles: [],
            lookups: { requirements: [], properties: [], buildings: [], areas: [] },
        });
        onWillStart(async () => {
            const [isManager] = await Promise.all([
                user.hasGroup("compliance_audit_management.group_compliance_manager"),
            ]);
            this.state.isManager = isManager;
            const ctx = this.props.action?.context || {};
            if (ctx.ca_mode === "create" && isManager) {
                this.state.showCreate = true;
            } else if (ctx.ca_mode === "detail" && (ctx.ca_res_id || ctx.active_id)) {
                this.state.mode = "detail";
                this.state.resId = ctx.ca_res_id || ctx.active_id;
            }
            await this.loadLookups();
            await this.reload();
        });
    }

    emptyForm() {
        return {
            name: "",
            document_type: "certificate",
            issuing_authority: "",
            requirement_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            issue_date: "",
            expiry_date: "",
            renewal_reminder_days: "60",
        };
    }

    get canManage() {
        return this.state.isManager;
    }

    get emptyListHint() {
        return this.canManage
            ? "Add a license, certificate, or permit to start the register."
            : "Company compliance documents will appear here.";
    }

    get pageCount() {
        return Math.max(1, Math.ceil((this.state.total || 0) / this.pageSize));
    }

    get pageFrom() {
        if (!this.state.total) {
            return 0;
        }
        return (this.state.page - 1) * this.pageSize + 1;
    }

    get pageTo() {
        return Math.min(this.state.total, this.state.page * this.pageSize);
    }

    get filteredBuildings() {
        const propertyId = Number(this.state.form.property_id || 0);
        if (!propertyId) {
            return this.state.lookups.buildings;
        }
        return this.state.lookups.buildings.filter((row) => m2oId(row.property_id) === propertyId);
    }

    get filteredAreas() {
        const buildingId = Number(this.state.form.building_id || 0);
        if (!buildingId) {
            return this.state.lookups.areas;
        }
        return this.state.lookups.areas.filter((row) => m2oId(row.building_id) === buildingId);
    }

    m2oName = m2oName;
    todayIso = todayIso;

    typeLabel(value) {
        return TYPE_LABELS[value] || value || "—";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || value || "";
    }

    locationLabel(rec) {
        const parts = [
            this.m2oName(rec.property_id),
            this.m2oName(rec.building_id),
            this.m2oName(rec.area_id),
        ].filter(Boolean);
        return parts.join(" · ") || "—";
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    isExpiryUrgent(rec) {
        return ["expiring_soon", "renewal_due", "expired"].includes(rec.state);
    }

    buildDomain() {
        const domain = [];
        if (this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        if (this.state.typeFilter) {
            domain.push(["document_type", "=", this.state.typeFilter]);
        }
        if (this.state.propertyFilter) {
            domain.push(["property_id", "=", Number(this.state.propertyFilter)]);
        }
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", ["name", "ilike", search], ["issuing_authority", "ilike", search]);
        }
        return domain;
    }

    async loadLookups() {
        const [requirements, properties, buildings, areas] = await Promise.all([
            this.orm.searchRead("compliance.requirement", [["active", "=", true]], ["name"], {
                order: "name",
                limit: 200,
            }),
            this.orm.searchRead("compliance.property", [], ["name"], { order: "name", limit: 200 }),
            this.orm.searchRead("compliance.building", [], ["name", "property_id"], {
                order: "name",
                limit: 400,
            }),
            this.orm.searchRead("compliance.area", [], ["name", "building_id"], {
                order: "name",
                limit: 800,
            }),
        ]);
        this.state.lookups = { requirements, properties, buildings, areas };
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            if (this.state.mode === "detail" && this.state.resId) {
                await this.loadDetail(this.state.resId);
            } else {
                await this.loadList();
            }
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load documents.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadList() {
        const domain = this.buildDomain();
        const [total, records, kpis] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, DOC_FIELDS, {
                order: "expiry_date, name",
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
            }),
            this.orm.call(MODEL, "get_document_kpis", []),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = kpis;
    }

    async loadDetail(resId) {
        const [records, history] = await Promise.all([
            this.orm.searchRead(MODEL, [["id", "=", resId]], DOC_FIELDS, { limit: 1 }),
            this.orm.searchRead(HISTORY_MODEL, [["document_id", "=", resId]], HISTORY_FIELDS, {
                order: "create_date desc, id desc",
                limit: 50,
            }),
        ]);
        if (!records.length) {
            this.state.mode = "list";
            this.state.resId = null;
            await this.loadList();
            this.notification.add("Document not found.", { type: "warning" });
            return;
        }
        this.state.record = records[0];
        this.state.history = history;
        const attachmentIds = records[0].attachment_ids || [];
        this.state.attachments = attachmentIds.length
            ? await this.orm.searchRead("ir.attachment", [["id", "in", attachmentIds]], ["name", "mimetype"])
            : [];
        this.state.kpis = await this.orm.call(MODEL, "get_document_kpis", []);
    }

    async setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.state.showRenew = false;
        await this.reload();
    }

    openCreate() {
        if (!this.canManage) {
            return;
        }
        this.state.form = this.emptyForm();
        this.state.pendingFiles = [];
        this.state.showCreate = true;
    }

    closeCreate() {
        this.state.showCreate = false;
        this.state.busy = "";
    }

    openRenew() {
        if (!this.canManage || !this.state.record) {
            return;
        }
        this.state.renewForm = {
            new_expiry_date: "",
            files: [],
        };
        this.state.showRenew = true;
    }

    closeRenew() {
        this.state.showRenew = false;
        this.state.busy = "";
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onFilter(filter) {
        this.state.filter = filter;
        this.state.page = 1;
        this.reload();
    }

    onTypeFilter(ev) {
        this.state.typeFilter = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onPropertyFilter(ev) {
        this.state.propertyFilter = ev.target.value;
        this.state.page = 1;
        this.reload();
    }

    onPage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.pageCount) {
            return;
        }
        this.state.page = next;
        this.reload();
    }

    onPropertyChange(ev) {
        this.state.form.property_id = ev.target.value;
        this.state.form.building_id = "";
        this.state.form.area_id = "";
    }

    onBuildingChange(ev) {
        this.state.form.building_id = ev.target.value;
        this.state.form.area_id = "";
    }

    onCreateFiles(ev) {
        this.state.pendingFiles = Array.from(ev.target.files || []);
    }

    onRenewFiles(ev) {
        this.state.renewForm.files = Array.from(ev.target.files || []);
    }

    async createAttachments(files, resId) {
        const ids = [];
        for (const file of files) {
            const datas = await fileToBase64(file);
            const created = await this.orm.create("ir.attachment", [
                {
                    name: file.name,
                    datas,
                    res_model: MODEL,
                    res_id: resId,
                    mimetype: file.type || "application/octet-stream",
                },
            ]);
            ids.push(Array.isArray(created) ? created[0] : created);
        }
        return ids;
    }

    async createDocument() {
        if (!this.canManage) {
            return;
        }
        const form = this.state.form;
        if (!form.name.trim() || !form.document_type || !form.expiry_date || !form.property_id) {
            this.notification.add("Name, type, property, and expiry date are required.", {
                type: "danger",
            });
            return;
        }
        if (!this.state.pendingFiles.length) {
            this.notification.add("Upload at least one document file.", { type: "danger" });
            return;
        }
        this.state.busy = "Adding document…";
        try {
            const vals = {
                name: form.name.trim(),
                document_type: form.document_type,
                issuing_authority: form.issuing_authority || false,
                expiry_date: form.expiry_date,
                renewal_reminder_days: form.renewal_reminder_days || "60",
                property_id: Number(form.property_id),
            };
            if (form.requirement_id) {
                vals.requirement_id = Number(form.requirement_id);
            }
            if (form.building_id) {
                vals.building_id = Number(form.building_id);
            }
            if (form.area_id) {
                vals.area_id = Number(form.area_id);
            }
            if (form.issue_date) {
                vals.issue_date = form.issue_date;
            }
            const created = await this.orm.create(MODEL, [vals]);
            const resId = Array.isArray(created) ? created[0] : created;
            const attachmentIds = await this.createAttachments(this.state.pendingFiles, resId);
            if (attachmentIds.length) {
                await this.orm.write(MODEL, [resId], { attachment_ids: [[6, 0, attachmentIds]] });
            }
            this.notification.add("Document added.", { type: "success" });
            this.state.showCreate = false;
            await this.setMode("detail", resId);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Create failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async runAction(method) {
        if (!this.canManage || !this.state.resId) {
            return;
        }
        this.state.busy = "Updating…";
        try {
            await this.orm.call(MODEL, method, [[this.state.resId]]);
            this.notification.add("Document updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async confirmRenew() {
        if (!this.canManage || !this.state.resId) {
            return;
        }
        const newExpiry = this.state.renewForm.new_expiry_date;
        if (!newExpiry) {
            this.notification.add("New expiry date is required.", { type: "danger" });
            return;
        }
        this.state.busy = "Recording renewal…";
        try {
            if (this.state.record.state !== "under_renewal") {
                await this.orm.call(MODEL, "action_start_renewal", [[this.state.resId]]);
            }
            let attachmentIds = [];
            if (this.state.renewForm.files.length) {
                attachmentIds = await this.createAttachments(this.state.renewForm.files, this.state.resId);
            }
            await this.orm.call(MODEL, "action_mark_renewed", [[this.state.resId]], {
                new_expiry_date: newExpiry,
                attachment_ids: attachmentIds,
            });
            this.notification.add("Document renewed.", { type: "success" });
            this.state.showRenew = false;
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Renewal failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }
}

registry.category("actions").add("compliance_audit_management.action_documents", ComplianceDocuments);
