import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CommunityDashboard extends Component {
    static template = "community_communication.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        onWillStart(async () => {
            this.state.data = await this.orm.call(
                "community.communication.dashboard",
                "get_dashboard_data",
                []
            );
        });
    }

    get data() {
        return this.state.data || {
            kpis: {},
            overview: {},
            engagement: [],
            upcoming_events: [],
            activity: [],
            active_polls: [],
        };
    }

    get donut() {
        const { published = 0, scheduled = 0, expired = 0 } = this.data.overview;
        const total = published + scheduled + expired || 1;
        const c = 2 * Math.PI * 36;
        const p = (published / total) * c;
        const s = (scheduled / total) * c;
        const e = (expired / total) * c;
        return { total, published, scheduled, expired, p, s, e, c, offsetP: 0, offsetS: p, offsetE: p + s };
    }

    get linePoints() {
        const rows = this.data.engagement || [];
        if (!rows.length) {
            return "";
        }
        const values = rows.map((row) => row.announcements + row.discussions + row.polls);
        const max = Math.max(...values, 1);
        return values
            .map((value, index) => {
                const x = (index / Math.max(rows.length - 1, 1)) * 280 + 10;
                const y = 110 - (value / max) * 90;
                return `${x},${y}`;
            })
            .join(" ");
    }

    openAnnouncements() {
        this.action.doAction("community_communication.action_cc_announcement");
    }
    createAnnouncement() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "community.communication.announcement",
            views: [[false, "form"]],
            target: "current",
        });
    }
    openRecord(row) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: row.model,
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openEvents() {
        this.action.doAction("community_communication.action_cc_event");
    }
    openPolls() {
        this.action.doAction("community_communication.action_cc_poll");
    }
    createEvent() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "community.communication.event",
            views: [[false, "form"]],
            target: "current",
        });
    }
    stateClass(state) {
        if (["published", "active", "confirmed", "resolved"].includes(state)) {
            return "success";
        }
        if (["scheduled", "pending", "submitted", "waitlisted"].includes(state)) {
            return "warning";
        }
        if (["expired", "cancelled", "closed"].includes(state)) {
            return "danger";
        }
        return "muted";
    }
}

registry.category("actions").add("community_communication.action_dashboard", CommunityDashboard);
