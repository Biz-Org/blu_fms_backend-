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

export class IotAutomation extends Component {
    static template = "integration_iot_management.Automation";
    static components = { IotAppShell, ...IOT_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            data: { rules: [], executions: [], lookups: {} },
            isAdmin: false,
            showRule: false,
            form: this.emptyForm(),
        });
        onWillStart(async () => {
            this.state.isAdmin = await user.hasGroup("integration_iot_management.group_integration_admin");
            await this.reload();
        });
    }

    emptyForm() {
        return {
            name: "",
            building_id: "",
            trigger_parameter: "temperature",
            operator: "gt",
            threshold: "26",
            action: "increase_hvac_cooling",
            action_value: "1",
            target_device_id: "",
            schedule_mode: "always",
            start: "00:00",
            end: "23:59",
            active: true,
        };
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("integration.iot.dashboard", "get_automation_data", []);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load automation.";
        } finally {
            this.state.loading = false;
        }
    }

    openCreate() {
        this.state.form = this.emptyForm();
        this.state.showRule = true;
    }

    async saveRule() {
        const form = this.state.form;
        try {
            await this.orm.create("integration.iot.automation.rule", [{
                name: form.name,
                building_id: form.building_id ? Number(form.building_id) : false,
                trigger_parameter: form.trigger_parameter,
                operator: form.operator,
                threshold: Number(form.threshold),
                action: form.action,
                action_value: Number(form.action_value || 0),
                target_device_id: form.target_device_id ? Number(form.target_device_id) : false,
                schedule_mode: form.schedule_mode,
                start_time: timeToFloat(form.start),
                end_time: timeToFloat(form.end),
                active: form.active === true || form.active === "true",
            }]);
            this.state.showRule = false;
            this.notification.add("Automation rule created", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save rule", { type: "danger" });
        }
    }

    async toggle(rule, active) {
        try {
            await this.orm.call("integration.iot.automation.rule", active ? "action_enable" : "action_disable", [rule.id]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Update failed", { type: "danger" });
        }
    }

    async override(row) {
        try {
            await this.orm.call("integration.iot.automation.execution", "action_manual_override", [row.id]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Override denied", { type: "danger" });
        }
    }

    operatorLabel(value) {
        return { gt: ">", gte: "≥", lt: "<", lte: "≤", eq: "=", neq: "≠" }[value] || value;
    }
}

registry.category("actions").add("integration_iot_management.action_automation", IotAutomation);
