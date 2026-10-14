import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const MODEL = "fire.safety.inspection";
const LINE_MODEL = "fire.safety.inspection.line";
const FINDING_MODEL = "fire.safety.finding";
const ACTION_MODEL = "fire.safety.action";
const PAGE_SIZE = 20;

const INSPECTION_FIELDS = [
    "name",
    "inspection_type",
    "state",
    "scheduled_date",
    "start_datetime",
    "complete_datetime",
    "close_datetime",
    "is_overdue",
    "checklist_template_id",
    "finding_count",
    "action_count",
    "line_count",
    "failed_line_count",
    "inspector_id",
    "assigned_user_id",
    "property_id",
    "building_id",
    "area_id",
    "location_detail",
    "notes",
    "attachment_ids",
];

const LINE_FIELDS = [
    "name",
    "category",
    "sequence",
    "required",
    "result",
    "notes",
    "attachment_ids",
    "inspection_id",
];

const FINDING_FIELDS = [
    "name",
    "severity",
    "state",
    "description",
    "line_id",
    "inspection_id",
    "action_count",
    "assigned_user_id",
    "evidence_ids",
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
    "closed_by_id",
    "closed_datetime",
    "evidence_ids",
];

const TYPE_LABELS = {
    fire_inspection: "Fire Inspection",
    safety_audit: "Safety Audit",
};

const STATE_LABELS = {
    scheduled: "Scheduled",
    in_progress: "In Progress",
    pending: "Pending",
    completed: "Completed",
    closed: "Closed",
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

const CATEGORY_LABELS = {
    fire_extinguishers: "Fire Extinguishers",
    fire_alarms: "Fire Alarms",
    fire_exits: "Fire Exits",
    emergency_lighting: "Emergency Lighting",
    evacuation_routes: "Evacuation Routes",
    emergency_signage: "Emergency Signage",
    fire_safety_equipment: "Fire Safety Equipment",
};

function todayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
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

export class FireSafetyInspections extends Component {
    static template = "fire_safety_management.Inspections";
    static components = { FsAppShell, ...FS_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
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
            kpis: { total: 0, open: 0, overdue: 0, pending: 0 },
            record: null,
            lines: [],
            findings: [],
            actions: [],
            attachments: [],
            lineAttachments: {},
            isSafetyManager: false,
            isSecurity: false,
            isReadOnly: true,
            form: this.emptyForm(),
            findingForm: this.emptyFindingForm(),
            actionForm: this.emptyActionForm(),
            lineNotes: {},
            verifyNotes: {},
            lookups: { properties: [], buildings: [], areas: [], templates: [], users: [] },
        });
        onWillStart(async () => {
            const [isSafetyManager, isSecurity, isGuard, isFacility, isAuditor, isExecutive] = await Promise.all([
                user.hasGroup("fire_safety_management.group_fire_safety_manager"),
                user.hasGroup("fire_safety_management.group_fire_safety_security"),
                user.hasGroup("fire_safety_management.group_fire_safety_guard"),
                user.hasGroup("fire_safety_management.group_fire_safety_facility"),
                user.hasGroup("fire_safety_management.group_fire_safety_auditor"),
                user.hasGroup("fire_safety_management.group_fire_safety_executive"),
            ]);
            this.state.isSafetyManager = isSafetyManager;
            this.state.isSecurity = isSecurity;
            this.state.isReadOnly = !isSafetyManager && !isSecurity
                && (isFacility || isAuditor || isExecutive || isGuard);
            const ctx = this.props.action?.context || {};
            const mode = ctx.fs_mode || "list";
            const resId = ctx.fs_res_id || ctx.active_id || null;
            if (mode === "create" && isSafetyManager) {
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
            inspection_type: "fire_inspection",
            scheduled_date: todayIso(),
            property_id: "",
            building_id: "",
            area_id: "",
            assigned_user_id: "",
            checklist_template_id: "",
            inspector_id: String(user.userId || ""),
            location_detail: "",
            notes: "",
        };
    }

    emptyFindingForm() {
        return { name: "", severity: "medium", line_id: "", description: "" };
    }

    emptyActionForm() {
        return { finding_id: "", name: "", deadline: todayIso(), assigned_user_id: "", description: "" };
    }

    rpcMessage(error) {
        return error?.data?.message || error?.message || "Request failed.";
    }

    m2oId(value) {
        if (Array.isArray(value)) {
            return value[0] || false;
        }
        return value || false;
    }

    m2oName(value) {
        if (Array.isArray(value)) {
            return value[1] || "";
        }
        return value || "";
    }

    toId(value) {
        const number = Number(value);
        return number ? number : false;
    }

    typeLabel(value) {
        return TYPE_LABELS[value] || value || "—";
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

    categoryLabel(value) {
        return CATEGORY_LABELS[value] || (value || "").replace(/_/g, " ") || "General";
    }

    formatDate(value) {
        return value ? String(value).slice(0, 10) : "—";
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }

    stripHtml(html) {
        return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }

    get canCreate() {
        return this.state.isSafetyManager;
    }

    get canOperate() {
        return this.state.isSafetyManager || this.state.isSecurity;
    }

    get inspection() {
        return this.state.record || {};
    }

    get filteredTemplates() {
        const type = this.state.form.inspection_type;
        return (this.state.lookups.templates || []).filter(
            (row) => !type || row.inspection_type === "both" || row.inspection_type === type
        );
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

    get requiredOpenLines() {
        return this.state.lines.filter((line) => line.required && !line.result);
    }

    get failedLines() {
        return this.state.lines.filter((line) => line.result === "fail");
    }

    get openActions() {
        return this.state.actions.filter((row) => row.state !== "closed");
    }

    get openFindings() {
        return this.state.findings.filter((row) => row.state !== "closed");
    }

    get canEditChecklist() {
        return this.canOperate && ["scheduled", "in_progress"].includes(this.inspection.state);
    }

    get canStart() {
        return this.canOperate && this.inspection.state === "scheduled";
    }

    get canComplete() {
        return this.state.isSafetyManager && this.inspection.state === "in_progress";
    }

    get canMarkCompleted() {
        return this.state.isSafetyManager && this.inspection.state === "pending";
    }

    get canClose() {
        return this.state.isSafetyManager && this.inspection.state === "completed";
    }

    get canAddFinding() {
        return this.state.isSafetyManager && ["scheduled", "in_progress", "pending"].includes(this.inspection.state);
    }

    get canAddAction() {
        return this.state.isSafetyManager && this.state.findings.some((row) => row.state !== "closed");
    }

    get canApplyChecklist() {
        return this.state.isSafetyManager && ["scheduled", "in_progress"].includes(this.inspection.state);
    }

    get pageFrom() {
        if (!this.state.total) {
            return 0;
        }
        return (this.state.page - 1) * this.pageSize + 1;
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
        if (action.state !== "open") {
            return false;
        }
        return this.state.isSafetyManager || this.m2oId(action.assigned_user_id) === user.userId;
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

    lineAttachments(line) {
        return this.state.lineAttachments[line.id] || [];
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
        const [properties, buildings, areas, templates] = await Promise.all([
            this.orm.searchRead("fire.safety.property", [["active", "=", true]], ["name", "code"], { order: "name" }),
            this.orm.searchRead("fire.safety.building", [["active", "=", true]], ["name", "property_id"], { order: "name" }),
            this.orm.searchRead("fire.safety.area", [["active", "=", true]], ["name", "building_id"], { order: "name" }),
            this.orm.searchRead(
                "fire.safety.checklist.template",
                [["active", "=", true]],
                ["name", "inspection_type", "item_count"],
                { order: "name" }
            ),
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
        this.state.lookups = { properties, buildings, areas, templates, users };
    }

    listDomain() {
        const domain = [];
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push(["name", "ilike", search]);
        }
        if (this.state.typeFilter) {
            domain.push(["inspection_type", "=", this.state.typeFilter]);
        }
        if (this.state.filter === "overdue") {
            domain.push(["is_overdue", "=", true]);
        } else if (this.state.filter === "open") {
            domain.push(["state", "in", ["scheduled", "in_progress", "pending"]]);
        } else if (this.state.filter === "mine") {
            domain.push("|", ["assigned_user_id", "=", user.userId], ["inspector_id", "=", user.userId]);
        } else if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    async loadList() {
        const domain = this.listDomain();
        const openDomain = [["state", "in", ["scheduled", "in_progress", "pending"]]];
        const [total, records, allTotal, openCount, overdueCount, pendingCount] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, INSPECTION_FIELDS, {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "scheduled_date desc, id desc",
            }),
            this.orm.searchCount(MODEL, []),
            this.orm.searchCount(MODEL, openDomain),
            this.orm.searchCount(MODEL, [["is_overdue", "=", true]]),
            this.orm.searchCount(MODEL, [["state", "=", "pending"]]),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = {
            total: allTotal,
            open: openCount,
            overdue: overdueCount,
            pending: pendingCount,
        };
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], INSPECTION_FIELDS);
        this.state.record = rows[0] || null;
        this.state.resId = id;
        if (!this.state.record) {
            this.state.error = "Inspection not found.";
            this.state.lines = [];
            this.state.findings = [];
            this.state.actions = [];
            return;
        }
        const [lines, findings] = await Promise.all([
            this.orm.searchRead(LINE_MODEL, [["inspection_id", "=", id]], LINE_FIELDS, { order: "sequence, id" }),
            this.orm.searchRead(FINDING_MODEL, [["inspection_id", "=", id]], FINDING_FIELDS, { order: "id desc" }),
        ]);
        this.state.lines = lines;
        this.state.findings = findings;
        const findingIds = findings.map((row) => row.id);
        this.state.actions = findingIds.length
            ? await this.orm.searchRead(ACTION_MODEL, [["finding_id", "in", findingIds]], ACTION_FIELDS, { order: "deadline, id" })
            : [];
        this.state.lineNotes = Object.fromEntries(lines.map((line) => [line.id, line.notes || ""]));
        this.state.findingForm = this.emptyFindingForm();
        this.state.form = {
            ...this.state.form,
            checklist_template_id: this.m2oId(this.state.record.checklist_template_id)
                ? String(this.m2oId(this.state.record.checklist_template_id))
                : "",
        };
        this.state.actionForm = {
            ...this.emptyActionForm(),
            finding_id: findingIds[0] ? String(findingIds[0]) : "",
            assigned_user_id: this.m2oId(this.state.record.assigned_user_id)
                ? String(this.m2oId(this.state.record.assigned_user_id))
                : "",
        };
        await this.loadAttachments();
    }

    async loadAttachments() {
        const inspectionIds = this.state.record?.attachment_ids || [];
        this.state.attachments = inspectionIds.length
            ? await this.orm.searchRead("ir.attachment", [["id", "in", inspectionIds]], ["name", "mimetype", "file_size"])
            : [];
        const lineMap = {};
        for (const line of this.state.lines) {
            const ids = line.attachment_ids || [];
            lineMap[line.id] = ids.length
                ? await this.orm.searchRead("ir.attachment", [["id", "in", ids]], ["name", "mimetype", "file_size"])
                : [];
        }
        this.state.lineAttachments = lineMap;
    }

    setMode(mode, resId = null) {
        this.state.mode = mode;
        this.state.resId = resId;
        this.state.error = "";
        this.state.page = mode === "list" ? this.state.page : 1;
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

    async createInspection() {
        if (!this.canCreate) {
            return;
        }
        if (!this.state.form.scheduled_date) {
            this.notification.add("Scheduled date is required.", { type: "danger" });
            return;
        }
        await this.withBusy("Creating inspection...", async () => {
            const ids = await this.orm.create(MODEL, [{
                inspection_type: this.state.form.inspection_type,
                scheduled_date: this.state.form.scheduled_date,
                property_id: this.toId(this.state.form.property_id),
                building_id: this.toId(this.state.form.building_id),
                area_id: this.toId(this.state.form.area_id),
                assigned_user_id: this.toId(this.state.form.assigned_user_id),
                checklist_template_id: this.toId(this.state.form.checklist_template_id),
                inspector_id: this.toId(this.state.form.inspector_id) || user.userId,
                location_detail: this.state.form.location_detail || false,
                notes: this.state.form.notes || false,
            }]);
            const id = Array.isArray(ids) ? ids[0] : ids;
            this.notification.add("Inspection scheduled.", { type: "success" });
            this.setMode("detail", id);
        });
    }

    async callWorkflow(method, extraArgs = []) {
        await this.withBusy("Updating inspection...", async () => {
            await this.orm.call(MODEL, method, [[this.state.resId], ...extraArgs]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Inspection updated.", { type: "success" });
        });
    }

    startInspection() {
        return this.callWorkflow("action_start_inspection");
    }

    completeInspection() {
        return this.callWorkflow("action_complete_inspection");
    }

    markCompleted() {
        return this.callWorkflow("action_mark_completed");
    }

    closeInspection() {
        return this.callWorkflow("action_close_inspection");
    }

    async applyChecklist() {
        const templateId = this.toId(this.state.form.checklist_template_id) || this.m2oId(this.inspection.checklist_template_id);
        if (!templateId) {
            this.notification.add("Select a checklist template first.", { type: "danger" });
            return;
        }
        await this.withBusy("Applying checklist...", async () => {
            if (templateId !== this.m2oId(this.inspection.checklist_template_id)) {
                await this.orm.write(MODEL, [this.state.resId], { checklist_template_id: templateId });
            }
            await this.orm.call(MODEL, "action_apply_checklist_template", [[this.state.resId]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Checklist applied.", { type: "success" });
        });
    }

    async setLineResult(line, result) {
        if (!this.canEditChecklist) {
            return;
        }
        const notes = this.state.lineNotes[line.id] ?? line.notes ?? "";
        await this.withBusy("Saving checklist...", async () => {
            await this.orm.call(MODEL, "action_update_checklist_line", [[this.state.resId], line.id, result, notes]);
            await this.loadRecord(this.state.resId);
        });
    }

    async saveLineNotes(line) {
        if (!this.canEditChecklist) {
            return;
        }
        const notes = this.state.lineNotes[line.id] ?? "";
        if ((line.notes || "") === notes) {
            return;
        }
        await this.withBusy("Saving notes...", async () => {
            if (line.result) {
                await this.orm.call(MODEL, "action_update_checklist_line", [[this.state.resId], line.id, line.result, notes]);
            } else {
                await this.orm.write(LINE_MODEL, [line.id], { notes });
            }
            await this.loadRecord(this.state.resId);
        });
    }

    async uploadAttachments(files, resModel, resId) {
        const ids = [];
        for (const file of files) {
            const datas = await fileToBase64(file);
            const created = await this.orm.create("ir.attachment", [{
                name: file.name,
                datas,
                res_model: resModel,
                res_id: resId,
                mimetype: file.type || "application/octet-stream",
            }]);
            ids.push(Array.isArray(created) ? created[0] : created);
        }
        return ids;
    }

    async onInspectionFiles(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        if (!files.length || !this.canOperate) {
            return;
        }
        await this.withBusy("Uploading evidence...", async () => {
            const ids = await this.uploadAttachments(files, MODEL, this.state.resId);
            await this.orm.write(MODEL, [this.state.resId], {
                attachment_ids: ids.map((id) => [4, id]),
            });
            await this.loadRecord(this.state.resId);
            this.notification.add("Evidence uploaded.", { type: "success" });
        });
    }

    async onLineFiles(line, ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        if (!files.length || !this.canEditChecklist) {
            return;
        }
        await this.withBusy("Uploading evidence...", async () => {
            const ids = await this.uploadAttachments(files, LINE_MODEL, line.id);
            await this.orm.write(LINE_MODEL, [line.id], {
                attachment_ids: ids.map((id) => [4, id]),
            });
            await this.loadRecord(this.state.resId);
            this.notification.add("Line evidence uploaded.", { type: "success" });
        });
    }

    async createFinding() {
        if (!this.canAddFinding) {
            return;
        }
        if (!this.state.findingForm.name.trim()) {
            this.notification.add("Finding title is required.", { type: "danger" });
            return;
        }
        await this.withBusy("Creating finding...", async () => {
            await this.orm.create(FINDING_MODEL, [{
                name: this.state.findingForm.name.trim(),
                inspection_id: this.state.resId,
                line_id: this.toId(this.state.findingForm.line_id),
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

    async callRecord(model, method, id, extraArgs = []) {
        await this.withBusy("Updating record...", async () => {
            await this.orm.call(model, method, [[id], ...extraArgs]);
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

registry.category("actions").add("fire_safety_management.action_inspections", FireSafetyInspections);
