import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { IotAppShell } from "@integration_iot_management/owl/ui/iot_shell";
import { IOT_COMPONENTS } from "@integration_iot_management/owl/ui/iot_ui";

export class IotDashboard extends Component {
    static template = "integration_iot_management.Dashboard";
    static components = { IotAppShell, ...IOT_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: "", data: null });
        onWillStart(() => this.reload());
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("integration.iot.dashboard", "get_dashboard_data", []);
        } catch (error) {
            this.state.data = null;
            this.state.error = error?.data?.message || error?.message || "Could not load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || {
            kpis: {},
            systems: {},
            environment: {},
            energy: { trend: [] },
            attention: [],
            activity: [],
        };
    }

    get kpis() {
        return this.data.kpis || {};
    }

    get maxTrend() {
        const values = (this.data.energy?.trend || []).map((row) => row.kwh);
        return Math.max(1, ...values);
    }

    barHeight(value) {
        return `${Math.max(6, (Number(value) / this.maxTrend) * 100)}%`;
    }

    formatWhen(value) {
        if (!value) {
            return "";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    envValue(key, fallback = "—") {
        const row = this.data.environment?.[key];
        if (!row || row.value === false || row.value === null || row.value === undefined) {
            return fallback;
        }
        return `${row.value}${row.unit ? " " + row.unit : ""}`;
    }

    openSystems(tab) {
        const xmlid = {
            lighting: "integration_iot_management.action_iot_lighting_ui",
            hvac: "integration_iot_management.action_iot_hvac_ui",
            fire: "integration_iot_management.action_iot_fire_ui",
            environment: "integration_iot_management.action_iot_environment_ui",
        }[tab];
        this.action.doAction(xmlid, { clearBreadcrumbs: true, forceLeave: true });
    }

    openDevices() {
        this.action.doAction("integration_iot_management.action_iot_devices_ui", { clearBreadcrumbs: true, forceLeave: true });
    }

    openAutomation() {
        this.action.doAction("integration_iot_management.action_iot_automation_ui", { clearBreadcrumbs: true, forceLeave: true });
    }

    openEnergy() {
        this.action.doAction("integration_iot_management.action_iot_energy_ui", { clearBreadcrumbs: true, forceLeave: true });
    }
}

registry.category("actions").add("integration_iot_management.action_dashboard", IotDashboard);
