import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { CaAppShell } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

const TYPE_OPTIONS = [
    { value: "check", label: "Checks" },
    { value: "audit", label: "Audits" },
    { value: "document", label: "Documents" },
    { value: "nc", label: "Non-Compliance" },
    { value: "action", label: "Corrective Actions" },
    { value: "regulatory", label: "Regulatory" },
];

function localKey(date) {
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
}

function parseIso(value) {
    if (!value) {
        return null;
    }
    const [y, m, d] = String(value).slice(0, 10).split("-").map(Number);
    if (!y || !m || !d) {
        return null;
    }
    return new Date(y, m - 1, d);
}

export class ComplianceCalendar extends Component {
    static template = "compliance_audit_management.Calendar";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.typeOptions = TYPE_OPTIONS;
        const now = new Date();
        this.state = useState({
            loading: true,
            error: "",
            cursor: localKey(new Date(now.getFullYear(), now.getMonth(), 1)),
            types: TYPE_OPTIONS.map((opt) => opt.value),
            events: [],
            selectedDay: "",
        });
        onWillStart(async () => {
            await this.reload();
        });
    }

    get cursorDate() {
        return parseIso(this.state.cursor) || new Date();
    }

    get monthLabel() {
        return this.cursorDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    }

    get rangeBounds() {
        const cursor = this.cursorDate;
        const year = cursor.getFullYear();
        const month = cursor.getMonth();
        const first = new Date(year, month, 1);
        const start = new Date(year, month, 1 - first.getDay());
        const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 41);
        return { from: localKey(start), to: localKey(end) };
    }

    get calendarDays() {
        const cursor = this.cursorDate;
        const year = cursor.getFullYear();
        const month = cursor.getMonth();
        const first = new Date(year, month, 1);
        const start = new Date(year, month, 1 - first.getDay());
        const today = localKey(new Date());
        const byDate = {};
        for (const ev of this.state.events || []) {
            const key = String(ev.date || "").slice(0, 10);
            if (!byDate[key]) {
                byDate[key] = [];
            }
            byDate[key].push(ev);
        }
        const days = [];
        for (let i = 0; i < 42; i++) {
            const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
            const key = localKey(date);
            days.push({
                key: `${key}-${i}`,
                dateKey: key,
                num: date.getDate(),
                muted: date.getMonth() !== month,
                today: key === today,
                selected: key === this.state.selectedDay,
                events: byDate[key] || [],
            });
        }
        return days;
    }

    get selectedEvents() {
        const key = this.state.selectedDay;
        if (!key) {
            return [];
        }
        return (this.state.events || []).filter((ev) => String(ev.date || "").slice(0, 10) === key);
    }

    get upcomingEvents() {
        const today = localKey(new Date());
        return (this.state.events || [])
            .filter((ev) => String(ev.date || "").slice(0, 10) >= today)
            .slice(0, 8);
    }

    typeEnabled(value) {
        return this.state.types.includes(value);
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const { from, to } = this.rangeBounds;
            this.state.events = await this.orm.call("compliance.dashboard", "get_calendar_events", [
                from,
                to,
                this.state.types,
            ]);
        } catch (error) {
            this.state.events = [];
            this.state.error =
                error?.data?.message || error?.message || "Could not load calendar events.";
        } finally {
            this.state.loading = false;
        }
    }

    shiftMonth(delta) {
        const cursor = this.cursorDate;
        this.state.cursor = localKey(new Date(cursor.getFullYear(), cursor.getMonth() + delta, 1));
        this.state.selectedDay = "";
        this.reload();
    }

    goToday() {
        const now = new Date();
        this.state.cursor = localKey(new Date(now.getFullYear(), now.getMonth(), 1));
        this.state.selectedDay = localKey(now);
        this.reload();
    }

    toggleType(value) {
        const current = new Set(this.state.types);
        if (current.has(value)) {
            if (current.size === 1) {
                return;
            }
            current.delete(value);
        } else {
            current.add(value);
        }
        this.state.types = TYPE_OPTIONS.map((opt) => opt.value).filter((v) => current.has(v));
        this.reload();
    }

    selectDay(day) {
        this.state.selectedDay = day.dateKey;
    }

    formatDate(value) {
        const date = parseIso(value);
        if (!date) {
            return "—";
        }
        return date.toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    openEvent(ev) {
        if (!ev?.action_xmlid) {
            return;
        }
        if (String(ev.action_xmlid).endsWith("_ui")) {
            this.action.doAction(ev.action_xmlid, {
                additionalContext: {
                    ca_mode: "detail",
                    ca_res_id: ev.id,
                    active_id: ev.id,
                },
                clearBreadcrumbs: true,
                forceLeave: true,
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: ev.model,
            res_id: ev.id,
            views: [[false, "form"]],
            target: "current",
            name: ev.name,
        });
    }
}

registry.category("actions").add("compliance_audit_management.action_calendar", ComplianceCalendar);
