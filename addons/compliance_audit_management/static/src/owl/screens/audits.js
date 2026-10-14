import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const MODEL = "compliance.audit";
const LINE_MODEL = "compliance.audit.line";
const FINDING_MODEL = "compliance.finding";
const PAGE_SIZE = 10;

const AUDIT_FIELDS = [
    "name",
    "reference",
    "kind",
    "audit_type",
    "inspection_type",
    "date_planned",
    "scope",
    "template_id",
    "notes",
    "recommendations",
    "outcome",
    "state",
    "is_overdue",
    "finding_count",
    "line_count",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
];

const LINE_FIELDS = ["name", "sequence", "required", "result", "remarks", "audit_id"];
const FINDING_FIELDS = [
    "name",
    "severity",
    "state",
    "description",
    "audit_id",
    "audit_line_id",
    "non_compliance_id",
];

const STATE_LABELS = {
    scheduled: "Scheduled",
    in_progress: "In Progress",
    pending_review: "Pending Review",
    completed: "Completed",
    failed: "Failed",
    closed: "Closed",
};

const AUDIT_TYPE_LABELS = {
    internal: "Internal Audit",
    external: "External Audit",
    regulatory: "Regulatory Audit",
    statutory: "Statutory Audit",
    compliance: "Compliance Audit",
    follow_up: "Follow-up Audit",
};

const INSPECTION_TYPE_LABELS = {
    regulatory: "Regulatory Inspection",
    statutory: "Statutory Inspection",
    safety: "Safety Inspection",
    equipment: "Equipment Inspection",
    building: "Building Inspection",
    environmental: "Environmental Inspection",
};

const RESULT_OPTIONS = [
    { value: "compliant", label: "Compliant" },
    { value: "non_compliant", label: "Non-Compliant" },
    { value: "na", label: "Not Applicable" },
];

const SEVERITY_OPTIONS = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "critical", label: "Critical" },
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

export class ComplianceAudits extends Component {
    static template = "compliance_audit_management.Audits";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.resultOptions = RESULT_OPTIONS;
        this.severityOptions = SEVERITY_OPTIONS;
        this.auditTypeOptions = Object.entries(AUDIT_TYPE_LABELS).map(([value, label]) => ({
            value,
            label,
        }));
        this.inspectionTypeOptions = Object.entries(INSPECTION_TYPE_LABELS).map(([value, label]) => ({
            value,
            label,
        }));
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            showCreate: false,
            showFinding: false,
            search: "",
            filter: "all",
            kindFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { scheduled_month: 0, in_progress: 0, overdue: 0, completion_rate: 0 },
            record: null,
            lines: [],
            findings: [],
            lineResults: {},
            lineRemarks: {},
            isManager: false,
            form: this.emptyForm(),
            findingForm: this.emptyFindingForm(),
            previewItems: [],
            lookups: { templates: [], properties: [], buildings: [], areas: [], users: [] },
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
            kind: "audit",
            audit_type: "internal",
            inspection_type: "safety",
            date_planned: todayIso(),
            template_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            assigned_user_id: String(user.userId || ""),
            scope: "",
            notes: "",
        };
    }

    emptyFindingForm() {
        return {
            name: "",
            severity: "medium",
            description: "",
            audit_line_id: "",
        };
    }

    get canManage() {
        return this.state.isManager;
    }

    get emptyListHint() {
        return this.canManage
            ? "Create an audit or inspection to start planning."
            : "Company audits and inspections will appear here.";
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

    stateLabel(value) {
        return STATE_LABELS[value] || value || "";
    }

    displayState(rec) {
        if (rec.is_overdue && !["completed", "closed", "failed"].includes(rec.state)) {
            return "overdue";
        }
        return rec.state;
    }

    displayStateLabel(rec) {
        if (rec.is_overdue && !["completed", "closed", "failed"].includes(rec.state)) {
            return "Overdue";
        }
        return this.stateLabel(rec.state);
    }

    kindLabel(rec) {
        return rec.kind === "inspection" ? "INSPECTION" : "AUDIT";
    }

    typeLabel(rec) {
        if (rec.kind === "inspection") {
            return INSPECTION_TYPE_LABELS[rec.inspection_type] || "—";
        }
        return AUDIT_TYPE_LABELS[rec.audit_type] || "—";
    }

    locationLabel(rec) {
        return (
            [this.m2oName(rec.property_id), this.m2oName(rec.building_id), this.m2oName(rec.area_id)]
                .filter(Boolean)
                .join(" · ") || "—"
        );
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
        if (filter === "overdue") {
            domain.push(
                ["state", "in", ["scheduled", "in_progress", "pending_review"]],
                ["date_planned", "<", todayIso()]
            );
        } else if (filter === "audits") {
            domain.push(["kind", "=", "audit"]);
        } else if (filter === "inspections") {
            domain.push(["kind", "=", "inspection"]);
        } else if (filter !== "all") {
            domain.push(["state", "=", filter]);
        }
        if (this.state.kindFilter) {
            domain.push(["kind", "=", this.state.kindFilter]);
        }
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", "|", ["name", "ilike", search], ["reference", "ilike", search], [
                "scope",
                "ilike",
                search,
            ]);
        }
        return domain;
    }

    async loadLookups() {
        const [templates, properties, buildings, areas, users] = await Promise.all([
            this.orm.searchRead(
                "compliance.checklist.template",
                [["active", "=", true]],
                ["name", "item_count"],
                { order: "name", limit: 200 }
            ),
            this.orm.searchRead("compliance.property", [], ["name"], { order: "name", limit: 200 }),
            this.orm.searchRead("compliance.building", [], ["name", "property_id"], {
                order: "name",
                limit: 400,
            }),
            this.orm.searchRead("compliance.area", [], ["name", "building_id"], {
                order: "name",
                limit: 800,
            }),
            this.orm.searchRead("res.users", [["share", "=", false]], ["name"], {
                order: "name",
                limit: 200,
            }),
        ]);
        this.state.lookups = { templates, properties, buildings, areas, users };
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
            this.state.error = error?.data?.message || error?.message || "Could not load audits.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadList() {
        const domain = this.buildDomain();
        const [total, records, kpis] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, AUDIT_FIELDS, {
                order: "date_planned desc, id desc",
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
            }),
            this.orm.call(MODEL, "get_audit_kpis", []),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = kpis;
    }

    async loadDetail(resId) {
        const [records, lines, findings] = await Promise.all([
            this.orm.searchRead(MODEL, [["id", "=", resId]], AUDIT_FIELDS, { limit: 1 }),
            this.orm.searchRead(LINE_MODEL, [["audit_id", "=", resId]], LINE_FIELDS, {
                order: "sequence, id",
            }),
            this.orm.searchRead(FINDING_MODEL, [["audit_id", "=", resId]], FINDING_FIELDS, {
                order: "id desc",
            }),
        ]);
        if (!records.length) {
            this.state.mode = "list";
            this.state.resId = null;
            await this.loadList();
            this.notification.add("Record not found.", { type: "warning" });
            return;
        }
        this.state.record = records[0];
        this.state.lines = lines;
        this.state.findings = findings;
        const lineResults = {};
        const lineRemarks = {};
        for (const line of lines) {
            lineResults[line.id] = line.result || "";
            lineRemarks[line.id] = line.remarks || "";
        }
        this.state.lineResults = lineResults;
        this.state.lineRemarks = lineRemarks;
        this.state.kpis = await this.orm.call(MODEL, "get_audit_kpis", []);
    }

    async setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.state.showFinding = false;
        await this.reload();
    }

    openCreate() {
        if (!this.canManage) {
            return;
        }
        this.state.form = this.emptyForm();
        this.state.previewItems = [];
        this.state.showCreate = true;
    }

    closeCreate() {
        this.state.showCreate = false;
        this.state.busy = "";
    }

    openFinding() {
        if (!this.canManage) {
            return;
        }
        this.state.findingForm = this.emptyFindingForm();
        this.state.showFinding = true;
    }

    closeFinding() {
        this.state.showFinding = false;
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

    onPropertyChange(ev) {
        this.state.form.property_id = ev.target.value;
        this.state.form.building_id = "";
        this.state.form.area_id = "";
    }

    onBuildingChange(ev) {
        this.state.form.building_id = ev.target.value;
        this.state.form.area_id = "";
    }

    async onTemplateChange(ev) {
        this.state.form.template_id = ev.target.value;
        const templateId = Number(this.state.form.template_id || 0);
        if (!templateId) {
            this.state.previewItems = [];
            return;
        }
        this.state.previewItems = await this.orm.call(MODEL, "get_template_preview", [templateId]);
        const template = this.state.lookups.templates.find((row) => row.id === templateId);
        if (template && !this.state.form.name) {
            this.state.form.name = template.name;
        }
    }

    async createAudit() {
        if (!this.canManage) {
            return;
        }
        const form = this.state.form;
        if (!form.name.trim() || !form.date_planned || !form.property_id) {
            this.notification.add("Name, planned date, and property are required.", { type: "danger" });
            return;
        }
        if (form.kind === "audit" && !form.audit_type) {
            this.notification.add("Select an audit type.", { type: "danger" });
            return;
        }
        if (form.kind === "inspection" && !form.inspection_type) {
            this.notification.add("Select an inspection type.", { type: "danger" });
            return;
        }
        this.state.busy = "Creating…";
        try {
            const vals = {
                name: form.name.trim(),
                kind: form.kind,
                date_planned: form.date_planned,
                property_id: Number(form.property_id),
                scope: form.scope || false,
                notes: form.notes || false,
            };
            if (form.kind === "audit") {
                vals.audit_type = form.audit_type;
                vals.inspection_type = false;
            } else {
                vals.inspection_type = form.inspection_type;
                vals.audit_type = false;
            }
            if (form.template_id) {
                vals.template_id = Number(form.template_id);
            }
            if (form.building_id) {
                vals.building_id = Number(form.building_id);
            }
            if (form.area_id) {
                vals.area_id = Number(form.area_id);
            }
            if (form.assigned_user_id) {
                vals.assigned_user_id = Number(form.assigned_user_id);
            }
            const created = await this.orm.create(MODEL, [vals]);
            const resId = Array.isArray(created) ? created[0] : created;
            this.notification.add("Audit / inspection created.", { type: "success" });
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

    async saveLines() {
        const writes = [];
        for (const line of this.state.lines) {
            const result = this.state.lineResults[line.id] || false;
            const remarks = this.state.lineRemarks[line.id] || false;
            if (result !== (line.result || false) || remarks !== (line.remarks || false)) {
                writes.push(this.orm.write(LINE_MODEL, [line.id], { result, remarks }));
            }
        }
        if (writes.length) {
            await Promise.all(writes);
        }
    }

    async saveProgress() {
        if (!this.canManage) {
            return;
        }
        this.state.busy = "Saving…";
        try {
            await this.saveLines();
            this.notification.add("Checklist progress saved.", { type: "success" });
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
            if (["action_complete", "action_pending_review"].includes(method)) {
                await this.saveLines();
            }
            await this.orm.call(MODEL, method, [[this.state.resId]]);
            this.notification.add("Record updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async createFinding() {
        if (!this.canManage || !this.state.resId) {
            return;
        }
        const form = this.state.findingForm;
        if (!form.name.trim()) {
            this.notification.add("Finding title is required.", { type: "danger" });
            return;
        }
        this.state.busy = "Logging finding…";
        try {
            const vals = {
                name: form.name.trim(),
                severity: form.severity || "medium",
                description: form.description || false,
                audit_id: this.state.resId,
            };
            if (form.audit_line_id) {
                vals.audit_line_id = Number(form.audit_line_id);
            }
            await this.orm.create(FINDING_MODEL, [vals]);
            this.notification.add("Finding logged.", { type: "success" });
            this.state.showFinding = false;
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not log finding.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async findingAction(findingId, method) {
        if (!this.canManage) {
            return;
        }
        this.state.busy = "Updating finding…";
        try {
            await this.orm.call(FINDING_MODEL, method, [[findingId]]);
            this.notification.add("Finding updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Finding action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }
}

registry.category("actions").add("compliance_audit_management.action_audits", ComplianceAudits);
