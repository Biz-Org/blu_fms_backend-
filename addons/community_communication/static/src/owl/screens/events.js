import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { EVENT_CATEGORIES, labelOf, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "name", "category", "description", "state", "date_start", "date_end", "community_id",
    "building_id", "venue_id", "location", "require_registration", "date_deadline",
    "capacity", "reminder_enabled", "confirmed_count", "waitlist_count", "spots_available",
    "author_id", "attachment_ids", "audience_type", "building_ids", "audience_group_ids",
];

export class CommunityEvents extends CcAction {
    static template = "community_communication.Events";

    get staffOnlyModes() {
        return ["create", "edit", "attendees"];
    }

    get defaultMode() {
        const tag = this.props.action?.tag || "";
        return tag.includes("action_registrations") ? "attendees" : "calendar";
    }

    enforceResidentMode() {
        if (this.state.isOfficer) {
            return;
        }
        if (this.staffOnlyModes.includes(this.state.mode)) {
            this.state.mode = "calendar";
            this.state.resId = false;
        }
    }

    get shellActive() {
        return this.state.mode === "attendees" ? "registrations" : "events";
    }

    ensureCursor() {
        const now = new Date();
        const raw = this.state.extras.cursor;
        if (!raw || !Number.isFinite(raw.year) || !Number.isFinite(raw.month)) {
            this.state.extras.cursor = {
                year: now.getFullYear(),
                month: now.getMonth(),
                day: now.getDate(),
            };
            return;
        }
        if (!Number.isFinite(raw.day)) {
            this.state.extras.cursor = {
                year: raw.year,
                month: raw.month,
                day: raw.year === now.getFullYear() && raw.month === now.getMonth()
                    ? now.getDate()
                    : 1,
            };
        }
    }

    cursorDate() {
        this.ensureCursor();
        const raw = this.state.extras.cursor;
        return new Date(raw.year, raw.month, raw.day);
    }

    setCursor(date) {
        this.state.extras.cursor = {
            year: date.getFullYear(),
            month: date.getMonth(),
            day: date.getDate(),
        };
    }

    weekStart(date) {
        const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        start.setDate(start.getDate() - start.getDay());
        return start;
    }

    hasMine() {
        return Boolean(this.state.extras?.mine?.id);
    }

    registrationClosed(rec) {
        if (!rec?.date_deadline) {
            return false;
        }
        const deadline = new Date(rec.date_deadline);
        return !Number.isNaN(deadline.getTime()) && deadline.getTime() < Date.now();
    }

    canRegister(rec) {
        return Boolean(
            rec
            && rec.require_registration
            && rec.state === "published"
            && !this.hasMine()
            && !this.registrationClosed(rec)
        );
    }

    canUnregister(rec) {
        return Boolean(
            rec
            && rec.require_registration
            && rec.state === "published"
            && this.hasMine()
            && !this.registrationClosed(rec)
        );
    }

    mineStatus() {
        return this.hasMine() ? this.state.extras.mine.state : "Not registered";
    }

    localKey(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    eventDayKey(value) {
        if (!value) {
            return "";
        }
        const text = String(value);
        if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
            return text.slice(0, 10);
        }
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "" : this.localKey(date);
    }

    eventDateParts(event) {
        if (!event?.date_start) {
            return { month: "", day: "" };
        }
        const key = this.eventDayKey(event.date_start);
        const date = new Date(`${key}T00:00:00`);
        if (Number.isNaN(date.getTime())) {
            return { month: "", day: "" };
        }
        return {
            month: date.toLocaleString(undefined, { month: "short" }).toUpperCase(),
            day: String(date.getDate()),
        };
    }

    get categories() {
        return EVENT_CATEGORIES;
    }

    emptyForm() {
        return {
            name: "",
            category: "activities",
            description: "",
            community_id: this.defaultCommunityId(),
            venue_id: false,
            location: "",
            date_start: "",
            date_end: "",
            date_deadline: "",
            require_registration: true,
            capacity: 0,
            reminder_enabled: true,
            attachment_ids: [],
            pendingFiles: [],
            audience_type: "community",
            building_ids: [],
            audience_group_ids: [],
            buildingQuery: "",
            groupQuery: "",
        };
    }

    calendarDomain() {
        const domain = this.domainIlike("name");
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        return domain;
    }

    async load() {
        this.ensureCursor();
        if (["calendar", "week"].includes(this.state.mode) || this.state.mode === "attendees" && !this.state.resId) {
            this.state.records = await this.orm.searchRead(
                "community.communication.event",
                this.calendarDomain(),
                FIELDS,
                { limit: 200, order: "date_start asc" }
            );
            this.state.extras.upcoming = this.state.records.filter(
                (e) => e.state === "published" && e.date_start && new Date(e.date_start) >= new Date()
            ).slice(0, 5);
        }
        if (this.state.mode === "create") {
            this.state.form = this.emptyForm();
            await this.loadFormAttachments([]);
        }
        if (this.state.resId && ["detail", "edit", "rsvp", "attendees"].includes(this.state.mode)) {
            const rows = await this.orm.searchRead(
                "community.communication.event",
                [["id", "=", this.state.resId]],
                FIELDS
            );
            this.state.record = rows[0] || null;
            if (this.state.record) {
                const attachIds = this.m2mIds(this.state.record.attachment_ids);
                this.state.extras.attachments = attachIds.length
                    ? await this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype", "file_size"])
                    : [];
            }
            if (this.state.mode === "edit" && this.state.record) {
                this.state.form = this.formFromRecord(this.state.record);
                await this.loadFormAttachments(this.state.record.attachment_ids);
            }
            if (["rsvp", "detail"].includes(this.state.mode) && this.state.record) {
                this.state.extras.mine = await this.call(
                    "community.communication.event",
                    "get_my_registration",
                    [this.state.resId]
                ).catch(() => ({}));
                const residents = await this.orm.searchRead(
                    "community.communication.resident",
                    [["user_id", "=", this.state.userId]],
                    ["name", "email", "unit_id", "building_id"]
                );
                this.state.extras.me = residents[0] || null;
            }
            if (this.state.mode === "attendees") {
                this.state.extras.attendees = await this.orm.searchRead(
                    "community.communication.event.registration",
                    [["event_id", "=", this.state.resId]],
                    ["partner_name", "state", "registered_on", "unit_id", "waitlist_rank"],
                    { order: "registered_on desc" }
                );
            }
        }
    }

    formFromRecord(rec) {
        return {
            name: rec.name,
            category: rec.category,
            description: rec.description || "",
            community_id: this.m2oId(rec.community_id),
            venue_id: this.m2oId(rec.venue_id),
            location: rec.location || "",
            date_start: this.toDatetimeLocal(rec.date_start),
            date_end: this.toDatetimeLocal(rec.date_end),
            date_deadline: this.toDatetimeLocal(rec.date_deadline),
            require_registration: rec.require_registration,
            capacity: rec.capacity || 0,
            reminder_enabled: rec.reminder_enabled,
            attachment_ids: rec.attachment_ids || [],
            pendingFiles: [],
            audience_type: rec.audience_type || "community",
            building_ids: this.m2mIds(rec.building_ids),
            audience_group_ids: this.m2mIds(rec.audience_group_ids),
            buildingQuery: "",
            groupQuery: "",
        };
    }

    get calendarDays() {
        try {
            const cursor = this.cursorDate();
            const year = cursor.getFullYear();
            const month = cursor.getMonth();
            const first = new Date(year, month, 1);
            const start = new Date(year, month, 1 - first.getDay());
            const today = this.localKey(new Date());
            const days = [];
            for (let i = 0; i < 42; i++) {
                const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
                const key = this.localKey(date);
                days.push({
                    key: `${key}-${i}`,
                    num: date.getDate(),
                    muted: date.getMonth() !== month,
                    today: key === today,
                    events: (this.state.records || []).filter((ev) => this.eventDayKey(ev.date_start) === key),
                });
            }
            return days;
        } catch (_error) {
            return [];
        }
    }

    get weekDays() {
        const start = this.weekStart(this.cursorDate());
        const today = this.localKey(new Date());
        return Array.from({ length: 7 }, (_, i) => {
            const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
            const key = this.localKey(date);
            return {
                key: `${key}-w${i}`,
                label: date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
                today: key === today,
                events: (this.state.records || []).filter((ev) => this.eventDayKey(ev.date_start) === key),
            };
        });
    }

    monthLabel() {
        return this.cursorDate().toLocaleDateString(undefined, { month: "long", year: "numeric" });
    }

    periodLabel() {
        if (this.state.mode !== "week") {
            return this.monthLabel();
        }
        const start = this.weekStart(this.cursorDate());
        const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
        const startLabel = start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        const endLabel = end.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
        return `${startLabel} – ${endLabel}`;
    }

    shiftMonth(delta) {
        const cursor = this.cursorDate();
        this.setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + delta, 1));
        this.reload();
    }

    shiftWeek(delta) {
        const cursor = this.cursorDate();
        this.setCursor(new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + delta * 7));
        this.reload();
    }

    shiftPeriod(delta) {
        if (this.state.mode === "week") {
            this.shiftWeek(delta);
        } else {
            this.shiftMonth(delta);
        }
    }

    categoryLabel(key) {
        return labelOf(EVENT_CATEGORIES, key);
    }

    async save(publish) {
        return this.withBusy(publish ? "Publishing..." : "Saving...", async () => {
            const form = this.state.form;
            const errors = {};
            if (!(form.name || "").trim()) {
                errors.name = "Event name is required.";
            }
            if (!form.date_start) {
                errors.date_start = "Start date is required.";
            }
            if (!form.date_end) {
                errors.date_end = "End date is required.";
            }
            if (form.date_start && form.date_end && new Date(form.date_end) < new Date(form.date_start)) {
                errors.date_end = "End must be after the start.";
            }
            if (form.require_registration && form.date_deadline && form.date_start && new Date(form.date_deadline) > new Date(form.date_start)) {
                errors.date_deadline = "Registration deadline must be before the event start.";
            }
            this.validateAudience(errors, form);
            if (!this.setErrors(errors)) {
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            const vals = {
                name: form.name,
                category: form.category,
                description: form.description,
                community_id: this.defaultCommunityId(),
                venue_id: form.venue_id || false,
                location: form.location,
                date_start: this.fromDatetimeLocal(form.date_start),
                date_end: this.fromDatetimeLocal(form.date_end),
                date_deadline: form.require_registration ? this.fromDatetimeLocal(form.date_deadline) : false,
                require_registration: Boolean(form.require_registration),
                capacity: form.require_registration ? parseInt(form.capacity, 10) || 0 : 0,
                reminder_enabled: Boolean(form.reminder_enabled),
                ...this.audienceVals(form),
            };
            let id = this.state.resId;
            try {
                if (this.state.mode === "edit" && id) {
                    await this.orm.write("community.communication.event", [id], vals);
                } else {
                    id = (await this.orm.create("community.communication.event", [vals]))[0];
                }
                await this.persistAttachments("community.communication.event", id);
                if (publish) {
                    await this.call("community.communication.event", "action_publish", [id]);
                    this.notification.add("Event published", { type: "success" });
                } else {
                    this.notification.add("Draft saved", { type: "success" });
                }
                await this.setMode("detail", id);
            } catch (error) {
                if (!error?.data) {
                    await this.notifyError(error);
                }
            }
        });
    }

    async register() {
        return this.withBusy("Registering...", async () => {
            await this.call("community.communication.event", "action_register", [this.state.resId]);
            await this.reload();
            const mine = this.state.extras.mine || {};
            this.notification.add(
                mine.state === "waitlisted" ? "You are on the waitlist" : "Registration confirmed",
                { type: "success" }
            );
        });
    }

    async cancelMine() {
        return this.withBusy("Cancelling...", async () => {
            await this.call("community.communication.event", "action_unregister", [this.state.resId]);
            this.notification.add("Registration cancelled", { type: "success" });
            await this.reload();
        });
    }

    async publishEvent() {
        await this.call("community.communication.event", "action_publish", [this.state.resId]);
        this.notification.add("Event published", { type: "success" });
        await this.reload();
    }

    async cancelEvent() {
        await this.call("community.communication.event", "action_cancel", [this.state.resId]);
        this.reload();
    }

    async staffRegistrationAction(row, method) {
        return this.withBusy("Updating...", async () => {
            await this.call("community.communication.event.registration", method, [row.id]);
            this.notification.add("Registration updated", { type: "success" });
            await this.reload();
        });
    }

    capPct(rec) {
        if (!rec?.capacity) {
            return 0;
        }
        return Math.round(((rec.confirmed_count || 0) / rec.capacity) * 100);
    }

    previewBody() {
        return stripHtml(this.state.form.description || "").slice(0, 160);
    }

    eventTime(rec) {
        if (!rec?.date_start) {
            return "";
        }
        const start = new Date(rec.date_start);
        const end = rec.date_end ? new Date(rec.date_end) : null;
        const fmt = (d) => d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
        return end ? `${fmt(start)} - ${fmt(end)}` : fmt(start);
    }
}

registry.category("actions").add("community_communication.action_events", CommunityEvents);
registry.category("actions").add("community_communication.action_registrations", CommunityEvents);
