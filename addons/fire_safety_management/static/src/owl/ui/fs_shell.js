import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

export const FS_NAV = [
    { id: "dashboard", label: "Dashboard", icon: "fa-th-large", xmlid: "fire_safety_management.action_fs_dashboard_ui", tag: "fire_safety_management.action_dashboard" },
    { id: "inspections", label: "Inspections & Audits", icon: "fa-clipboard", xmlid: "fire_safety_management.action_fs_inspections_ui", tag: "fire_safety_management.action_inspections", hideForGuard: true },
    { id: "incidents", label: "Incidents", icon: "fa-exclamation-triangle", xmlid: "fire_safety_management.action_fs_incidents_ui", tag: "fire_safety_management.action_incidents" },
    { id: "drills", label: "Mock Drills", icon: "fa-bullhorn", xmlid: "fire_safety_management.action_fs_drills_ui", tag: "fire_safety_management.action_drills", hideForGuard: true },
    { id: "equipment", label: "Fire Equipment", icon: "fa-fire-extinguisher", xmlid: "fire_safety_management.action_fs_equipment_ui", tag: "fire_safety_management.action_equipment", hideForGuard: true },
    { id: "emergency", label: "Emergency Response", icon: "fa-bell", xmlid: "fire_safety_management.action_fs_emergency_ui", tag: "fire_safety_management.action_emergency" },
    { id: "reports", label: "Compliance Reports", icon: "fa-bar-chart", xmlid: "fire_safety_management.action_fs_reports_ui", tag: "fire_safety_management.action_reports", hideForGuard: true },
];

export class FsAppShell extends Component {
    static template = "fire_safety_management.FsAppShell";
    static props = {
        active: String,
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.user = user;
        this.state = useState({
            isSafetyManager: false,
            isSecurity: false,
            isGuard: false,
            isFacility: false,
            isAuditor: false,
            isExecutive: false,
            isSystem: false,
        });
        onWillStart(async () => {
            const [
                isSafetyManager,
                isSecurity,
                isGuard,
                isFacility,
                isAuditor,
                isExecutive,
                isSystem,
            ] = await Promise.all([
                user.hasGroup("fire_safety_management.group_fire_safety_manager"),
                user.hasGroup("fire_safety_management.group_fire_safety_security"),
                user.hasGroup("fire_safety_management.group_fire_safety_guard"),
                user.hasGroup("fire_safety_management.group_fire_safety_facility"),
                user.hasGroup("fire_safety_management.group_fire_safety_auditor"),
                user.hasGroup("fire_safety_management.group_fire_safety_executive"),
                user.hasGroup("base.group_system"),
            ]);
            Object.assign(this.state, {
                isSafetyManager,
                isSecurity,
                isGuard,
                isFacility,
                isAuditor,
                isExecutive,
                isSystem,
            });
        });
    }

    get nav() {
        const guardOnly = this.state.isGuard && !this.state.isSafetyManager && !this.state.isSecurity;
        if (guardOnly) {
            return FS_NAV.filter((item) => !item.hideForGuard);
        }
        return FS_NAV;
    }

    get canOpenSettings() {
        return this.state.isSystem || this.state.isSafetyManager;
    }

    get roleLabel() {
        if (this.state.isSafetyManager) {
            return "Safety Manager";
        }
        if (this.state.isSecurity) {
            return "Security";
        }
        if (this.state.isGuard) {
            return "Security Guard";
        }
        if (this.state.isFacility) {
            return "Facility Manager";
        }
        if (this.state.isAuditor) {
            return "Auditor";
        }
        if (this.state.isExecutive) {
            return "Management / CXO";
        }
        return "Fire & Safety";
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
        this.action.doAction("base_setup.action_general_configuration", {
            clearBreadcrumbs: true,
        });
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }
}
