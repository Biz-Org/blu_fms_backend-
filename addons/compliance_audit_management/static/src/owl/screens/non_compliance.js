import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const MODEL = "compliance.non.compliance";
const ACTION_MODEL = "compliance.action";
const PAGE_SIZE = 10;

const NC_FIELDS = [
    "name",
    "reference",
    "description",
    "source",
    "severity",
    "root_cause",
    "internal_notes",
    "due_date",
    "state",
    "is_overdue",
    "action_count",
    "requirement_id",
    "finding_id",
    "check_id",
    "audit_id",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
    "closed_by_id",
    "closed_datetime",
];

const ACTION_FIELDS = [
    "name",
    "description",
    "deadline",
    "state",
    "is_overdue",
    "verification_notes",
    "assigned_user_id",
    "non_compliance_id",
    "verified_by_id",
    "verified_datetime",
];

const STATE_LABELS = {
    open: "Open",
    assigned: "Assigned",
    in_progress: "In Progress",
    pending_verification: "Pending Verification",
    resolved: "Resolved",
    closed: "Closed",
};

const ACTION_STATE_LABELS = {
    open: "Open",
    in_progress: "In Progress",
    pending_verification: "Pending Verification",
    verified: "Verified",
    closed: "Closed",
};

const SOURCE_LABELS = {
    check: "Compliance Check",
    audit: "Audit",
    inspection: "Inspection",
    manual: "Manual",
};

const SEVERITY_OPTIONS = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "critical", label: "Critical" },
];

const OPEN_STATES = ["open", "assigned", "in_progress", "pending_verification"];

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

export class ComplianceNonCompliance extends Component {
    static template = "compliance_audit_management.NonCompliance";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;
        this.severityOptions = SEVERITY_OPTIONS;
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            showCreate: false,
            showAction: false,
            search: "",
            filter: "all",
            severityFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { open: 0, overdue: 0, pending_verification: 0, high_severity: 0 },
            record: null,
            actions: [],
            actionNotes: {},
            detailForm: this.emptyDetailForm(),
            isManager: false,
            form: this.emptyForm(),
            actionForm: this.emptyActionForm(),
            lookups: { properties: [], buildings: [], areas: [], users: [], requirements: [] },
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
            severity: "medium",
            source: "manual",
            due_date: todayIso(),
            property_id: "",
            building_id: "",
            area_id: "",
            requirement_id: "",
            assigned_user_id: String(user.userId || ""),
            description: "",
            root_cause: "",
            internal_notes: "",
        };
    }

    emptyDetailForm() {
        return {
            assigned_user_id: "",
            due_date: "",
            root_cause: "",
            internal_notes: "",
        };
    }

    emptyActionForm() {
        return {
            name: "",
            deadline: todayIso(),
            assigned_user_id: String(user.userId || ""),
            description: "",
            verification_notes: "",
        };
    }

    get canManage() {
        return this.state.isManager;
    }

    get emptyListHint() {
        return this.canManage
            ? "Log a non-compliance issue or convert a finding from an audit/check."
            : "Company non-compliance issues will appear here.";
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

    get detailEditable() {
        return this.canManage && this.state.record && this.state.record.state !== "closed";
    }

    m2oName = m2oName;

    stateLabel(value) {
        return STATE_LABELS[value] || value || "";
    }

    actionStateLabel(value) {
        return ACTION_STATE_LABELS[value] || value || "";
    }

    sourceLabel(value) {
        return SOURCE_LABELS[value] || value || "—";
    }

    severityLabel(value) {
        const match = SEVERITY_OPTIONS.find((opt) => opt.value === value);
        return match?.label || value || "—";
    }

    displayState(rec) {
        if (rec.is_overdue && OPEN_STATES.includes(rec.state)) {
            return "overdue";
        }
        return rec.state;
    }

    displayStateLabel(rec) {
        if (rec.is_overdue && OPEN_STATES.includes(rec.state)) {
            return "Overdue";
        }
        return this.stateLabel(rec.state);
    }

    actionDisplayState(rec) {
        if (rec.is_overdue && !["verified", "closed"].includes(rec.state)) {
            return "overdue";
        }
        return rec.state;
    }

    actionDisplayStateLabel(rec) {
        if (rec.is_overdue && !["verified", "closed"].includes(rec.state)) {
            return "Overdue";
        }
        return this.actionStateLabel(rec.state);
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
            domain.push(["state", "in", OPEN_STATES], ["due_date", "<", todayIso()]);
        } else if (filter === "open") {
            domain.push(["state", "in", ["open", "assigned"]]);
        } else if (filter === "high") {
            domain.push(["state", "in", OPEN_STATES], ["severity", "in", ["high", "critical"]]);
        } else if (filter !== "all") {
            domain.push(["state", "=", filter]);
        }
        if (this.state.severityFilter) {
            domain.push(["severity", "=", this.state.severityFilter]);
        }
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", "|", ["name", "ilike", search], ["reference", "ilike", search], [
                "root_cause",
                "ilike",
                search,
            ]);
        }
        return domain;
    }

    async loadLookups() {
        const [properties, buildings, areas, users, requirements] = await Promise.all([
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
            this.orm.searchRead("compliance.requirement", [], ["name", "code"], {
                order: "name",
                limit: 200,
            }),
        ]);
        this.state.lookups = { properties, buildings, areas, users, requirements };
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
                error?.data?.message || error?.message || "Could not load non-compliance issues.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadList() {
        const domain = this.buildDomain();
        const [total, records, kpis] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, NC_FIELDS, {
                order: "id desc",
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
            }),
            this.orm.call(MODEL, "get_nc_kpis", []),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = kpis;
    }

    async loadDetail(resId) {
        const [records, actions] = await Promise.all([
            this.orm.searchRead(MODEL, [["id", "=", resId]], NC_FIELDS, { limit: 1 }),
            this.orm.searchRead(ACTION_MODEL, [["non_compliance_id", "=", resId]], ACTION_FIELDS, {
                order: "deadline, id",
            }),
        ]);
        if (!records.length) {
            this.state.mode = "list";
            this.state.resId = null;
            await this.loadList();
            this.notification.add("Record not found.", { type: "warning" });
            return;
        }
        const record = records[0];
        this.state.record = record;
        this.state.actions = actions;
        const actionNotes = {};
        for (const action of actions) {
            actionNotes[action.id] = action.verification_notes || "";
        }
        this.state.actionNotes = actionNotes;
        this.state.detailForm = {
            assigned_user_id: String(m2oId(record.assigned_user_id) || ""),
            due_date: record.due_date || "",
            root_cause: record.root_cause || "",
            internal_notes: record.internal_notes || "",
        };
        this.state.kpis = await this.orm.call(MODEL, "get_nc_kpis", []);
    }

    async setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.state.showAction = false;
        await this.reload();
    }

    openCreate() {
        if (!this.canManage) {
            return;
        }
        this.state.form = this.emptyForm();
        this.state.showCreate = true;
    }

    closeCreate() {
        this.state.showCreate = false;
        this.state.busy = "";
    }

    openAction() {
        if (!this.canManage) {
            return;
        }
        this.state.actionForm = this.emptyActionForm();
        if (this.state.record?.assigned_user_id) {
            this.state.actionForm.assigned_user_id = String(m2oId(this.state.record.assigned_user_id));
        }
        this.state.showAction = true;
    }

    closeAction() {
        this.state.showAction = false;
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

    onSeverityFilter(ev) {
        this.state.severityFilter = ev.target.value;
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

    async createIssue() {
        if (!this.canManage) {
            return;
        }
        const form = this.state.form;
        if (!form.name.trim()) {
            this.notification.add("Issue title is required.", { type: "danger" });
            return;
        }
        this.state.busy = "Creating…";
        try {
            const vals = {
                name: form.name.trim(),
                severity: form.severity || "medium",
                source: form.source || "manual",
                due_date: form.due_date || false,
                description: form.description || false,
                root_cause: form.root_cause || false,
                internal_notes: form.internal_notes || false,
            };
            if (form.property_id) {
                vals.property_id = Number(form.property_id);
            }
            if (form.building_id) {
                vals.building_id = Number(form.building_id);
            }
            if (form.area_id) {
                vals.area_id = Number(form.area_id);
            }
            if (form.requirement_id) {
                vals.requirement_id = Number(form.requirement_id);
            }
            if (form.assigned_user_id) {
                vals.assigned_user_id = Number(form.assigned_user_id);
            }
            const created = await this.orm.create(MODEL, [vals]);
            const resId = Array.isArray(created) ? created[0] : created;
            this.notification.add("Non-compliance issue created.", { type: "success" });
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
            await this.orm.write(MODEL, [this.state.resId], {
                assigned_user_id: form.assigned_user_id ? Number(form.assigned_user_id) : false,
                due_date: form.due_date || false,
                root_cause: form.root_cause || false,
                internal_notes: form.internal_notes || false,
            });
            this.notification.add("Issue updated.", { type: "success" });
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
            this.notification.add("Issue updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async createCorrectiveAction() {
        if (!this.canManage || !this.state.resId) {
            return;
        }
        const form = this.state.actionForm;
        if (!form.name.trim() || !form.deadline) {
            this.notification.add("Action title and deadline are required.", { type: "danger" });
            return;
        }
        this.state.busy = "Adding action…";
        try {
            const vals = {
                name: form.name.trim(),
                non_compliance_id: this.state.resId,
                deadline: form.deadline,
                description: form.description || false,
            };
            if (form.assigned_user_id) {
                vals.assigned_user_id = Number(form.assigned_user_id);
            }
            await this.orm.create(ACTION_MODEL, [vals]);
            this.notification.add("Corrective action added.", { type: "success" });
            this.state.showAction = false;
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not add action.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async caRun(actionId, method) {
        if (!this.canManage) {
            return;
        }
        this.state.busy = "Updating action…";
        try {
            await this.orm.call(ACTION_MODEL, method, [[actionId]]);
            this.notification.add("Corrective action updated.", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Action failed.", {
                type: "danger",
            });
        } finally {
            this.state.busy = "";
        }
    }

    async caSaveNotes(actionId) {
        if (!this.canManage) {
            return;
        }
        this.state.busy = "Saving notes…";
        try {
            await this.orm.write(ACTION_MODEL, [actionId], {
                verification_notes: this.state.actionNotes[actionId] || false,
            });
            this.notification.add("Verification notes saved.", { type: "success" });
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

registry
    .category("actions")
    .add("compliance_audit_management.action_non_compliance", ComplianceNonCompliance);
