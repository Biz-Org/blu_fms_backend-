import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

const MODEL = "fire.safety.drill";
const PAGE_SIZE = 20;

const DRILL_FIELDS = [
    "name",
    "drill_type",
    "state",
    "scheduled_datetime",
    "conducted_by",
    "expected_participants",
    "target_participation",
    "description",
    "participant_ids",
    "attendance_count",
    "participation_rate",
    "response_time_minutes",
    "observations",
    "issues",
    "completed_datetime",
    "cancelled_reason",
    "property_id",
    "building_id",
    "area_id",
    "assigned_user_id",
];

const TYPE_LABELS = {
    fire_evacuation: "Fire Evacuation Drill",
    emergency_evacuation: "Emergency Evacuation Drill",
    disaster_preparedness: "Disaster Preparedness Drill",
    other: "Other",
};

const STATE_LABELS = {
    scheduled: "Upcoming",
    rescheduled: "Rescheduled",
    completed: "Completed",
    cancelled: "Cancelled",
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

function toDatetimeLocal(value) {
    if (!value) {
        return nowLocal();
    }
    return String(value).replace(" ", "T").slice(0, 16);
}

export class FireSafetyDrills extends Component {
    static template = "fire_safety_management.Drills";
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
            filter: "upcoming",
            typeFilter: "",
            page: 1,
            total: 0,
            records: [],
            kpis: { total: 0, upcoming: 0, completed: 0, cancelled: 0 },
            record: null,
            isSafetyManager: false,
            form: this.emptyForm(),
            completeForm: this.emptyCompleteForm(),
            rescheduleForm: { new_datetime: nowLocal(), reason: "" },
            cancelReason: "",
            lookups: { properties: [], buildings: [], areas: [], users: [] },
            participantQuery: "",
            participantResults: [],
            selectedParticipants: [],
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
            drill_type: "fire_evacuation",
            scheduled_datetime: nowLocal(),
            conducted_by: "Internal Safety Team",
            expected_participants: 0,
            target_participation: 100,
            assigned_user_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            description: "",
            participant_ids: [],
        };
    }

    emptyCompleteForm() {
        return {
            attendance_count: 0,
            response_time_minutes: 0,
            observations: "",
            issues: "",
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

    stateLabel(value) {
        return STATE_LABELS[value] || (value || "").replace(/_/g, " ");
    }

    stripHtml(html) {
        return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }

    formatRate(value) {
        return `${Number(value || 0).toFixed(1)}%`;
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

    get drill() {
        return this.state.record || {};
    }

    get isOpen() {
        return ["scheduled", "rescheduled"].includes(this.drill.state);
    }

    get canComplete() {
        return this.canOperate && this.isOpen;
    }

    get canReschedule() {
        return this.canOperate && this.drill.state === "scheduled";
    }

    get canConfirmSchedule() {
        return this.canOperate && this.drill.state === "rescheduled";
    }

    get canCancel() {
        return this.canOperate && this.isOpen;
    }

    get canNotify() {
        return this.canOperate && this.isOpen;
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

    get participantNames() {
        if (this.state.selectedParticipants.length) {
            return this.state.selectedParticipants.map((row) => row.name);
        }
        const ids = this.m2mIds(this.drill.participant_ids);
        const users = this.state.lookups.users || [];
        return ids.map((id) => users.find((row) => row.id === id)?.name || `#${id}`);
    }

    m2mIds(value) {
        if (!value) {
            return [];
        }
        if (!Array.isArray(value)) {
            return [Number(value)].filter(Boolean);
        }
        return value
            .map((item) => (Array.isArray(item) ? Number(item[0]) : Number(item)))
            .filter(Boolean);
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
                this.state.selectedParticipants = [];
                this.state.participantQuery = "";
                this.state.participantResults = [];
                await this.loadLookups();
                await this.searchParticipants("");
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
                [["active", "=", true], ["id", "!=", 1]],
                ["name", "login"],
                { limit: 120, order: "name" }
            );
        } catch {
            users = [];
        }
        this.state.lookups = { properties, buildings, areas, users };
        if (!this.state.selectedParticipants.length && users.length) {
            const selected = new Set(this.state.form.participant_ids.map(Number));
            this.state.selectedParticipants = users.filter((row) => selected.has(row.id));
        }
    }

    async ensureParticipantNames(ids) {
        const needed = this.m2mIds(ids);
        if (!needed.length) {
            this.state.selectedParticipants = [];
            return;
        }
        const known = new Map(this.state.selectedParticipants.map((row) => [row.id, row]));
        for (const row of this.state.lookups.users || []) {
            known.set(row.id, row);
        }
        const missing = needed.filter((id) => !known.has(id));
        if (missing.length) {
            try {
                const rows = await this.orm.searchRead(
                    "res.users",
                    [["id", "in", missing]],
                    ["name", "login"]
                );
                for (const row of rows) {
                    known.set(row.id, row);
                }
            } catch {
                /* keep known names only */
            }
        }
        this.state.selectedParticipants = needed.map((id) => known.get(id) || { id, name: `#${id}` });
        this.state.form.participant_ids = needed;
    }

    async onParticipantQuery(ev) {
        const query = (ev.target.value || "").trim();
        this.state.participantQuery = query;
        clearTimeout(this._participantSearchTimer);
        this._participantSearchTimer = setTimeout(() => this.searchParticipants(query), 200);
    }

    async searchParticipants(query) {
        const selected = new Set(this.state.form.participant_ids.map(Number));
        const domain = [["active", "=", true], ["id", "!=", 1]];
        if (query) {
            domain.push("|", ["name", "ilike", query], ["login", "ilike", query]);
        }
        try {
            const rows = await this.orm.searchRead("res.users", domain, ["name", "login"], {
                limit: 20,
                order: "name",
            });
            this.state.participantResults = rows.filter((row) => !selected.has(row.id));
        } catch (error) {
            this.state.participantResults = [];
            this.state.error = this.rpcMessage(error);
        }
    }

    addParticipant(usr) {
        const id = Number(usr.id);
        if (!id || this.state.form.participant_ids.map(Number).includes(id)) {
            return;
        }
        this.state.form.participant_ids = [...this.state.form.participant_ids.map(Number), id];
        this.state.selectedParticipants = [...this.state.selectedParticipants, usr];
        this.state.participantResults = this.state.participantResults.filter((row) => row.id !== id);
        this.state.participantQuery = "";
    }

    removeParticipant(id) {
        const number = Number(id);
        this.state.form.participant_ids = this.state.form.participant_ids
            .map(Number)
            .filter((value) => value !== number);
        this.state.selectedParticipants = this.state.selectedParticipants.filter(
            (row) => row.id !== number
        );
    }

    toggleParticipant(id) {
        const number = Number(id);
        if (this.state.form.participant_ids.map(Number).includes(number)) {
            this.removeParticipant(number);
            return;
        }
        const usr =
            (this.state.lookups.users || []).find((row) => row.id === number) ||
            this.state.participantResults.find((row) => row.id === number) ||
            { id: number, name: `#${number}` };
        this.addParticipant(usr);
    }

    isParticipantSelected(id) {
        return this.state.form.participant_ids.map(Number).includes(Number(id));
    }

    listDomain() {
        const domain = [];
        const search = (this.state.search || "").trim();
        if (search) {
            domain.push("|", ["name", "ilike", search], ["conducted_by", "ilike", search]);
        }
        if (this.state.typeFilter) {
            domain.push(["drill_type", "=", this.state.typeFilter]);
        }
        if (this.state.filter === "upcoming") {
            domain.push(["state", "in", ["scheduled", "rescheduled"]]);
        } else if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    async loadList() {
        const domain = this.listDomain();
        const [total, records, allTotal, scheduledCount, rescheduledCount, completedCount, cancelledCount] = await Promise.all([
            this.orm.searchCount(MODEL, domain),
            this.orm.searchRead(MODEL, domain, DRILL_FIELDS, {
                limit: this.pageSize,
                offset: (this.state.page - 1) * this.pageSize,
                order: "scheduled_datetime desc, id desc",
            }),
            this.orm.searchCount(MODEL, []),
            this.orm.searchCount(MODEL, [["state", "=", "scheduled"]]),
            this.orm.searchCount(MODEL, [["state", "=", "rescheduled"]]),
            this.orm.searchCount(MODEL, [["state", "=", "completed"]]),
            this.orm.searchCount(MODEL, [["state", "=", "cancelled"]]),
        ]);
        this.state.total = total;
        this.state.records = records;
        this.state.kpis = {
            total: allTotal,
            upcoming: scheduledCount + rescheduledCount,
            completed: completedCount,
            cancelled: cancelledCount,
        };
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], DRILL_FIELDS);
        this.state.record = rows[0] || null;
        this.state.resId = id;
        if (!this.state.record) {
            this.state.error = "Drill not found.";
            return;
        }
        this.state.completeForm = {
            attendance_count: this.state.record.attendance_count || 0,
            response_time_minutes: this.state.record.response_time_minutes || 0,
            observations: this.stripHtml(this.state.record.observations),
            issues: this.stripHtml(this.state.record.issues),
        };
        this.state.rescheduleForm = {
            new_datetime: toDatetimeLocal(this.state.record.scheduled_datetime),
            reason: "",
        };
        this.state.cancelReason = this.state.record.cancelled_reason || "";
        await this.ensureParticipantNames(this.state.record.participant_ids);
        this.state.participantQuery = "";
        this.state.participantResults = [];
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

    async createDrill() {
        if (!this.canCreate) {
            return;
        }
        if (!this.state.form.name.trim() || !this.state.form.scheduled_datetime || !this.state.form.conducted_by.trim()) {
            this.notification.add("Name, schedule, and conducted-by are required.", { type: "danger" });
            return;
        }
        await this.withBusy("Scheduling drill...", async () => {
            const created = await this.orm.create(MODEL, [{
                name: this.state.form.name.trim(),
                drill_type: this.state.form.drill_type,
                scheduled_datetime: fromDatetimeLocal(this.state.form.scheduled_datetime),
                conducted_by: this.state.form.conducted_by.trim(),
                expected_participants: Number(this.state.form.expected_participants) || 0,
                target_participation: Number(this.state.form.target_participation) || 100,
                assigned_user_id: this.toId(this.state.form.assigned_user_id) || user.userId,
                property_id: this.toId(this.state.form.property_id),
                building_id: this.toId(this.state.form.building_id),
                area_id: this.toId(this.state.form.area_id),
                description: this.state.form.description || false,
                participant_ids: [[6, 0, this.state.form.participant_ids.map(Number).filter(Boolean)]],
            }]);
            const id = Array.isArray(created) ? created[0] : created;
            const count = this.state.form.participant_ids.length;
            this.notification.add(
                count
                    ? `Mock drill scheduled. Community announcement sent to ${count} participant(s).`
                    : "Mock drill scheduled. Select participants and use Notify Participants to announce.",
                { type: "success" }
            );
            this.setMode("detail", id);
        });
    }

    async completeDrill() {
        if (!this.canComplete) {
            return;
        }
        await this.withBusy("Completing drill...", async () => {
            await this.orm.call(MODEL, "action_complete_drill", [[this.state.resId], {
                attendance_count: Number(this.state.completeForm.attendance_count) || 0,
                response_time_minutes: Number(this.state.completeForm.response_time_minutes) || 0,
                observations: this.state.completeForm.observations || false,
                issues: this.state.completeForm.issues || false,
            }]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Mock drill completed.", { type: "success" });
        });
    }

    async rescheduleDrill() {
        if (!this.canReschedule) {
            return;
        }
        const when = fromDatetimeLocal(this.state.rescheduleForm.new_datetime);
        if (!when) {
            this.notification.add("A new date and time are required to reschedule.", { type: "danger" });
            return;
        }
        await this.withBusy("Rescheduling drill...", async () => {
            const reason = (this.state.rescheduleForm.reason || "").trim();
            if (reason) {
                await this.orm.call(MODEL, "message_post", [[this.state.resId]], { body: reason });
            }
            await this.orm.call(MODEL, "action_reschedule_drill", [[this.state.resId], when]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Mock drill rescheduled.", { type: "success" });
        });
    }

    async confirmSchedule() {
        if (!this.canConfirmSchedule) {
            return;
        }
        await this.withBusy("Confirming schedule...", async () => {
            await this.orm.call(MODEL, "action_confirm_reschedule", [[this.state.resId]]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Schedule confirmed.", { type: "success" });
        });
    }

    async cancelDrill() {
        if (!this.canCancel) {
            return;
        }
        await this.withBusy("Cancelling drill...", async () => {
            await this.orm.call(MODEL, "action_cancel_drill", [[this.state.resId], this.state.cancelReason || false]);
            await this.loadRecord(this.state.resId);
            this.notification.add("Mock drill cancelled.", { type: "success" });
        });
    }

    async notifyParticipants() {
        if (!this.canNotify) {
            return;
        }
        if (!this.m2mIds(this.drill.participant_ids).length && !this.state.form.participant_ids.length) {
            this.notification.add("Select at least one participant before notifying.", { type: "warning" });
            return;
        }
        await this.withBusy("Notifying participants...", async () => {
            const current = this.m2mIds(this.drill.participant_ids).slice().sort((a, b) => a - b).join(",");
            const next = this.state.form.participant_ids
                .map(Number)
                .filter(Boolean)
                .slice()
                .sort((a, b) => a - b)
                .join(",");
            // Only write when the selection changed; avoid clearing the
            // "already notified" flag after Schedule Drill.
            if (next && next !== current) {
                await this.orm.write(MODEL, [this.state.resId], {
                    participant_ids: [[6, 0, this.state.form.participant_ids.map(Number).filter(Boolean)]],
                });
            }
            const result = await this.orm.call(MODEL, "action_notify_participants", [[this.state.resId]]);
            await this.loadRecord(this.state.resId);
            const status = result && result.status;
            const message =
                (result && result.message) ||
                (status === "already_notified"
                    ? "Participants were already notified for this mock drill."
                    : "Participants notified via Community Announcements.");
            this.notification.add(message, {
                type: status === "already_notified" ? "info" : status === "skipped" ? "warning" : "success",
            });
        });
    }

    async saveParticipants() {
        if (!this.canOperate || !this.state.resId) {
            return;
        }
        await this.withBusy("Updating participants...", async () => {
            await this.orm.write(MODEL, [this.state.resId], {
                participant_ids: [[6, 0, this.state.form.participant_ids.map(Number).filter(Boolean)]],
            });
            await this.loadRecord(this.state.resId);
            this.notification.add("Participants updated.", { type: "success" });
        });
    }
}

registry.category("actions").add("fire_safety_management.action_drills", FireSafetyDrills);
