import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
export class CommunityAnalytics extends Component {
    static template = "community_communication.Analytics";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ days: 30, buildingId: false, data: null });
        onWillStart(() => this.reload());
    }

    async reload() {
        this.state.data = await this.orm.call(
            "community.communication.dashboard",
            "get_analytics_data",
            [this.state.days, this.state.buildingId || false]
        );
    }

    onDaysChange(ev) {
        this.state.days = parseInt(ev.target.value, 10);
        this.reload();
    }

    onBuildingChange(ev) {
        this.state.buildingId = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this.reload();
    }

    get data() {
        return this.state.data || {
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
        const max = Math.max(...rows.map((row) => row.value || 0), 1);
        return Math.max(8, Math.round((value / max) * 100));
    }

    exportReport() {
        const d = this.data;
        const lines = [
            ["Metric", "Value"],
            ["Published announcements", d.announcements.published],
            ["Views", d.announcements.views],
            ["Ack rate", d.announcements.ack_rate + "%"],
            ["Active threads", d.discussions.active],
            ["Feedback submitted", d.feedback.submitted],
            ["Feedback resolved", d.feedback.resolved],
            ["Poll participants", d.polls.participants],
            ["Event registrations", d.events.registrations],
            ["Attendance", d.events.attendance + "%"],
        ];
        const csv = lines.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "community_engagement.csv";
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("community_communication.action_analytics", CommunityAnalytics);
