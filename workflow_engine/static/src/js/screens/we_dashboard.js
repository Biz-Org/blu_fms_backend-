/** @odoo-module **/

import { Component } from "@odoo/owl";

const RECENT_ACTIVITY = [
    {
        id: "mock-act-1",
        action: "complete",
        feed_text: "Workflow Invoice Processing completed",
        time: "10 mins ago",
    },
    {
        id: "mock-act-2",
        action: "failure",
        feed_text: "Execution failed for Data Sync Daily",
        time: "45 mins ago",
    },
];

export class WeDashboard extends Component {
    static template = "workflow_engine.Dashboard";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    get recentActivity() {
        return RECENT_ACTIVITY;
    }

    navigate(screenId) {
        if (typeof this.props.onNavigate === "function") {
            this.props.onNavigate(screenId);
        }
    }

    activityText(row) {
        return row.feed_text || row.name || "";
    }

    activityTime(row) {
        return row.time || "";
    }

    activityIcon(action) {
        if (action === "failure" || action === "reject") {
            return "fa-times-circle we-activity-icon-danger";
        }
        return "fa-check-circle we-activity-icon-success";
    }
}
