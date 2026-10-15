import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const MODEL = "fire.safety.equipment";
const HISTORY_MODEL = "fire.safety.equipment.history";
const PAGE_SIZE = 20;

const EQUIPMENT_FIELDS = [
    "name",
    "code",
    "equipment_type",
    "location_detail",
    "install_date",
    "inspection_due_date",
    "service_due_date",
    "expiry_date",
    "condition",
    "state",
    "last_inspection_date",
    "last_service_date",
    "notes",
    "property_id",
    "building_id",
    "area_id",
    "assigned_user_id",
];

const HISTORY_FIELDS = ["event_type", "event_date", "summary", "notes", "performed_by_id", "equipment_id"];

const TYPE_LABELS = {
    fire_extinguisher: "Fire Extinguishers",
    fire_hydrant: "Fire Hydrants",
    fire_hose: "Fire Hoses",
    fire_alarm: "Fire Alarms",
    smoke_detector: "Smoke Detectors",
    sprinkler: "Sprinklers",
    fire_pump: "Fire Pumps",
    emergency_light: "Emergency Lights",
    fire_door: "Fire Doors",
    exit_sign: "Emergency Exit Signs",
};

const CONDITION_LABELS = {
    operational: "Operational",
    under_maintenance: "Under Maintenance",
    faulty: "Faulty",
    replaced: "Replaced",
};

const STATE_LABELS = {
    operational: "Operational",
    inspection_due: "Inspection Due",
    service_due: "Service Due",
    under_maintenance: "Under Maintenance",
    faulty: "Faulty",
    expired: "Expired",
    replaced: "Replaced",
};

const EVENT_LABELS = {
    service: "Service",
    inspection: "Inspection",
    replacement: "Replacement",
    fault: "Fault",
};

const DUE_STATES = ["inspection_due", "service_due", "expired"];

function pad(value) {
    return String(value).padStart(2, "0");
}

function todayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export class FireSafetyEquipment extends Component {
    static template = "fire_safety_management.Equipment";
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
            kpis: { total: 0, due: 0, operational: 0, expired: 0 },
            record: null,
            history: [],
            isSafetyManager: false,
            form: this.emptyForm(),
            historyForm: this.emptyHistoryForm(),
            lookups: { properties: [], buildings: [], areas: [], users: [] },
        });
        onWillStart(async () => {
            this.state.isSafetyManager = await user.hasGroup(
                "fire_safety_management.group_fire_safety_manager"
            );
            const ctx = this.props.action?.context || {};
            const mode = ctx.fs_mode || "list";
            const resId = ctx.fs_res_id || ctx.active_id || null;
            if (mode === "create" && this.canCreate) {
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
            name: "",
            code: "",
            equipment_type: "fire_extinguisher",
            condition: "operational",
            install_date: "",
            inspection_due_date: "",
            service_due_date: "",
            expiry_date: "",
            location_detail: "",
            assigned_user_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            notes: "",
        };
    }

    emptyHistoryForm() {
        return {
            event_type: "service",
            event_date: todayIso(),
            summary: "",
            notes: "",
        };
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

    conditionLabel(value) {
        return CONDITION_LABELS[value] || value || "—";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ");
    }

    eventLabel(value) {
        return EVENT_LABELS[value] || value || "—";
    }

    stripHtml(html) {
        return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }

    formatDate(value) {
        return value ? String(value).slice(0, 10) : "—";
    }

    get types() {
        return Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));
    }

    get canCreate() {
        return this.state.isSafetyManager;
    }

    get canOperate() {
        return this.state.isSafetyManager;
    }

    get equipment() {
        return this.state.record || {};
    }

    get canMarkOperational() {
        return this.canOperate && this.equipment.condition && this.equipment.condition !== "operational";
    }

    get canMarkMaintenance() {
        return this.canOperate && this.equipment.condition !== "under_maintenance" && this.equipment.condition !== "replaced";
    }

    get canMarkFaulty() {
        return this.canOperate && this.equipment.condition !== "faulty" && this.equipment.condition !== "replaced";
    }

    get canMarkReplaced() {
        return this.canOperate && this.equipment.condition !== "replaced";
    }

    get canAddHistory() {
        return this.canOperate;
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

    get pageFrom() {
        return this.state.total ? (this.state.page - 1) * this.pageSize + 1 : 0;
    }

    get pageTo() {
        return Math.min(this.state.page * this.pageSize, this.state.total);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.state.total / this.pageSize));
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
            domain.push("|", "|", ["name", "ilike", search], ["code", "ilike", search], ["location_detail", "ilike", search]);
        }
        if (this.state.typeFilter) {
            domain.push(["equipment_type", "=", this.state.typeFilter]);
        }
        if (this.state.filter === "due") {
            domain.push(["state", "in", DUE_STATES]);
        } else if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    async loadList() {
        const domain = this.listDomain();
        const [total, records, allTotal, dueCount, operationalCount, expiredCount] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, EQUIPMENT_FIELDS, {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "code, name",
            }),
            this.orm.searchCount(MODEL, []),
            this.orm.searchCount(MODEL, [["state", "in", DUE_STATES]]),
            this.orm.searchCount(MODEL, [["state", "=", "operational"]]),
            this.orm.searchCount(MODEL, [["state", "=", "expired"]]),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = {
            total: allTotal,
            due: dueCount,
            operational: operationalCount,
            expired: expiredCount,
        };
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], EQUIPMENT_FIELDS);
        this.state.record = rows[0] || null;
        this.state.resId = id;
        if (!this.state.record) {
            this.state.error = "Equipment not found.";
            this.state.history = [];
            return;
        }
        this.state.history = await this.orm.searchRead(
            HISTORY_MODEL,
            [["equipment_id", "=", id]],
            HISTORY_FIELDS,
            { order: "event_date desc, id desc" }
        );
        this.state.historyForm = this.emptyHistoryForm();
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

    async createEquipment() {
        if (!this.canCreate) {
            return;
        }
        if (!this.state.form.name.trim() || !this.state.form.code.trim()) {
            this.notification.add("Name and code are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Creating equipment...", async () => {
            const created = await this.orm.create(MODEL, [{
                name: this.state.form.name.trim(),
                code: this.state.form.code.trim(),
                equipment_type: this.state.form.equipment_type,
                condition: this.state.form.condition,
                install_date: this.state.form.install_date || false,
                inspection_due_date: this.state.form.inspection_due_date || false,
                service_due_date: this.state.form.service_due_date || false,
                expiry_date: this.state.form.expiry_date || false,
                location_detail: this.state.form.location_detail || false,
                assigned_user_id: this.toId(this.state.form.assigned_user_id) || user.userId,
                property_id: this.toId(this.state.form.property_id),
                building_id: this.toId(this.state.form.building_id),
                area_id: this.toId(this.state.form.area_id),
                notes: this.state.form.notes || false,
            }]);
            const id = Array.isArray(created) ? created[0] : created;
            this.notification.add("Equipment recorded.", { type: "success" });
            this.setMode("detail", id);
        });
    }

    async callCondition(method, label) {
        if (!this.canOperate) {
            return;
        }
        await this.withBusy(label, async () => {
            await this.orm.call(MODEL, method, [[this.state.resId]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Equipment condition updated.", { type: "success" });
        });
    }

    markOperational() {
        return this.callCondition("action_mark_operational", "Marking operational...");
    }

    markMaintenance() {
        return this.callCondition("action_mark_under_maintenance", "Marking under maintenance...");
    }

    markFaulty() {
        return this.callCondition("action_mark_faulty", "Marking faulty...");
    }

    markReplaced() {
        return this.callCondition("action_mark_replaced", "Marking replaced...");
    }

    async addHistory() {
        if (!this.canAddHistory) {
            return;
        }
        if (!this.state.historyForm.summary.trim() || !this.state.historyForm.event_date) {
            this.notification.add("History summary and date are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Recording history...", async () => {
            await this.orm.create(HISTORY_MODEL, [{
                equipment_id: this.state.resId,
                event_type: this.state.historyForm.event_type,
                event_date: this.state.historyForm.event_date,
                summary: this.state.historyForm.summary.trim(),
                notes: this.state.historyForm.notes || false,
                performed_by_id: user.userId,
            }]);
            this.state.historyForm = this.emptyHistoryForm();
            await this.loadRecord(this.state.resId);
            this.notification.add("Service history recorded.", { type: "success" });
        });
    }
}

registry.category("actions").add("fire_safety_management.action_equipment", FireSafetyEquipment);
