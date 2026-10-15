import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { IotAppShell } from "@integration_iot_management/owl/ui/iot_shell";
import { IOT_COMPONENTS } from "@integration_iot_management/owl/ui/iot_ui";

export class IotEnergy extends Component {
    static template = "integration_iot_management.Energy";
    static components = { IotAppShell, ...IOT_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: "", data: null, isAdmin: false });
        onWillStart(async () => {
            this.state.isAdmin = await user.hasGroup("integration_iot_management.group_integration_admin");
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("integration.iot.dashboard", "get_energy_data", []);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load energy data.";
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || { kpis: {}, trend: [], by_location: [], opportunities: [], attention: [] };
    }

    get maxTrend() {
        return Math.max(1, ...(this.data.trend || []).map((row) => row.kwh));
    }

    barHeight(value) {
        return `${Math.max(6, (Number(value) / this.maxTrend) * 100)}%`;
    }

    get maxLocation() {
        return Math.max(1, ...(this.data.by_location || []).map((row) => row.kwh));
    }

    locWidth(value) {
        return `${Math.max(4, (Number(value) / this.maxLocation) * 100)}%`;
    }

    async applyOpportunity(row) {
        try {
            await this.orm.call("integration.iot.energy.opportunity", "action_apply", [row.id]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not apply opportunity", { type: "danger" });
        }
    }
}

registry.category("actions").add("integration_iot_management.action_energy", IotEnergy);
