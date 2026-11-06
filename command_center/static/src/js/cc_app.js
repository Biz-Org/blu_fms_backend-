/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { extractError } from "./cc_utils";
import { DashboardScreen } from "./screens/dashboard";
import { AlertsScreen } from "./screens/alerts";
import { MonitoringScreen } from "./screens/monitoring";
import { IncidentsScreen } from "./screens/incidents";
import { EmergencyScreen } from "./screens/emergency";
import { ReportsScreen } from "./screens/reports";
import { ReportBuilderScreen } from "./screens/report_builder";

const SCREENS = [
    {
        id: "dashboard",
        label: "Dashboard",
        icon: "fa-th-large",
        title: "Command Center Dashboard",
        crumb: "Dashboard",
        subtitle: "Centralized single-pane operational control.",
    },
    {
        id: "alerts",
        label: "Alerts",
        icon: "fa-bell",
        title: "Central Alert Management",
        crumb: "Alerts",
        subtitle: "Review and action operational alerts.",
    },
    {
        id: "monitoring",
        label: "Monitoring",
        icon: "fa-sitemap",
        title: "Multi-Site & Real-Time Monitoring",
        crumb: "Monitoring",
        subtitle: "Site status across the operational estate.",
    },
    {
        id: "incidents",
        label: "Incidents",
        icon: "fa-exclamation-triangle",
        title: "Incident Dashboard",
        crumb: "Incidents",
        subtitle: "Track and resolve operational incidents.",
    },
    {
        id: "emergency",
        label: "Emergency",
        icon: "fa-warning",
        title: "Emergency Alerts & Escalation",
        crumb: "Emergency",
        subtitle: "Emergency alerts and escalation handling.",
    },
    {
        id: "reports",
        label: "Reports",
        icon: "fa-bar-chart",
        title: "Command Center Reports",
        crumb: "Reports",
        subtitle: "Review command center operational records.",
    },
    {
        id: "report_builder",
        label: "Report Builder",
        icon: "fa-table",
        title: "Command Center Report Builder & Export",
        crumb: "Report Builder",
        subtitle: "Configure, run, and export command center reports.",
    },
];

export class CommandCenterApp extends Component {
    static template = "command_center.App";
    static props = ["*"];
    static components = {
        DashboardScreen,
        AlertsScreen,
        MonitoringScreen,
        IncidentsScreen,
        EmergencyScreen,
        ReportsScreen,
        ReportBuilderScreen,
    };

    setup() {
        this.orm = useService("orm");
        const initialScreen =
            this.props.action?.context?.cc_screen ||
            this.props.action?.params?.screen ||
            "dashboard";
        this.screens = SCREENS;
        this.state = useState({
            screen: SCREENS.some((item) => item.id === initialScreen)
                ? initialScreen
                : "dashboard",
            session: {
                uid: 0,
                name: "",
                is_user: false,
                is_manager: false,
                is_admin: false,
            },
            sessionError: null,
            menuOpen: false,
            topSearch: "",
            siteId: "",
            sites: [],
        });
        onWillStart(async () => {
            try {
                const session = await this.orm.call("cc.ui.api", "get_session_context", []);
                this.state.session = session || this.state.session;
            } catch (err) {
                this.state.sessionError = extractError(err);
            }
            try {
                const dash = await this.orm.call("cc.ui.api", "get_dashboard_data", []);
                this.state.sites = dash.sites_summary || [];
            } catch (err) {
                this.state.sites = [];
            }
        });
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
    }

    get searchPlaceholder() {
        if (this.state.screen === "alerts") {
            return "Search alerts...";
        }
        if (this.state.screen === "incidents") {
            return "Search incidents...";
        }
        if (this.state.screen === "emergency") {
            return "Search events...";
        }
        if (this.state.screen === "reports") {
            return "Search reports...";
        }
        if (this.state.screen === "report_builder") {
            return "Search...";
        }
        return "Search operational data...";
    }

    get initials() {
        const name = this.state.session.name || "U";
        return name.trim().slice(0, 1).toUpperCase();
    }

    get roleLabel() {
        if (this.state.session.is_admin) {
            return "Administrator";
        }
        if (this.state.session.is_manager) {
            return "Manager";
        }
        return "User";
    }

    onNavClick(ev) {
        const screen = ev.currentTarget.dataset.screen;
        this.navigate(screen);
        this.closeMenu();
    }

    toggleMenu() {
        this.state.menuOpen = !this.state.menuOpen;
    }

    closeMenu() {
        this.state.menuOpen = false;
    }

    navigate(screen) {
        if (screen && this.screens.some((item) => item.id === screen)) {
            this.state.screen = screen;
            this.state.menuOpen = false;
        }
    }

    onShellSearch() {
        this.state.topSearch = (this.state.topSearch || "").trim();
    }

    onShellSite() {
        this.state.siteId = this.state.siteId || "";
    }
}

registry.category("actions").add("command_center_app", CommandCenterApp);
