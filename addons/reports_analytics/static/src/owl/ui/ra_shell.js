import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

export const RA_NAV = [
    { id: "dashboard", label: "Analytics Dashboard", icon: "fa-th-large", xmlid: "reports_analytics.action_ra_dashboard" },
    { id: "reports", label: "Reports", icon: "fa-file-text-o", xmlid: "reports_analytics.action_ra_reports" },
    { id: "builder", label: "Report Builder", icon: "fa-wrench", xmlid: "reports_analytics.action_ra_builder" },
    { id: "kpis", label: "Dashboards", icon: "fa-tachometer", xmlid: "reports_analytics.action_ra_kpis" },
    { id: "scheduled", label: "Scheduled Reports", icon: "fa-clock-o", xmlid: "reports_analytics.action_ra_scheduled" },
    {
        id: "analytics",
        label: "Analytics",
        icon: "fa-line-chart",
        xmlid: "reports_analytics.action_ra_operational",
        children: [
            { id: "operational", label: "Operational", xmlid: "reports_analytics.action_ra_operational" },
            { id: "financial", label: "Financial", xmlid: "reports_analytics.action_ra_financial" },
            { id: "trends", label: "Trend Analysis", xmlid: "reports_analytics.action_ra_trends" },
            { id: "cross", label: "Cross-Module", xmlid: "reports_analytics.action_ra_cross_module" },
            { id: "predictive", label: "Predictive", xmlid: "reports_analytics.action_ra_predictive" },
        ],
    },
    { id: "library", label: "Report Library", icon: "fa-folder-open-o", xmlid: "reports_analytics.action_ra_library" },
    { id: "alerts", label: "Analytics Alerts", icon: "fa-bell-o", xmlid: "reports_analytics.action_ra_alerts" },
];

export class RaAppShell extends Component {
    static template = "reports_analytics.RaAppShell";
    static props = {
        active: String,
        slots: { type: Object, optional: true },
        onNewAnalysis: { type: Function, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.user = user;
        this.state = useState({ canConfigure: false });
        onWillStart(async () => {
            this.state.canConfigure = await user.hasGroup("reports_analytics.group_analytics_admin");
        });
    }

    get nav() {
        return RA_NAV;
    }

    isActive(item) {
        if (item.id === this.props.active) {
            return true;
        }
        return (item.children || []).some((child) => child.id === this.props.active);
    }

    childActive(child) {
        return child.id === this.props.active;
    }

    get avatarUrl() {
        return `/web/image/res.users/${user.userId}/avatar_128`;
    }

    open(item) {
        this.action.doAction(item.xmlid, { clearBreadcrumbs: true, forceLeave: true });
    }

    openProfile() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            res_id: user.userId,
            views: [[false, "form"]],
            target: "new",
            name: "User Profile",
        });
    }

    openSettings() {
        this.action.doAction("reports_analytics.action_analytics_data_source", { clearBreadcrumbs: true });
    }

    openSupport() {
        this.action.doAction("reports_analytics.action_analytics_audit_log");
    }

    newAnalysis() {
        this.props.onNewAnalysis?.();
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }
}
