import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const MODEL = "compliance.regulatory.report";
const PAGE_SIZE = 10;

const REPORT_FIELDS = [
    "name",
    "reference",
    "regulatory_authority",
    "requirement_id",
    "reporting_period",
    "description",
    "owner_id",
    "deadline",
    "priority",
    "submission_date",
    "submission_reference",
    "state",
    "is_overdue",
    "is_due",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
    "attachment_ids",
    "acknowledgement_ids",
];

const STATE_LABELS = {
    draft: "Draft",
    in_preparation: "In Preparation",
    submitted: "Submitted",
};

const PRIORITY_OPTIONS = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "critical", label: "Critical" },
];

function todayIso() {
    return localKeyFromDate(new Date());
}

function localKeyFromDate(date) {
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
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

export class ComplianceRegulatory extends Component {
    static template = "compliance_audit_management.Regulatory";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.priorityOptions = PRIORITY_OPTIONS;
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            showCreate: false,
            search: "",
            filter: "all",
            page: 1,
            total: 0,
            records: [],
            kpis: { due_soon: 0, overdue: 0, in_preparation: 0, submitted: 0 },
            record: null,
            attachments: [],
            acknowledgements: [],
            pendingFiles: [],
            pendingAcks: [],
            detailForm: this.emptyDetailForm(),
            isManager: false,
            form: this.emptyForm(),
            lookups: { properties: [], requirements: [], users: [] },
        });
        onWillStart(async () => {
            this.state.isManager = await user.hasGroup(
                "compliance_audit_management.group_compliance_manager"
            );
            const ctx = this.props.action?.context || {};
            if (ctx.ca_mode === "create" && this.state.isManager) {
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
            regulatory_authority: "",
            reporting_period: "",
            deadline: todayIso(),
            priority: "medium",
            owner_id: String(user.userId || ""),
            requirement_id: "",
            property_id: "",
            description: "",
        };
    }

    emptyDetailForm() {
        return {
            submission_reference: "",
            owner_id: "",
            deadline: "",
            priority: "medium",
            description: "",
        };
    }

    get canManage() {
        return this.state.isManager;
    }

    get detailEditable() {
        return this.canManage && this.state.record && this.state.record.state !== "submitted";
    }

    get emptyListHint() {
        return this.canManage
            ? "Create a regulatory submission to track authority deadlines."
            : "Company regulatory submissions will appear here.";
    }

    get pageCount() {
        return Math.max(1, Math.ceil((this.state.total || 0) / this.pageSize));
    }

    get pageFrom() {
        return this.state.total ? (this.state.page - 1) * this.pageSize + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.total, this.state.page * this.pageSize);
    }

    m2oName = m2oName;

    stateLabel(value) {
        return STATE_LABELS[value] || value || "";
    }

    priorityLabel(value) {
        const match = PRIORITY_OPTIONS.find((opt) => opt.value === value);
        return match?.label || value || "—";
    }

    displayState(rec) {
        if (rec.is_overdue && rec.state !== "submitted") {
            return "overdue";
        }
        return rec.state;
    }

    displayStateLabel(rec) {
        if (rec.is_overdue && rec.state !== "submitted") {
            return "Overdue";
        }
        return this.stateLabel(rec.state);
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

    buildDomain() {
        const domain = [];
        const filter = this.state.filter;
        const today = todayIso();
        if (filter === "overdue") {
            domain.push(["state", "!=", "submitted"], ["deadline", "<", today]);
        } else if (filter === "due_soon") {
            const soon = new Date();
            soon.setDate(soon.getDate() + 30);
            const soonIso = localKeyFromDate(soon);
            domain.push(
                ["state", "!=", "submitted"],
                ["deadline", ">=", today],
                ["deadline", "<=", soonIso]
            );
        } else if (filter !== "all") {
            domain.push(["state", "=", filter]);
        }
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push(
                "|",
                "|",
                "|",
                ["name", "ilike", search],
                ["reference", "ilike", search],
                ["regulatory_authority", "ilike", search],
                ["reporting_period", "ilike", search]
            );
        }
        return domain;
    }

    async loadLookups() {
        const [properties, requirements, users] = await Promise.all([
            this.orm.searchRead("compliance.property", [], ["name"], { order: "name", limit: 200 }),
            this.orm.searchRead("compliance.requirement", [], ["name", "code"], {
                order: "name",
                limit: 200,
            }),
            this.orm.searchRead("res.users", [["share", "=", false]], ["name"], {
                order: "name",
                limit: 200,
            }),
        ]);
        this.state.lookups = { properties, requirements, users };
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
            this.state.error =
                error?.data?.message || error?.message || "Could not load regulatory reports.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadList() {
        const domain = this.buildDomain();
        const [total, records, kpis] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, REPORT_FIELDS, {
                order: "deadline asc, id desc",
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
            }),
            this.orm.call(MODEL, "get_regulatory_kpis", []),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = kpis;
    }

    async loadDetail(resId) {
        const records = await this.orm.searchRead(MODEL, [["id", "=", resId]], REPORT_FIELDS, {
            limit: 1,
        });
        if (!records.length) {
            this.state.mode = "list";
            this.state.resId = null;
            await this.loadList();
            this.notification.add("Record not found.", { type: "warning" });
            return;
        }
        const record = records[0];
        this.state.record = record;
        this.state.detailForm = {
            submission_reference: record.submission_reference || "",
            owner_id: String(m2oId(record.owner_id) || ""),
            deadline: record.deadline || "",
            priority: record.priority || "medium",
            description: record.description || "",
        };
        const attachIds = record.attachment_ids || [];
        const ackIds = record.acknowledgement_ids || [];
        const [attachments, acknowledgements] = await Promise.all([
            attachIds.length
                ? this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype"])
                : [],
            ackIds.length
                ? this.orm.searchRead("ir.attachment", [["id", "in", ackIds]], ["name", "mimetype"])
                : [],
        ]);
        this.state.attachments = attachments;
        this.state.acknowledgements = acknowledgements;
        this.state.pendingFiles = [];
        this.state.pendingAcks = [];
        this.state.kpis = await this.orm.call(MODEL, "get_regulatory_kpis", []);
    }

    async setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
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

    onPage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.pageCount) {
            return;
        }
        this.state.page = next;
        this.reload();
    }

    onCreateFiles(ev) {
        this.state.pendingFiles = Array.from(ev.target.files || []);
    }

    onAckFiles(ev) {
        this.state.pendingAcks = Array.from(ev.target.files || []);
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

    async createReport() {
        if (!this.canManage) {
            return;
        }
        const form = this.state.form;
        if (
            !form.name.trim() ||
            !form.regulatory_authority.trim() ||
            !form.reporting_period.trim() ||
            !form.deadline
        ) {
            this.notification.add("Name, authority, reporting period, and deadline are required.", {
                type: "danger",
            });
            return;
        }
        this.state.busy = "Creating…";
        try {
            const vals = {
                name: form.name.trim(),
                regulatory_authority: form.regulatory_authority.trim(),
                reporting_period: form.reporting_period.trim(),
                deadline: form.deadline,
                priority: form.priority || "medium",
                description: form.description || false,
            };
            if (form.owner_id) {
                vals.owner_id = Number(form.owner_id);
            }
            if (form.requirement_id) {
                vals.requirement_id = Number(form.requirement_id);
            }
            if (form.property_id) {
                vals.property_id = Number(form.property_id);
            }
            const created = await this.orm.create(MODEL, [vals]);
            const resId = Array.isArray(created) ? created[0] : created;
            if (this.state.pendingFiles.length) {
                const attachmentIds = await this.createAttachments(this.state.pendingFiles, resId);
                if (attachmentIds.length) {
                    await this.orm.write(MODEL, [resId], {
                        attachment_ids: [[6, 0, attachmentIds]],
                    });
                }
            }
            this.notification.add("Regulatory report created.", { type: "success" });
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

    async saveDetail() {
        if (!this.detailEditable || !this.state.resId) {
            return;
        }
        this.state.busy = "Saving…";
        try {
            const form = this.state.detailForm;
            const vals = {
                submission_reference: form.submission_reference || false,
                deadline: form.deadline || false,
                priority: form.priority || "medium",
                description: form.description || false,
                owner_id: form.owner_id ? Number(form.owner_id) : false,
            };
            await this.orm.write(MODEL, [this.state.resId], vals);
            if (this.state.pendingFiles.length) {
                const newIds = await this.createAttachments(this.state.pendingFiles, this.state.resId);
                const merged = [...(this.state.record.attachment_ids || []), ...newIds];
                await this.orm.write(MODEL, [this.state.resId], {
                    attachment_ids: [[6, 0, merged]],
                });
            }
            if (this.state.pendingAcks.length) {
                const newIds = await this.createAttachments(this.state.pendingAcks, this.state.resId);
                const merged = [...(this.state.record.acknowledgement_ids || []), ...newIds];
                await this.orm.write(MODEL, [this.state.resId], {
                    acknowledgement_ids: [[6, 0, merged]],
                });
            }
            this.notification.add("Report updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Save failed.", {
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
            this.notification.add("Report updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }
}

registry
    .category("actions")
    .add("compliance_audit_management.action_regulatory", ComplianceRegulatory);
