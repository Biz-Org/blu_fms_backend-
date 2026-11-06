/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaAlerts extends Component {
    static template = "video_analytics.Alerts";
    static props = VaScreenProps;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            filters: { state: "", severity: "", event_type: "", camera_id: "", zone_id: "", user_id: "", window: "24h" },
            kpis: {},
            events: [],
            selected: null,
            assignable_users: [],
            cameras: [],
            zones: [],
            note: "",
            assignUserId: "",
            busy: false,
        });
        onWillStart(() => this.load());
    }

    locationLine(row) {
        if (!row) {
            return "—";
        }
        const left = row.location_label || row.zone_name;
        const right = row.camera_code || row.camera_name;
        if (left && right) {
            return `${left} / ${right}`;
        }
        return left || right || "—";
    }

    windowDateFrom() {
        const window = this.state.filters.window;
        if (window === "24h") {
            return new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 19).replace("T", " ");
        }
        if (window === "7d") {
            return new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString().slice(0, 19).replace("T", " ");
        }
        return "";
    }

    applyFilters() {
        this.load();
    }

    async load(eventId) {
        const selectedId = typeof eventId === "number" ? eventId : (this.state.selected && this.state.selected.id) || false;
        const blocking = this.state.loading;
        this.state.error = null;
        try {
            const filters = {
                ...this.state.filters,
                event_id: selectedId,
                date_from: this.windowDateFrom(),
            };
            const data = await this.orm.call("va.ui.api", "get_alerts_data", [filters]);
            this.state.kpis = data.kpis || {};
            this.state.events = data.events || [];
            this.state.selected = data.selected || null;
            this.state.assignable_users = data.assignable_users || [];
            this.state.cameras = data.cameras || [];
            this.state.zones = data.zones || [];
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
    onAssign() { this.runAction("assign", { user_id: Number(this.state.assignUserId || this.props.session.uid) }); }
    onAddNote() { this.runAction("add_note", { body: this.state.note }); }
    onResolve() { this.runAction("resolve", { note: this.state.note }); }
    onClose() { this.runAction("close"); }
    onFalsePositive() { this.runAction("false_positive", { note: this.state.note }); }
    onReopen() { this.runAction("reopen"); }

    get flow() {
        return this.workflowInfo(this.state.selected);
    }
}
