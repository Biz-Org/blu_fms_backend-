import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";

export class CommunityAnalytics extends CcAction {
    static template = "community_communication.Analytics";

    get defaultMode() {
        return "analytics";
    }

    async load() {
        if (!this.state.isOfficer) {
            this.openClient("community_communication.action_dashboard");
            return;
        }
        this.state.extras.days = this.state.extras.days || 30;
        this.state.extras.buildingId = this.state.extras.buildingId || false;
        this.state.extras.data = await this.orm.call(
            "community.communication.dashboard",
            "get_analytics_data",
            [this.state.extras.days, this.state.extras.buildingId || false]
        );
    }

    get data() {
        return this.state.extras.data || {
            trend: [],
            announcements: { most_viewed: [] },
            discussions: { categories: [] },
            feedback: {},
            polls: { bars: [] },
            events: {},
            by_building: [],
            insights: [],
            buildings: [],
        };
    }

    trendPoints(key) {
        const rows = this.data.trend || [];
        if (!rows.length) {
            return "";
        }
        const values = rows.map((row) => row[key] || 0);
        const max = Math.max(...values, 1);
        return values
            .map((value, index) => {
                const x = (index / Math.max(rows.length - 1, 1)) * 520 + 10;
                const y = 140 - (value / max) * 110;
                return `${x},${y}`;
            })
            .join(" ");
    }

    barHeight(value, rows) {
        const max = Math.max(...(rows || []).map((row) => row.value || 0), 1);
        return Math.max(8, Math.round((value / max) * 100));
    }

    onDays(ev) {
        this.state.extras.days = parseInt(ev.target.value, 10);
        this.reload();
    }

    onBuilding(ev) {
        this.state.extras.buildingId = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this.reload();
    }

    exportReport() {
        const d = this.data;
        this.exportRows("community_engagement.csv", [
            ["Metric", "Value"],
            ["Published announcements", d.announcements.published],
            ["Views", d.announcements.views],
            ["Ack rate", `${d.announcements.ack_rate}%`],
            ["Active threads", d.discussions.active],
            ["Feedback submitted", d.feedback.submitted],
            ["Feedback resolved", d.feedback.resolved],
            ["Poll participants", d.polls.participants],
            ["Event registrations", d.events.registrations],
            ["Attendance", `${d.events.attendance}%`],
        ]);
    }
}

registry.category("actions").add("community_communication.action_analytics", CommunityAnalytics);
