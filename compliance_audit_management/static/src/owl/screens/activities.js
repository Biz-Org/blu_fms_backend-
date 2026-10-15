import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const MODEL = "compliance.check";
const LINE_MODEL = "compliance.check.line";
const PAGE_SIZE = 10;

const CHECK_FIELDS = [
    "name",
    "reference",
    "requirement_id",
    "category",
    "template_id",
    "due_date",
    "repeat",
    "notes",
    "state",
    "is_overdue",
    "line_count",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
];

const LINE_FIELDS = ["name", "sequence", "required", "result", "remarks", "check_id"];

const STATE_LABELS = {
    scheduled: "Scheduled",
    in_progress: "In Progress",
    pending: "Pending",
    completed: "Completed",
};

const CATEGORY_LABELS = {
    ehs: "Environmental Health & Safety",
    fire_life_safety: "Fire & Life Safety",
    hvac: "HVAC & Mechanical Systems",
    accessibility: "Accessibility (ADA)",
    health_safety: "Health & Safety",
    mechanical: "Mechanical",
    environmental: "Environmental",
    building: "Building",
    equipment: "Equipment",
    regulatory: "Regulatory",
    other: "Other",
};

const REPEAT_OPTIONS = [
    { value: "none", label: "Does not repeat" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
    { value: "quarterly", label: "Quarterly" },
    { value: "annually", label: "Annually" },
];

const RESULT_OPTIONS = [
    { value: "compliant", label: "Compliant" },
    { value: "non_compliant", label: "Non-Compliant" },
    { value: "na", label: "Not Applicable" },
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

export class ComplianceActivities extends Component {
    static template = "compliance_audit_management.Activities";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.categories = Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }));
        this.repeatOptions = REPEAT_OPTIONS;
        this.resultOptions = RESULT_OPTIONS;
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            showCreate: false,
            search: "",
            filter: "all",
            categoryFilter: "",
            propertyFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { overdue: 0, pending: 0, scheduled_30d: 0, completion_rate: 0 },
            record: null,
            lines: [],
            lineResults: {},
            lineRemarks: {},
            isManager: false,
            isAuditor: false,
            form: this.emptyForm(),
            previewItems: [],
            lookups: {
                requirements: [],
                templates: [],
                properties: [],
                buildings: [],
                areas: [],
                users: [],
            },
        });
        onWillStart(async () => {
            const [isManager, isAuditor] = await Promise.all([
                user.hasGroup("compliance_audit_management.group_compliance_manager"),
                user.hasGroup("compliance_audit_management.group_compliance_auditor"),
            ]);
            this.state.isManager = isManager;
            this.state.isAuditor = isAuditor;
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
            requirement_id: "",
            template_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            assigned_user_id: String(user.userId || ""),
            due_date: todayIso(),
            repeat: "none",
            notes: "",
            name: "",
        };
    }

    get canCreate() {
        return this.state.isManager;
    }

    get canOperate() {
        return this.state.isManager;
    }

    get emptyListHint() {
        return this.canCreate
            ? "Create a compliance check to schedule statutory work."
            : "Assigned and company checks will appear here.";
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

    get filteredTemplates() {
        const requirementId = Number(this.state.form.requirement_id || 0);
        if (!requirementId) {
            return this.state.lookups.templates;
        }
        return this.state.lookups.templates.filter((tpl) => {
            const ids = tpl.requirement_ids || [];
            return !ids.length || ids.includes(requirementId);
        });
    }

    m2oName = m2oName;

    categoryLabel(value) {
        return CATEGORY_LABELS[value] || value || "—";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || value || "";
    }

    displayState(rec) {
        if (rec.is_overdue && rec.state !== "completed") {
            return "overdue";
        }
        return rec.state;
    }

    displayStateLabel(rec) {
        if (rec.is_overdue && rec.state !== "completed") {
            return "Overdue";
        }
        return this.stateLabel(rec.state);
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

    buildDomain() {
        const domain = [];
        const filter = this.state.filter;
        if (filter === "overdue") {
            domain.push(
                ["state", "!=", "completed"],
                ["due_date", "<", todayIso()]
            );
        } else if (filter !== "all") {
            domain.push(["state", "=", filter]);
        }
        if (this.state.categoryFilter) {
            domain.push(["category", "=", this.state.categoryFilter]);
        }
        if (this.state.propertyFilter) {
            domain.push(["property_id", "=", Number(this.state.propertyFilter)]);
        }
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", "|", ["name", "ilike", search], ["reference", "ilike", search], ["notes", "ilike", search]);
        }
        return domain;
    }

    async loadLookups() {
        const [requirements, templates, properties, buildings, areas, users] = await Promise.all([
            this.orm.searchRead("compliance.requirement", [["active", "=", true]], ["name", "category"], {
                order: "name",
                limit: 200,
            }),
            this.orm.searchRead(
                "compliance.checklist.template",
                [["active", "=", true]],
                ["name", "item_count", "requirement_ids", "preview_text"],
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
        this.state.lookups = { requirements, templates, properties, buildings, areas, users };
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
            this.state.error = error?.data?.message || error?.message || "Could not load compliance activities.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadList() {
        const domain = this.buildDomain();
        const [total, records, kpis] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, CHECK_FIELDS, {
                order: "due_date, id desc",
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
            }),
            this.orm.call(MODEL, "get_activity_kpis", []),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = kpis;
    }

    async loadDetail(resId) {
        const [records, lines] = await Promise.all([
            this.orm.searchRead(MODEL, [["id", "=", resId]], CHECK_FIELDS, { limit: 1 }),
            this.orm.searchRead(LINE_MODEL, [["check_id", "=", resId]], LINE_FIELDS, {
                order: "sequence, id",
            }),
        ]);
        if (!records.length) {
            this.state.mode = "list";
            this.state.resId = null;
            await this.loadList();
            this.notification.add("Activity not found.", { type: "warning" });
            return;
        }
        this.state.record = records[0];
        this.state.lines = lines;
        const lineResults = {};
        const lineRemarks = {};
        for (const line of lines) {
            lineResults[line.id] = line.result || "";
            lineRemarks[line.id] = line.remarks || "";
        }
        this.state.lineResults = lineResults;
        this.state.lineRemarks = lineRemarks;
        this.state.kpis = await this.orm.call(MODEL, "get_activity_kpis", []);
    }

    async setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.state.page = mode === "list" ? this.state.page : 1;
        await this.reload();
    }

    openCreate() {
        if (!this.canCreate) {
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

    onCategoryFilter(ev) {
        this.state.categoryFilter = ev.target.value;
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

    async onRequirementChange(ev) {
        this.state.form.requirement_id = ev.target.value;
        const requirement = this.state.lookups.requirements.find(
            (row) => String(row.id) === String(this.state.form.requirement_id)
        );
        if (requirement && !this.state.form.name) {
            this.state.form.name = requirement.name;
        }
        const stillValid = this.filteredTemplates.some(
            (tpl) => String(tpl.id) === String(this.state.form.template_id)
        );
        if (!stillValid) {
            this.state.form.template_id = "";
            this.state.previewItems = [];
        }
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

    onPropertyChange(ev) {
        this.state.form.property_id = ev.target.value;
        this.state.form.building_id = "";
        this.state.form.area_id = "";
    }

    onBuildingChange(ev) {
        this.state.form.building_id = ev.target.value;
        this.state.form.area_id = "";
    }

    async createCheck() {
        if (!this.canCreate) {
            return;
        }
        const form = this.state.form;
        if (!form.requirement_id || !form.due_date) {
            this.notification.add("Requirement and due date are required.", { type: "danger" });
            return;
        }
        if (!form.property_id) {
            this.notification.add("Property / building selection is required.", { type: "danger" });
            return;
        }
        this.state.busy = "Creating activity…";
        try {
            const requirement = this.state.lookups.requirements.find(
                (row) => String(row.id) === String(form.requirement_id)
            );
            const vals = {
                name: (form.name || requirement?.name || "Compliance Check").trim(),
                requirement_id: Number(form.requirement_id),
                due_date: form.due_date,
                repeat: form.repeat || "none",
                notes: form.notes || false,
                property_id: Number(form.property_id),
            };
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
            const createdId = await this.orm.create(MODEL, [vals]);
            const resId = Array.isArray(createdId) ? createdId[0] : createdId;
            this.notification.add("Compliance check created.", { type: "success" });
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
        if (!this.canOperate || !this.state.resId) {
            return;
        }
        this.state.busy = "Updating…";
        try {
            if (method === "action_complete") {
                await this.saveLines();
            }
            await this.orm.call(MODEL, method, [[this.state.resId]]);
            this.notification.add("Activity updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
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
        if (!this.canOperate) {
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
}

registry.category("actions").add("compliance_audit_management.action_activities", ComplianceActivities);
