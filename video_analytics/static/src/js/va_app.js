/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { extractError } from "./va_utils";
import { VaAlerts } from "./screens/va_alerts";
import { VaCctv } from "./screens/va_cctv";
import { VaDashboard } from "./screens/va_dashboard";
import { VaDetection } from "./screens/va_detection";
import { VaOccupancy } from "./screens/va_occupancy";
import { VaPlayback } from "./screens/va_playback";

const SCREENS = [
    // Sidebar lists only these six destinations.
    {
        id: "dashboard",
        label: "Video Analytics Dashboard",
        icon: "fa-th-large",
        title: "Video Analytics Dashboard",
        subtitle: "Overview of cameras, events, detections, and occupancy.",
        crumb: "Dashboard",
        searchPlaceholder: "Search cameras, events…",
    },
    {
        id: "cctv",
        label: "CCTV Integration & Live Streaming",
        icon: "fa-video-camera",
        title: "CCTV Integration & Live Streaming",
        subtitle: "Camera registry and stream metadata.",
        crumb: "CCTV",
        searchPlaceholder: "Search cameras…",
    },
    {
        id: "playback",
        label: "Video Event Playback & Investigation",
        icon: "fa-play-circle",
        title: "Event Playback & Investigation",
        subtitle: "Review events and investigation notes.",
        crumb: "Events",
        searchPlaceholder: "Search events…",
    },
    {
        id: "detection",
        label: "AI Detection & Zone Monitoring",
        icon: "fa-crosshairs",
        title: "AI Detection & Zone Monitoring",
        subtitle: "Zones, detection rules, and AI detections.",
        crumb: "AI Detection & Zone Monitoring",
        searchPlaceholder: "Search…",
    },
    {
        id: "occupancy",
        label: "Occupancy & Crowd Monitoring",
        icon: "fa-users",
        title: "Occupancy & Crowd Monitoring",
        subtitle: "Zone occupancy and crowd events.",
        crumb: "Occupancy",
        searchPlaceholder: "Search zones…",
    },
    {
        id: "alerts",
        label: "Video-Based Alerts & Event Management",
        icon: "fa-bell",
        title: "Video-Based Alerts & Event Management",
        subtitle: "Acknowledge, assign, and resolve events.",
        crumb: "Alerts",
        searchPlaceholder: "Search events…",
    },
];

export class VideoAnalyticsApp extends Component {
    static template = "video_analytics.App";
    static props = ["*"];
    static components = {
        VaDashboard,
        VaCctv,
        VaPlayback,
        VaDetection,
        VaOccupancy,
        VaAlerts,
    };

    setup() {
        this.orm = useService("orm");
        const initialScreen =
            this.props.action?.context?.va_screen ||
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
            searchQuery: "",
            menuOpen: false,
        });
        onWillStart(async () => {
            try {
                const session = await this.orm.call("va.ui.api", "get_session_context", []);
                this.state.session = session || this.state.session;
            } catch (err) {
                this.state.sessionError = extractError(err);
            }
        });
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
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
}

registry.category("actions").add("video_analytics_app", VideoAnalyticsApp);
