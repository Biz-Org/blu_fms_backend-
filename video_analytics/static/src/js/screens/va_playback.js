/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaPlayback extends Component {
    static template = "video_analytics.Playback";
    static props = VaScreenProps;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            filters: { search: "", state: "", severity: "", event_type: "", camera_id: "", zone_id: "", date_from: this._todayIso() },
            events: [],
            selected: null,
            assignable_users: [],
            cameras: [],
            zones: [],
            note: "",
            assignUserId: "",
            busy: false,
            kpis: {},
        });
        onWillStart(() => this.load());
    }

    applyFilters() {
        this.load();
    }

    clearFilters() {
        this.state.filters.search = "";
        this.state.filters.state = "";
        this.state.filters.severity = "";
        this.state.filters.event_type = "";
        this.state.filters.camera_id = "";
        this.state.filters.zone_id = "";
        this.state.filters.date_from = this._todayIso();
        this.load();
    }

    _todayIso() {
        const now = new Date();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return `${now.getFullYear()}-${month}-${day}`;
    }

    cameraLine(row) {
        if (!row) {
            return "—";
        }
        const code = row.camera_code || "";
        const loc = row.location_label || "";
        if (code && loc) {
            return `${code} (${loc})`;
        }
        return code || loc || row.camera_name || "—";
    }

    get hasYesterdayTrend() {
        const value = this.state.kpis && this.state.kpis.vs_yesterday;
        return value !== false && value !== null && value !== undefined;
    }

    get yesterdayTrendLabel() {
        const value = Number(this.state.kpis.vs_yesterday);
        if (!Number.isFinite(value)) {
            return "";
        }
        const sign = value > 0 ? "+" : "";
        return `${sign}${value}% vs yesterday`;
    }

    get trendClass() {
        const value = Number(this.state.kpis.vs_yesterday);
        if (value > 0) {
            return "va-kpi-hint va-text-success";
        }
        if (value < 0) {
            return "va-kpi-hint va-text-danger";
        }
        return "va-kpi-hint";
    }

    get dateChipLabel() {
        const raw = this.state.filters.date_from;
        if (!raw) {
            return "Select date";
        }
        const parts = String(raw).split("-").map((part) => Number(part));
        if (parts.length < 3 || !parts[0] || !parts[1] || !parts[2]) {
            return String(raw);
        }
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const month = months[parts[1] - 1] || "";
        const label = `${month} ${parts[2]}`;
        const now = new Date();
        if (now.getFullYear() === parts[0] && now.getMonth() + 1 === parts[1] && now.getDate() === parts[2]) {
            return `Today, ${label}`;
        }
        return `${label}, ${parts[0]}`;
    }

    get playbackRange() {
        const selected = this.state.selected;
        if (!selected) {
            return "— / —";
        }
        const start = this.formatTime(selected.playback_start);
        const end = this.formatTime(selected.playback_end);
        return `${start} / ${end}`;
    }

    async load(eventId) {
        const selectedId = typeof eventId === "number" ? eventId : (this.state.selected && this.state.selected.id) || false;
        const blocking = this.state.loading;
        this.state.error = null;
        try {
            const filters = {
                ...this.state.filters,
                event_id: selectedId,
                search: this.props.searchQuery || this.state.filters.search || "",
            };
            const data = await this.orm.call("va.ui.api", "get_playback_data", [filters]);
            this.state.events = data.events || [];
            this.state.selected = data.selected || null;
            this.state.assignable_users = data.assignable_users || [];
            this.state.cameras = data.cameras || [];
            this.state.zones = data.zones || [];
            this.state.kpis = data.kpis || {};
            if (this.state.selected && this.state.selected.user_id) {
                this.state.assignUserId = String(this.state.selected.user_id);
            }
        } catch (err) {
            this.state.error = extractError(err);
        }
        if (blocking) {
            this.state.loading = false;
        }
    }

    selectEvent(ev) {
        this.load(Number(ev.currentTarget.dataset.id));
    }

    async runAction(action, extra) {
        if (!this.state.selected) {
            return;
        }
        this.state.busy = true;
        this.state.error = null;
        try {
            await this.orm.call("va.ui.api", "run_event_action", [this.state.selected.id, action, extra || {}]);
            this.state.note = "";
            await this.load(this.state.selected.id);
            this.notification.add("Event updated.", { type: "success" });
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.busy = false;
    }

    onAck() { this.runAction("acknowledge"); }
    onInvestigate() { this.runAction("investigate"); }
    onAssign() {
        const userId = Number(this.state.assignUserId || this.props.session.uid);
        this.runAction("assign", { user_id: userId });
    }
    onAddNote() { this.runAction("add_note", { body: this.state.note }); }
    onFalsePositive() { this.runAction("false_positive", { note: this.state.note }); }
    onResolve() { this.runAction("resolve", { note: this.state.note }); }
    onClose() { this.runAction("close"); }

    get flow() {
        return this.workflowInfo(this.state.selected);
    }
}
