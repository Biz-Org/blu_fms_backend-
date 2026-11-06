/** @odoo-module **/

import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { WeAnalytics } from "./screens/we_analytics";
import { WeApprovals } from "./screens/we_approvals";
import { WeBuilder } from "./screens/we_builder";
import { WeDashboard } from "./screens/we_dashboard";
import { WeNotifications } from "./screens/we_notifications";
import { WeTasks } from "./screens/we_tasks";
import { WeTemplates } from "./screens/we_templates";
import { extractError } from "./we_utils";

const SCREENS = [
    {
        id: "dashboard",
        label: "Workflow Engine Dashboard",
        icon: "fa-share-alt",
        title: "Workflow Engine Dashboard",
        subtitle: "Overview of workflow status, tasks, and system performance.",
        crumb: "Dashboard",
    },
    {
        id: "builder",
        label: "Workflow Builder",
        icon: "fa-sitemap",
        title: "Workflow Builder",
        subtitle: "Design and publish workflow versions.",
        crumb: "Builder",
    },
    {
        id: "templates",
        label: "Workflow Templates",
        icon: "fa-clone",
        title: "Workflow Templates",
        subtitle: "Browse and apply reusable workflow templates.",
        crumb: "Templates",
    },
    {
        id: "approvals",
        label: "Approval & Rule Management",
        icon: "fa-sliders",
        title: "Approval & Rule Management",
        subtitle: "Configure automated routing, escalation rules, and hierarchical sign-offs.",
        crumb: "Approval Rules",
    },
    {
        id: "tasks",
        label: "Task & Execution Management",
        icon: "fa-check-circle",
        title: "Task & Execution Management",
        subtitle: "Monitor, assign, and escalate workflow tasks.",
        crumb: "Tasks",
    },
    {
        id: "notifications",
        label: "Notifications & Approval Tracking",
        icon: "fa-bell-o",
        title: "Notifications & Approval Tracking",
        subtitle: "Manage pending requests and monitor system notifications.",
        crumb: "Approvals",
    },
    {
        id: "analytics",
        label: "Workflow Analytics & Reports",
        icon: "fa-bar-chart",
        title: "Workflow Analytics & Reports",
        subtitle: "Execution metrics, bottlenecks, and module usage from live data.",
        crumb: "Analytics",
    },
];

export class WorkflowEngineApp extends Component {
    static template = "workflow_engine.App";
    static props = ["*"];
    static components = {
        WeDashboard,
        WeBuilder,
        WeTemplates,
        WeApprovals,
        WeTasks,
        WeNotifications,
        WeAnalytics,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const initialScreen =
            this.props.action?.context?.we_screen ||
            this.props.action?.params?.screen ||
            "dashboard";
        this.screens = SCREENS;
        this.state = useState({
            taskSearch: "",
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
            sessionReady: true,
            sessionError: null,
        });
        onMounted(() => {
            if (document.getElementById("we-inter-font")) {
                return;
            }
            const link = document.createElement("link");
            link.id = "we-inter-font";
            link.rel = "stylesheet";
            link.href =
                "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap";
            document.head.appendChild(link);
        });
        onWillStart(async () => {
            try {
                const session = await this.orm.call(
                    "workflow.engine.ui.api",
                    "get_session_context",
                    []
                );
                this.state.session = session || this.state.session;
            } catch (err) {
                this.state.sessionError = extractError(err);
            }
        });
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
    }

    get isBuilder() {
        return this.state.screen === "builder";
    }

    get initials() {
        const name = this.state.session.name || "A";
        return name.trim().slice(0, 1).toUpperCase();
    }

    get roleLabel() {
        if (this.state.session.is_admin) {
            return "Administrator";
        }
        if (this.state.session.is_manager) {
            return "Workflow manager";
        }
        return "Workflow user";
    }

    onNavClick(ev) {
        const screen = ev.currentTarget.dataset.screen;
        this.navigate(screen);
    }

    navigate(screen) {
        if (screen && this.screens.some((item) => item.id === screen)) {
            this.state.screen = screen;
        }
    }
}

registry.category("actions").add("workflow_engine_app", WorkflowEngineApp);
