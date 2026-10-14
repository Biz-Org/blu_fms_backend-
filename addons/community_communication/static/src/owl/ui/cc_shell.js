import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

export const CC_NAV = [
    { id: "dashboard", label: "Dashboard", icon: "fa-th-large", xmlid: "community_communication.action_community_dashboard", tag: "community_communication.action_dashboard" },
    { id: "announcements", label: "Announcements", icon: "fa-bullhorn", xmlid: "community_communication.action_cc_announcement_ui", tag: "community_communication.action_announcements" },
    { id: "discussions", label: "Discussion Forums", icon: "fa-comments", xmlid: "community_communication.action_cc_discussion_ui", tag: "community_communication.action_discussions" },
    { id: "polls", label: "Polls", icon: "fa-bar-chart", xmlid: "community_communication.action_cc_poll_ui", tag: "community_communication.action_polls" },
    { id: "events", label: "Event Calendar", icon: "fa-calendar", xmlid: "community_communication.action_cc_event_ui", tag: "community_communication.action_events" },
    { id: "notices", label: "Community Notices", icon: "fa-thumb-tack", xmlid: "community_communication.action_cc_notice_ui", tag: "community_communication.action_notices" },
    { id: "feedback", label: "Resident Feedback", icon: "fa-commenting-o", xmlid: "community_communication.action_cc_feedback_ui", tag: "community_communication.action_feedback" },
    { id: "groups", label: "Community Groups", icon: "fa-users", xmlid: "community_communication.action_cc_group_ui", tag: "community_communication.action_groups" },
    { id: "registrations", label: "Event Registration", icon: "fa-check-square-o", xmlid: "community_communication.action_cc_registration_ui", tag: "community_communication.action_registrations", staffOnly: true },
    { id: "analytics", label: "Engagement Analytics", icon: "fa-line-chart", xmlid: "community_communication.action_community_analytics", tag: "community_communication.action_analytics", staffOnly: true },
];

export class CcAppShell extends Component {
    static template = "community_communication.CcAppShell";
    static props = {
        active: String,
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.user = user;
        this.state = useState({ isOfficer: false, mobileNavOpen: false });
        onWillStart(async () => {
            this.state.isOfficer = await user.hasGroup("community_communication.group_community_officer");
        });
    }

    toggleMobileNav() {
        this.state.mobileNavOpen = !this.state.mobileNavOpen;
    }

    closeMobileNav() {
        this.state.mobileNavOpen = false;
    }

    get nav() {
        if (this.state.isOfficer) {
            return CC_NAV;
        }
        return CC_NAV.filter((item) => !item.staffOnly);
    }

    get avatarUrl() {
        return `/web/image/res.users/${user.userId}/avatar_128`;
    }

    get initials() {
        const name = user.name || "";
        const parts = name.trim().split(/\s+/);
        return ((parts[0] || "U")[0] + (parts[1] || "")[0]).toUpperCase();
    }

    open(item) {
        this.closeMobileNav();
        this.action.doAction({
            type: "ir.actions.client",
            tag: item.tag,
            name: item.label,
            target: "current",
        }, { clearBreadcrumbs: true });
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
        this.action.doAction("base_setup.action_general_configuration", {
            clearBreadcrumbs: true,
        });
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }
}
