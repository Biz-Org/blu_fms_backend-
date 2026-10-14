import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { statusTone } from "@community_communication/owl/utils";

export class CommunityDashboard extends CcAction {
    static template = "community_communication.Dashboard";

    get defaultMode() {
        return "dashboard";
    }

    async load() {
        this.state.extras.data = await this.orm.call(
            "community.communication.dashboard",
            "get_dashboard_data",
            []
        );
    }

    get data() {
        return this.state.extras.data || {
            kpis: {},
            overview: {},
            engagement: [],
            upcoming_events: [],
            activity: [],
            active_polls: [],
        };
    }

    get donut() {
        const { published = 0, scheduled = 0, expired = 0 } = this.data.overview || {};
        const total = published + scheduled + expired || 1;
        const c = 2 * Math.PI * 36;
        const p = (published / total) * c;
        const s = (scheduled / total) * c;
        const e = (expired / total) * c;
        return { published, scheduled, expired, p, s, e, c, offsetS: p, offsetE: p + s };
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

    activityWhen(row) {
        return this.formatDay(row.date);
    }

    eventDateParts(event) {
        const label = (event.date_label || "").trim();
        const bits = label.split(/\s+/);
        if (bits.length >= 2) {
            return { month: bits[0], day: bits[1] };
        }
        if (event.date) {
            const date = new Date(event.date);
            return {
                month: date.toLocaleString(undefined, { month: "short" }).toUpperCase(),
                day: String(date.getDate()),
            };
        }
        return { month: "", day: "" };
    }

    createAnnouncement() {
        this.openClient("community_communication.action_announcements", { mode: "create" });
    }
    openAnnouncements() {
        this.openClient("community_communication.action_announcements");
    }
    openDiscussions() {
        this.openClient("community_communication.action_discussions");
    }
    openPolls() {
        this.openClient("community_communication.action_polls");
    }
    openActivePoll(poll) {
        this.openClient("community_communication.action_polls", {
            mode: this.state.isOfficer ? "results" : "vote",
            resId: poll.id,
        });
    }
    openEvents() {
        this.openClient("community_communication.action_events");
    }
    openFeedback() {
        this.openClient("community_communication.action_feedback");
    }
    createEvent() {
        this.openClient("community_communication.action_events", { mode: "create" });
    }
    openRecord(row) {
        const map = {
            "community.communication.announcement": "community_communication.action_announcements",
            "community.communication.discussion": "community_communication.action_discussions",
            "community.communication.poll": "community_communication.action_polls",
            "community.communication.feedback": "community_communication.action_feedback",
            "community.communication.event": "community_communication.action_events",
        };
        const tag = map[row.model];
        if (tag) {
            this.openClient(tag, { mode: "detail", resId: row.id });
        }
    }
    stateClass(state) {
        return statusTone(state);
    }
}

registry.category("actions").add("community_communication.action_dashboard", CommunityDashboard);
