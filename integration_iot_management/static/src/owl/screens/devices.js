import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { IotAppShell } from "@integration_iot_management/owl/ui/iot_shell";
import { IOT_COMPONENTS } from "@integration_iot_management/owl/ui/iot_ui";

export class IotDevices extends Component {
    static template = "integration_iot_management.Devices";
    static components = { IotAppShell, ...IOT_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            tab: this.props.action?.context?.iot_tab || "devices",
            loading: true,
            error: "",
            data: {},
            lookups: {},
            search: "",
            status: "",
            isAdmin: false,
            showDevice: false,
            showSensor: false,
            ingest: { sensor_id: "", value: "" },
            deviceForm: this.emptyDevice(),
            sensorForm: this.emptySensor(),
        });
        onWillStart(async () => {
            this.state.isAdmin = await user.hasGroup("integration_iot_management.group_integration_admin");
            await this.reload();
        });
    }

    emptyDevice() {
        return {
            name: "",
            device_type: "lighting",
            integration_id: "",
            property_id: "",
            building_id: "",
            area_id: "",
            control_supported: true,
        };
    }

    emptySensor() {
        return { name: "", device_id: "", parameter: "temperature", unit: "°C", min_threshold: "", max_threshold: "" };
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("integration.iot.dashboard", "get_devices_data", [
                this.state.tab,
                this.state.search,
                this.state.status,
            ]);
            this.state.lookups = this.state.data.lookups || {};
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load devices.";
        } finally {
            this.state.loading = false;
        }
    }

    setTab(tab) {
        this.state.tab = tab;
        this.reload();
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        this.reload();
    }

    onStatus(ev) {
        this.state.status = ev.target.value;
        this.reload();
    }

    async saveDevice() {
        const form = this.state.deviceForm;
        try {
            await this.orm.create("integration.iot.device", [{
                name: form.name,
                device_type: form.device_type,
                integration_id: form.integration_id ? Number(form.integration_id) : false,
                property_id: form.property_id ? Number(form.property_id) : false,
                building_id: form.building_id ? Number(form.building_id) : false,
                area_id: form.area_id ? Number(form.area_id) : false,
                control_supported: !!form.control_supported,
                status: "online",
            }]);
            this.state.showDevice = false;
            this.notification.add("Device registered", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not register device", { type: "danger" });
        }
    }

    async saveSensor() {
        const form = this.state.sensorForm;
        try {
            await this.orm.create("integration.iot.sensor", [{
                name: form.name,
                device_id: Number(form.device_id),
                parameter: form.parameter,
                unit: form.unit,
                min_threshold: form.min_threshold === "" ? 0 : Number(form.min_threshold),
                max_threshold: form.max_threshold === "" ? 0 : Number(form.max_threshold),
            }]);
            this.state.showSensor = false;
            this.notification.add("Sensor configured", { type: "success" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save sensor", { type: "danger" });
        }
    }

    async ingestReading() {
        try {
            await this.orm.call("integration.iot.reading", "ingest_reading", [
                Number(this.state.ingest.sensor_id),
                Number(this.state.ingest.value),
            ]);
            this.notification.add("Reading stored (simulated source unless a live adapter exists)", { type: "warning" });
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Invalid reading", { type: "danger" });
        }
    }

    async toggleDevice(row, activate) {
        try {
            await this.orm.call("integration.iot.device", activate ? "action_activate" : "action_deactivate", [row.id]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Update failed", { type: "danger" });
        }
    }

    async archiveDevice(row) {
        try {
            await this.orm.call("integration.iot.device", "action_archive", [row.id]);
            await this.reload();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Archive failed", { type: "danger" });
        }
    }
}

registry.category("actions").add("integration_iot_management.action_devices", IotDevices);
