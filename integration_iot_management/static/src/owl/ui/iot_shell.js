import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

export const IOT_NAV = [
    {
        id: "dashboard",
        label: "Dashboard",
        icon: "fa-th-large",
        xmlid: "integration_iot_management.action_iot_dashboard_ui",
        tag: "integration_iot_management.action_dashboard",
    },
    {
        id: "systems",
        label: "Building Systems",
        icon: "fa-building-o",
        xmlid: "integration_iot_management.action_iot_lighting_ui",
        tag: "integration_iot_management.action_systems",
        children: [
            { id: "lighting", label: "Lighting", xmlid: "integration_iot_management.action_iot_lighting_ui" },
            { id: "hvac", label: "HVAC", xmlid: "integration_iot_management.action_iot_hvac_ui" },
            { id: "fire", label: "Fire Alarm", xmlid: "integration_iot_management.action_iot_fire_ui" },
            { id: "environment", label: "Environment", xmlid: "integration_iot_management.action_iot_environment_ui" },
        ],
    },
    {
        id: "devices_root",
        label: "Devices & Sensors",
        icon: "fa-rss",
        xmlid: "integration_iot_management.action_iot_devices_ui",
        tag: "integration_iot_management.action_devices",
        children: [
            { id: "devices", label: "Devices", xmlid: "integration_iot_management.action_iot_devices_ui" },
            { id: "sensors", label: "Sensors", xmlid: "integration_iot_management.action_iot_sensors_ui" },
        ],
    },
    {
        id: "automation",
        label: "Automation",
        icon: "fa-cogs",
        xmlid: "integration_iot_management.action_iot_automation_ui",
        tag: "integration_iot_management.action_automation",
    },
    {
        id: "energy",
        label: "Energy",
        icon: "fa-bolt",
        xmlid: "integration_iot_management.action_iot_energy_ui",
        tag: "integration_iot_management.action_energy",
    },
];

export class IotAppShell extends Component {
    static template = "integration_iot_management.IotAppShell";
    static props = {
        active: String,
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.user = user;
        this.state = useState({ isAdmin: false, isSystem: false });
        onWillStart(async () => {
            const [isAdmin, isSystem] = await Promise.all([
                user.hasGroup("integration_iot_management.group_integration_admin"),
                user.hasGroup("base.group_system"),
            ]);
            Object.assign(this.state, { isAdmin, isSystem });
        });
    }

    get nav() {
        return IOT_NAV;
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

    get canOpenSettings() {
        return this.state.isSystem || this.state.isAdmin;
    }

    get roleLabel() {
        return this.state.isAdmin ? "Integration Admin" : "Integration & IoT";
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
        this.action.doAction("integration_iot_management.action_iot_integration", {
            clearBreadcrumbs: true,
        });
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }
}
