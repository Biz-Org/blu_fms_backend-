import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const MODEL = "fire.safety.incident";
const PERSON_MODEL = "fire.safety.incident.person";
const FINDING_MODEL = "fire.safety.finding";
const ACTION_MODEL = "fire.safety.action";
const PAGE_SIZE = 20;

const INCIDENT_FIELDS = [
    "name",
    "incident_type",
    "severity",
    "state",
    "incident_datetime",
    "location_detail",
    "description",
    "immediate_action",
    "reported_by_id",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
    "investigation_notes",
    "root_cause",
    "resolved_datetime",
    "evidence_ids",
];

const PERSON_FIELDS = ["name", "role", "contact", "notes", "incident_id"];

const FINDING_FIELDS = [
    "name",
    "severity",
    "state",
    "description",
    "incident_id",
    "action_count",
    "assigned_user_id",
];

const ACTION_FIELDS = [
    "name",
    "state",
    "deadline",
    "is_overdue",
    "description",
    "finding_id",
    "assigned_user_id",
    "verification_notes",
    "verified_by_id",
    "verified_datetime",
];

const TYPE_LABELS = {
    fire: "Fire",
    smoke_detection: "Smoke Detection",
    fire_alarm: "Fire Alarm",
    electrical: "Electrical Incident",
    gas_leak: "Gas Leak",
    safety_hazard: "Safety Hazard",
    injury: "Injury/Accident",
    false_alarm: "False Alarm",
    other: "Other",
};

const STATE_LABELS = {
    open: "Open",
    investigating: "Investigating",
    resolved: "Resolved",
};

const ACTION_STATE_LABELS = {
    open: "Open",
    done: "Awaiting Verification",
    closed: "Closed",
};

const SEVERITY_LABELS = {
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",
};

function pad(value) {
    return String(value).padStart(2, "0");
}

function todayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function nowLocal() {
    const now = new Date();
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function fromDatetimeLocal(value) {
    if (!value) {
        return false;
    }
    return value.includes("T") ? `${value.replace("T", " ")}:00` : value;
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

export class FireSafetyIncidents extends Component {
    static template = "fire_safety_management.Incidents";
    static components = { FsAppShell, ...FS_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = user;
        this.pageSize = PAGE_SIZE;
        this.state = useState({
            mode: "list",
            resId: null,
            loading: true,
            busy: "",
            error: "",
            search: "",
            filter: "all",
            typeFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { total: 0, open: 0, investigating: 0, resolved: 0 },
            record: null,
            persons: [],
            findings: [],
            actions: [],
            attachments: [],
            isSafetyManager: false,
            isSecurity: false,
            isGuard: false,
            form: this.emptyForm(),
            personForm: this.emptyPersonForm(),
            findingForm: this.emptyFindingForm(),
            actionForm: this.emptyActionForm(),
            notesForm: { investigation_notes: "", root_cause: "", immediate_action: "" },
            verifyNotes: {},
            lookups: { properties: [], buildings: [], areas: [], users: [] },
        });
        onWillStart(async () => {
            const [isSafetyManager, isSecurity, isGuard] = await Promise.all([
                user.hasGroup("fire_safety_management.group_fire_safety_manager"),
                user.hasGroup("fire_safety_management.group_fire_safety_security"),
                user.hasGroup("fire_safety_management.group_fire_safety_guard"),
            ]);
            this.state.isSafetyManager = isSafetyManager;
            this.state.isSecurity = isSecurity;
            this.state.isGuard = isGuard && !isSafetyManager && !isSecurity;
            const ctx = this.props.action?.context || {};
            const mode = ctx.fs_mode || "list";
            const resId = ctx.fs_res_id || ctx.active_id || null;
            if (mode === "create" && this.canReport) {
                this.state.mode = "create";
            } else if (mode === "detail" && resId) {
                this.state.mode = "detail";
                this.state.resId = resId;
            }
            await this.reload();
        });
    }

    emptyForm() {
        return {
            incident_type: "safety_hazard",
            severity: "medium",
            incident_datetime: nowLocal(),
            property_id: "",
            building_id: "",
            area_id: "",
            assigned_user_id: "",
            location_detail: "",
            description: "",
            immediate_action: "",
            persons: [{ name: "", role: "", contact: "" }],
            pendingFiles: [],
        };
    }

    emptyPersonForm() {
        return { name: "", role: "", contact: "", notes: "" };
    }

    emptyFindingForm() {
        return { name: "", severity: "medium", description: "" };
    }

    emptyActionForm() {
        return { finding_id: "", name: "", deadline: todayIso(), assigned_user_id: "", description: "" };
    }

    rpcMessage(error) {
        return error?.data?.message || error?.message || "Request failed.";
    }

    m2oId(value) {
        return Array.isArray(value) ? value[0] || false : value || false;
    }

    m2oName(value) {
        return Array.isArray(value) ? value[1] || "" : value || "";
    }

    toId(value) {
        const number = Number(value);
        return number ? number : false;
    }

    typeLabel(value) {
        return TYPE_LABELS[value] || (value || "").replace(/_/g, " ") || "—";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ");
    }

    actionStateLabel(value) {
        return ACTION_STATE_LABELS[value] || (value || "").replace(/_/g, " ");
    }

    severityLabel(value) {
        return SEVERITY_LABELS[value] || value || "—";
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }

    formatDate(value) {
        return value ? String(value).slice(0, 10) : "—";
    }

    stripHtml(html) {
        return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }

    get types() {
        return Object.entries(TYPE_LABELS);
    }

    get canReport() {
        return this.state.isSafetyManager || this.state.isSecurity || this.state.isGuard;
    }

    get canOperate() {
        return this.state.isSafetyManager || this.state.isSecurity;
    }

    get incident() {
        return this.state.record || {};
    }

    get filteredBuildings() {
        const propertyId = this.toId(this.state.form.property_id);
        return (this.state.lookups.buildings || []).filter(
            (row) => !propertyId || this.m2oId(row.property_id) === propertyId
        );
    }

    get filteredAreas() {
        const buildingId = this.toId(this.state.form.building_id);
        return (this.state.lookups.areas || []).filter(
            (row) => !buildingId || this.m2oId(row.building_id) === buildingId
        );
    }

    get openFindings() {
        return this.state.findings.filter((row) => row.state !== "closed");
    }

    get canInvestigate() {
        return this.canOperate && this.incident.state === "open";
    }

    get canResolve() {
        return this.state.isSafetyManager && this.incident.state === "investigating";
    }

    get canEditInvestigation() {
        return this.canOperate && this.incident.state !== "resolved";
    }

    get canAddPerson() {
        return this.canOperate && this.incident.state !== "resolved";
    }

    get canAddFinding() {
        return this.state.isSafetyManager && this.incident.state !== "resolved";
    }

    get canAddAction() {
        return this.state.isSafetyManager && this.openFindings.length;
    }

    get canUploadEvidence() {
        return this.canOperate && this.incident.state !== "resolved";
    }

    get pageFrom() {
        return this.state.total ? (this.state.page - 1) * this.pageSize + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.page * this.pageSize, this.state.total);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.state.total / this.pageSize));
    }

    actionsFor(finding) {
        return this.state.actions.filter((row) => this.m2oId(row.finding_id) === finding.id);
    }

    canMarkDone(action) {
        return action.state === "open"
            && (this.state.isSafetyManager || this.m2oId(action.assigned_user_id) === user.userId);
    }

    canVerify(action) {
        return this.state.isSafetyManager
            && action.state === "done"
            && this.m2oId(action.assigned_user_id) !== user.userId;
    }

    canCloseAction(action) {
        return this.state.isSafetyManager && action.state === "done" && this.m2oId(action.verified_by_id);
    }

    canReopen(action) {
        return this.state.isSafetyManager && action.state === "done";
    }

    canProgressFinding(finding) {
        return this.state.isSafetyManager && finding.state === "open";
    }

    canCloseFinding(finding) {
        return this.state.isSafetyManager && finding.state !== "closed";
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            if (this.state.mode === "list") {
                await this.loadList();
            } else if (this.state.mode === "create") {
                this.state.form = this.emptyForm();
                await this.loadLookups();
            } else if (this.state.resId) {
                await Promise.all([this.loadLookups(), this.loadRecord(this.state.resId)]);
            }
        } catch (error) {
            this.state.error = this.rpcMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    async loadLookups() {
        const [properties, buildings, areas] = await Promise.all([
            this.orm.searchRead("fire.safety.property", [["active", "=", true]], ["name"], { order: "name" }),
            this.orm.searchRead("fire.safety.building", [["active", "=", true]], ["name", "property_id"], { order: "name" }),
            this.orm.searchRead("fire.safety.area", [["active", "=", true]], ["name", "building_id"], { order: "name" }),
        ]);
        let users = [];
        try {
            users = await this.orm.searchRead(
                "res.users",
                [["share", "=", false], ["active", "=", true]],
                ["name"],
                { limit: 80, order: "name" }
            );
        } catch {
            users = [];
        }
        this.state.lookups = { properties, buildings, areas, users };
    }

    listDomain() {
        const domain = [];
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", ["name", "ilike", search], ["location_detail", "ilike", search]);
        }
        if (this.state.typeFilter) {
            domain.push(["incident_type", "=", this.state.typeFilter]);
        }
        if (this.state.filter === "open_loop") {
            domain.push(["state", "in", ["open", "investigating"]]);
        } else if (this.state.filter === "mine") {
            domain.push("|", ["assigned_user_id", "=", user.userId], ["reported_by_id", "=", user.userId]);
        } else if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    async loadList() {
        const domain = this.listDomain();
        const [total, records, allTotal, openCount, investigatingCount, resolvedCount] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, INCIDENT_FIELDS, {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "incident_datetime desc, id desc",
            }),
            this.orm.searchCount(MODEL, []),
            this.orm.searchCount(MODEL, [["state", "=", "open"]]),
            this.orm.searchCount(MODEL, [["state", "=", "investigating"]]),
            this.orm.searchCount(MODEL, [["state", "=", "resolved"]]),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = {
            total: allTotal,
            open: openCount,
            investigating: investigatingCount,
            resolved: resolvedCount,
        };
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], INCIDENT_FIELDS);
        this.state.record = rows[0] || null;
        this.state.resId = id;
        if (!this.state.record) {
            this.state.error = "Incident not found.";
            this.state.persons = [];
            this.state.findings = [];
            this.state.actions = [];
            return;
        }
        const [persons, findings] = await Promise.all([
            this.orm.searchRead(PERSON_MODEL, [["incident_id", "=", id]], PERSON_FIELDS, { order: "id" }),
            this.orm.searchRead(FINDING_MODEL, [["incident_id", "=", id]], FINDING_FIELDS, { order: "id desc" }),
        ]);
        this.state.persons = persons;
        this.state.findings = findings;
        const findingIds = findings.map((row) => row.id);
        this.state.actions = findingIds.length
            ? await this.orm.searchRead(ACTION_MODEL, [["finding_id", "in", findingIds]], ACTION_FIELDS, { order: "deadline, id" })
            : [];
        this.state.notesForm = {
            investigation_notes: this.stripHtml(this.state.record.investigation_notes),
            root_cause: this.stripHtml(this.state.record.root_cause),
            immediate_action: this.stripHtml(this.state.record.immediate_action),
        };
        this.state.findingForm = this.emptyFindingForm();
        this.state.personForm = this.emptyPersonForm();
        this.state.actionForm = {
            ...this.emptyActionForm(),
            finding_id: findingIds[0] ? String(findingIds[0]) : "",
            assigned_user_id: this.m2oId(this.state.record.assigned_user_id)
                ? String(this.m2oId(this.state.record.assigned_user_id))
                : "",
        };
        const evidenceIds = this.state.record.evidence_ids || [];
        this.state.attachments = evidenceIds.length
            ? await this.orm.searchRead("ir.attachment", [["id", "in", evidenceIds]], ["name", "mimetype", "file_size"])
            : [];
    }

    setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.reload();
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

    onPage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.pageCount) {
            return;
        }
        this.state.page = next;
        this.reload();
    }

    onPropertyChange() {
        this.state.form.building_id = "";
        this.state.form.area_id = "";
    }

    onBuildingChange() {
        this.state.form.area_id = "";
    }

    addPersonRow() {
        this.state.form.persons.push({ name: "", role: "", contact: "" });
    }

    removePersonRow(index) {
        this.state.form.persons.splice(index, 1);
        if (!this.state.form.persons.length) {
            this.state.form.persons.push({ name: "", role: "", contact: "" });
        }
    }

    onPendingFiles(ev) {
        this.state.form.pendingFiles = [...this.state.form.pendingFiles, ...(ev.target.files || [])];
        ev.target.value = "";
    }

    removePendingFile(index) {
        this.state.form.pendingFiles.splice(index, 1);
    }

    async withBusy(label, fn) {
        this.state.busy = label;
        this.state.error = "";
        try {
            await fn();
        } catch (error) {
            const message = this.rpcMessage(error);
            this.state.error = message;
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.busy = "";
        }
    }

    async uploadAttachments(files, resModel, resId) {
        const ids = [];
        for (const file of files) {
            const datas = await fileToBase64(file);
            const created = await this.orm.create("ir.attachment", [{
                name: file.name,
                datas,
                res_model: resModel,
                res_id: resId || false,
                mimetype: file.type || "application/octet-stream",
            }]);
            ids.push(Array.isArray(created) ? created[0] : created);
        }
        return ids;
    }

    async reportIncident() {
        if (!this.canReport) {
            return;
        }
        if (!this.state.form.description.trim()) {
            this.notification.add("Describe what happened before reporting the incident.", { type: "danger" });
            return;
        }
        if (!this.state.form.incident_datetime) {
            this.notification.add("Incident date and time are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Reporting incident...", async () => {
            const evidenceIds = this.state.form.pendingFiles.length
                ? await this.uploadAttachments(this.state.form.pendingFiles, MODEL, false)
                : [];
            const persons = (this.state.form.persons || [])
                .filter((row) => (row.name || "").trim())
                .map((row) => [0, 0, {
                    name: row.name.trim(),
                    role: row.role || false,
                    contact: row.contact || false,
                }]);
            const result = await this.orm.call(MODEL, "action_report_incident", [{
                incident_type: this.state.form.incident_type,
                severity: this.state.form.severity,
                incident_datetime: fromDatetimeLocal(this.state.form.incident_datetime),
                property_id: this.toId(this.state.form.property_id),
                building_id: this.toId(this.state.form.building_id),
                area_id: this.toId(this.state.form.area_id),
                assigned_user_id: this.toId(this.state.form.assigned_user_id) || user.userId,
                location_detail: this.state.form.location_detail || false,
                description: this.state.form.description,
                immediate_action: this.state.form.immediate_action || false,
                person_ids: persons,
                evidence_ids: evidenceIds.length ? [[6, 0, evidenceIds]] : [],
            }]);
            const id = Array.isArray(result) ? result[0] : result;
            this.notification.add("Incident reported.", { type: "success" });
            this.setMode("detail", id);
        });
    }

    async callWorkflow(method) {
        await this.withBusy("Updating incident...", async () => {
            await this.orm.call(MODEL, method, [[this.state.resId]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Incident updated.", { type: "success" });
        });
    }

    startInvestigation() {
        return this.callWorkflow("action_start_investigation");
    }

    resolveIncident() {
        return this.callWorkflow("action_resolve_incident");
    }

    async saveInvestigation() {
        if (!this.canEditInvestigation) {
            return;
        }
        await this.withBusy("Saving investigation...", async () => {
            await this.orm.write(MODEL, [this.state.resId], {
                investigation_notes: this.state.notesForm.investigation_notes || false,
                root_cause: this.state.notesForm.root_cause || false,
                immediate_action: this.state.notesForm.immediate_action || false,
            });
            await this.loadRecord(this.state.resId);
            this.notification.add("Investigation notes saved.", { type: "success" });
        });
    }

    async addPerson() {
        if (!this.canAddPerson || !this.state.personForm.name.trim()) {
            this.notification.add("Person name is required.", { type: "danger" });
            return;
        }
        await this.withBusy("Adding person...", async () => {
            await this.orm.create(PERSON_MODEL, [{
                incident_id: this.state.resId,
                name: this.state.personForm.name.trim(),
                role: this.state.personForm.role || false,
                contact: this.state.personForm.contact || false,
                notes: this.state.personForm.notes || false,
            }]);
            this.state.personForm = this.emptyPersonForm();
            await this.loadRecord(this.state.resId);
            this.notification.add("Person added.", { type: "success" });
        });
    }

    async onEvidenceFiles(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        if (!files.length || !this.canUploadEvidence) {
            return;
        }
        await this.withBusy("Uploading evidence...", async () => {
            const ids = await this.uploadAttachments(files, MODEL, this.state.resId);
            await this.orm.write(MODEL, [this.state.resId], {
                evidence_ids: ids.map((id) => [4, id]),
            });
            await this.loadRecord(this.state.resId);
            this.notification.add("Evidence uploaded.", { type: "success" });
        });
    }

    async createFinding() {
        if (!this.canAddFinding || !this.state.findingForm.name.trim()) {
            this.notification.add("Finding title is required.", { type: "danger" });
            return;
        }
        await this.withBusy("Creating finding...", async () => {
            await this.orm.create(FINDING_MODEL, [{
                name: this.state.findingForm.name.trim(),
                incident_id: this.state.resId,
                severity: this.state.findingForm.severity,
                description: this.state.findingForm.description || false,
            }]);
            this.state.findingForm = this.emptyFindingForm();
            await this.loadRecord(this.state.resId);
            this.notification.add("Finding recorded.", { type: "success" });
        });
    }

    async createAction() {
        if (!this.canAddAction) {
            return;
        }
        if (!this.state.actionForm.name.trim() || !this.toId(this.state.actionForm.finding_id) || !this.state.actionForm.deadline) {
            this.notification.add("Corrective action title, finding, and deadline are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Creating corrective action...", async () => {
            await this.orm.create(ACTION_MODEL, [{
                name: this.state.actionForm.name.trim(),
                finding_id: this.toId(this.state.actionForm.finding_id),
                deadline: this.state.actionForm.deadline,
                assigned_user_id: this.toId(this.state.actionForm.assigned_user_id),
                description: this.state.actionForm.description || false,
            }]);
            this.state.actionForm = {
                ...this.emptyActionForm(),
                finding_id: this.state.actionForm.finding_id,
            };
            await this.loadRecord(this.state.resId);
            this.notification.add("Corrective action created.", { type: "success" });
        });
    }

    async callRecord(model, method, id) {
        await this.withBusy("Updating record...", async () => {
            await this.orm.call(model, method, [[id]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Record updated.", { type: "success" });
        });
    }

    markFindingProgress(finding) {
        return this.callRecord(FINDING_MODEL, "action_mark_in_progress", finding.id);
    }

    closeFinding(finding) {
        return this.callRecord(FINDING_MODEL, "action_close_finding", finding.id);
    }

    markActionDone(action) {
        return this.callRecord(ACTION_MODEL, "action_mark_done", action.id);
    }

    reopenAction(action) {
        return this.callRecord(ACTION_MODEL, "action_reopen", action.id);
    }

    async verifyAction(action) {
        await this.withBusy("Verifying action...", async () => {
            const notes = (this.state.verifyNotes[action.id] || "").trim();
            if (notes) {
                await this.orm.write(ACTION_MODEL, [action.id], { verification_notes: notes });
            }
            await this.orm.call(ACTION_MODEL, "action_verify", [[action.id]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Corrective action verified.", { type: "success" });
        });
    }

    closeAction(action) {
        return this.callRecord(ACTION_MODEL, "action_close", action.id);
    }
}

registry.category("actions").add("fire_safety_management.action_incidents", FireSafetyIncidents);
