import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const MODEL = "fire.safety.emergency";
const EVENT_MODEL = "fire.safety.emergency.event";
const PAGE_SIZE = 20;

const EMERGENCY_FIELDS = [
    "name",
    "emergency_type",
    "severity",
    "state",
    "location_detail",
    "information",
    "response_team",
    "activation_datetime",
    "closed_datetime",
    "outcome",
    "activated_by_id",
    "property_id",
    "building_id",
    "area_id",
];

const EVENT_FIELDS = ["event_datetime", "name", "description", "user_id", "emergency_id"];

const TYPE_LABELS = {
    fire: "Fire",
    smoke: "Smoke",
    gas_leak: "Gas Leak",
    electrical: "Electrical Emergency",
    evacuation: "Evacuation",
    other: "Other",
};

const SEVERITY_LABELS = {
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",
};

const STATE_LABELS = {
    active: "Active",
    closed: "Closed",
};

function pad(value) {
    return String(value).padStart(2, "0");
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

function toHtml(value) {
    const text = String(value || "").trim();
    if (!text) {
        return false;
    }
    if (text.startsWith("<")) {
        return text;
    }
    return `<p>${text.replace(/</g, "&lt;")}</p>`;
}

export class FireSafetyEmergency extends Component {
    static template = "fire_safety_management.Emergency";
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
            kpis: { total: 0, active: 0, closed: 0 },
            record: null,
            events: [],
            isSafetyManager: false,
            isSecurity: false,
            form: this.emptyForm(),
            eventForm: this.emptyEventForm(),
            closeOutcome: "",
            lookups: { properties: [], buildings: [], areas: [] },
        });
        onWillStart(async () => {
            const [isSafetyManager, isSecurity] = await Promise.all([
                user.hasGroup("fire_safety_management.group_fire_safety_manager"),
                user.hasGroup("fire_safety_management.group_fire_safety_security"),
            ]);
            this.state.isSafetyManager = isSafetyManager;
            this.state.isSecurity = isSecurity;
            const ctx = this.props.action?.context || {};
            const mode = ctx.fs_mode || "list";
            const resId = ctx.fs_res_id || ctx.active_id || null;
            if (mode === "create" && this.canActivate) {
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
            emergency_type: "fire",
            severity: "high",
            activation_datetime: nowLocal(),
            location_detail: "",
            information: "",
            response_team: "",
            property_id: "",
            building_id: "",
            area_id: "",
        };
    }

    emptyEventForm() {
        return {
            name: "",
            description: "",
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

    severityLabel(value) {
        return SEVERITY_LABELS[value] || value || "—";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ");
    }

    severityTone(value) {
        if (value === "critical" || value === "high") {
            return "danger";
        }
        if (value === "medium") {
            return "warning";
        }
        return "muted";
    }

    stripHtml(html) {
        return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return String(value);
        }
        return date.toLocaleString();
    }

    get types() {
        return Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));
    }

    get canActivate() {
        return this.state.isSafetyManager || this.state.isSecurity;
    }

    get canClose() {
        return this.state.isSafetyManager && this.emergency.state === "active";
    }

    get canAddEvent() {
        return this.canActivate && this.emergency.state === "active";
    }

    get hasActive() {
        return Boolean(this.state.kpis.active);
    }

    get emergency() {
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
                await Promise.all([this.loadLookups(), this.loadKpis()]);
            } else if (this.state.resId) {
                await Promise.all([this.loadLookups(), this.loadKpis(), this.loadRecord(this.state.resId)]);
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
        this.state.lookups = { properties, buildings, areas };
    }

    async loadKpis() {
        const [allTotal, activeCount, closedCount] = await Promise.all([
            this.orm.searchCount(MODEL, []),
            this.orm.searchCount(MODEL, [["state", "=", "active"]]),
            this.orm.searchCount(MODEL, [["state", "=", "closed"]]),
        ]);
        this.state.kpis = { total: allTotal, active: activeCount, closed: closedCount };
    }

    listDomain() {
        const domain = [];
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", "|", ["name", "ilike", search], ["location_detail", "ilike", search], ["information", "ilike", search]);
        }
        if (this.state.typeFilter) {
            domain.push(["emergency_type", "=", this.state.typeFilter]);
        }
        if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    async loadList() {
        const domain = this.listDomain();
        const [total, records] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, EMERGENCY_FIELDS, {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "activation_datetime desc, id desc",
            }),
            this.loadKpis(),
        ]);
        this.state.total = total;
        this.state.records = records;
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], EMERGENCY_FIELDS);
        this.state.record = rows[0] || null;
        this.state.resId = id;
        this.state.closeOutcome = this.stripHtml(this.state.record?.outcome);
        if (!this.state.record) {
            this.state.error = "Emergency not found.";
            this.state.events = [];
            return;
        }
        this.state.events = await this.orm.searchRead(
            EVENT_MODEL,
            [["emergency_id", "=", id]],
            EVENT_FIELDS,
            { order: "event_datetime desc, id desc" }
        );
        this.state.eventForm = this.emptyEventForm();
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

    async activateEmergency() {
        if (!this.canActivate) {
            return;
        }
        if (this.hasActive) {
            this.notification.add("Only one active emergency is allowed per company. Close the current emergency first.", { type: "danger" });
            return;
        }
        if (!this.state.form.emergency_type || !this.state.form.severity) {
            this.notification.add("Type and severity are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Activating emergency...", async () => {
            const result = await this.orm.call(MODEL, "action_activate_emergency", [{
                emergency_type: this.state.form.emergency_type,
                severity: this.state.form.severity,
                activation_datetime: fromDatetimeLocal(this.state.form.activation_datetime) || false,
                location_detail: this.state.form.location_detail || false,
                information: toHtml(this.state.form.information),
                response_team: this.state.form.response_team || false,
                property_id: this.toId(this.state.form.property_id),
                building_id: this.toId(this.state.form.building_id),
                area_id: this.toId(this.state.form.area_id),
            }]);
            const id = Array.isArray(result) ? result[0] : (result && typeof result === "object" ? result.id : result);
            this.notification.add("Emergency activated.", { type: "success" });
            this.setMode("detail", id);
        });
    }

    async addEvent() {
        if (!this.canAddEvent) {
            return;
        }
        if (!this.state.eventForm.name.trim()) {
            this.notification.add("Timeline event name is required.", { type: "danger" });
            return;
        }
        await this.withBusy("Recording timeline...", async () => {
            await this.orm.create(EVENT_MODEL, [{
                emergency_id: this.state.resId,
                name: this.state.eventForm.name.trim(),
                description: this.state.eventForm.description || false,
                user_id: user.userId,
            }]);
            this.state.eventForm = this.emptyEventForm();
            await this.loadRecord(this.state.resId);
            this.notification.add("Timeline event recorded.", { type: "success" });
        });
    }

    async closeEmergency() {
        if (!this.canClose) {
            return;
        }
        if (!this.state.closeOutcome.trim()) {
            this.notification.add("Record an outcome before closing the emergency.", { type: "danger" });
            return;
        }
        await this.withBusy("Closing emergency...", async () => {
            await this.orm.call(MODEL, "action_close_emergency", [[this.state.resId], toHtml(this.state.closeOutcome)]);
            await Promise.all([this.loadKpis(), this.loadRecord(this.state.resId)]);
            this.notification.add("Emergency closed.", { type: "success" });
        });
    }
}

registry.category("actions").add("fire_safety_management.action_emergency", FireSafetyEmergency);
