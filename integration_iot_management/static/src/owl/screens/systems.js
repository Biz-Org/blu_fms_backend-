import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { IotAppShell } from "@integration_iot_management/owl/ui/iot_shell";
import { IOT_COMPONENTS } from "@integration_iot_management/owl/ui/iot_ui";

function timeToFloat(value) {
    if (!value) {
        return 0;
    }
    const [hours, minutes] = String(value).split(":").map(Number);
    return (hours || 0) + (minutes || 0) / 60;
}

function floatToTime(value) {
    const hours = Math.floor(Number(value) || 0);
    const minutes = Math.round(((Number(value) || 0) - hours) * 60);
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export class IotSystems extends Component {
    static template = "integration_iot_management.Systems";
    static components = { IotAppShell, ...IOT_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            tab: this.props.action?.context?.iot_tab || "lighting",
            loading: true,
            error: "",
            data: {},
            lookups: { buildings: [] },
            buildingFilter: "",
            showSchedule: false,
            isAdmin: false,
            schedule: this.emptySchedule(),
        });
        onWillStart(async () => {
            this.state.isAdmin = await user.hasGroup("integration_iot_management.group_integration_admin");
            this.state.lookups = await this.orm.call("integration.iot.dashboard", "get_lookups", []);
            await this.reload();
        });
    }

    emptySchedule() {
        return {
            name: "",
            building_id: "",
            lighting_action: "turn_on",
            start: "18:00",
            end: "23:00",
            active: true,
            day_mon: true, day_tue: true, day_wed: true, day_thu: true,
            day_fri: true, day_sat: true, day_sun: true,
        };
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("integration.iot.dashboard", "get_systems_data", [
                this.state.tab,
                this.state.buildingFilter || false,
            ]);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load building systems.";
        } finally {
            this.state.loading = false;
        }
    }

    setTab(tab) {
        this.state.tab = tab;
        this.reload();
    }

    onBuilding(ev) {
        this.state.buildingFilter = ev.target.value;
        this.reload();
    }

    async control(device, on) {
        try {
            const result = await this.orm.call("integration.iot.device", on ? "action_turn_on" : "action_turn_off", [device.id]);
            this.notification.add(result?.message || (on ? "Turned on" : "Turned off"), {
                type: result?.simulated ? "warning" : "success",
            });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Control failed", { type: "danger" });
        }
    }

    async setHvac(device) {
        const setpoint = Number(window.prompt("HVAC setpoint (°C)", device.hvac_setpoint || 24));
        if (Number.isNaN(setpoint)) {
            return;
        }
        try {
            const result = await this.orm.call("integration.iot.device", "action_set_hvac", [device.id], { setpoint });
            this.notification.add(result?.message || "HVAC updated", { type: result?.simulated ? "warning" : "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "HVAC update failed", { type: "danger" });
        }
    }

    async setFire(device, condition) {
        try {
            await this.orm.call("integration.iot.device", "action_set_fire_condition", [device.id, condition]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Update failed", { type: "danger" });
        }
    }

    openSchedule() {
        this.state.schedule = this.emptySchedule();
        this.state.showSchedule = true;
    }

    closeSchedule() {
        this.state.showSchedule = false;
    }

    async saveSchedule() {
        const form = this.state.schedule;
        try {
            await this.orm.call("integration.iot.schedule", "action_create_from_ui", [{
                name: form.name,
                system_kind: "lighting",
                building_id: form.building_id ? Number(form.building_id) : false,
                lighting_action: form.lighting_action,
                start_time: timeToFloat(form.start),
                end_time: timeToFloat(form.end),
                active: form.active === true || form.active === "true",
                day_mon: !!form.day_mon, day_tue: !!form.day_tue, day_wed: !!form.day_wed, day_thu: !!form.day_thu,
                day_fri: !!form.day_fri, day_sat: !!form.day_sat, day_sun: !!form.day_sun,
            }]);
            this.state.showSchedule = false;
            this.notification.add("Schedule created", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not create schedule", { type: "danger" });
        }
    }

    hourLabel(value) {
        return floatToTime(value);
    }
}

registry.category("actions").add("integration_iot_management.action_systems", IotSystems);
