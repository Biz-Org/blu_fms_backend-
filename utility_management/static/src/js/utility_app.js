/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SCREENS = [
    { id: "utility_dashboard", label: "Dashboard", icon: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" },
    { id: "utility_meter_inventory", label: "Meter Inventory", icon: "M7 3h10v18H7zM9 8h6M9 12h6M9 16h4" },
    { id: "utility_electricity_monitoring", label: "Electricity Monitoring", icon: "M13 2L4 14h7l-1 8 10-14h-7z" },
    { id: "utility_water_monitoring", label: "Water Monitoring", icon: "M12 3s6 6.2 6 10a6 6 0 1 1-12 0c0-3.8 6-10 6-10z" },
    { id: "utility_gas_monitoring", label: "Gas Monitoring", icon: "M12 3c2 3 4 5.2 4 8.2a4 4 0 1 1-8 0C8 8.2 10 6 12 3z" },
    { id: "utility_power_source", label: "Power Source Dashboard", icon: "M9 3v6H5l7 12v-6h4z" },
    { id: "utility_overall_consumption", label: "Overall Consumption Dashboard", icon: "M4 19V9M10 19V5M16 19v-7M22 19H2" },
    { id: "utility_meter_reading", label: "Meter Reading", icon: "M8 3h8v18H8zM10 8h4M10 12h4M10 16h2" },
    { id: "utility_leak_detection", label: "Leak Detection", icon: "M12 3c2.4 3 5 5.4 5 9a5 5 0 1 1-10 0c0-3.6 2.6-6 5-9z" },
    { id: "utility_alerts", label: "Utility Alerts", icon: "M6 9a6 6 0 1 1 12 0c0 4 2 5 2 5H4s2-1 2-5zM10 19a2 2 0 0 0 4 0" },
    { id: "utility_reports", label: "Utility Reports", icon: "M7 3h7l5 5v13H7zM14 3v5h5" },
    { id: "utility_settings", label: "Settings", icon: "M12 8a4 4 0 1 0 .01 8.01A4 4 0 0 0 12 8zM12 2v3M12 19v3M2 12h3M19 12h3" },
];

export const SOURCE_SCREENS = [
    { id: "smart_meter_dashboard", title: "Smart Meter Dashboard", parent: "utility_dashboard" },
    { id: "meter_inventory", title: "Meter Inventory", parent: "utility_meter_inventory" },
    { id: "add_configure_meter", title: "Add/Configure Meter", parent: "utility_meter_inventory" },
    { id: "meter_details", title: "Meter Details & Connectivity History", parent: "utility_meter_inventory" },
    { id: "electricity_monitoring", title: "Electricity Monitoring", parent: "utility_electricity_monitoring" },
    { id: "electricity_buildings", title: "Real-Time / Building-wise Electricity", parent: "utility_electricity_monitoring" },
    { id: "electricity_trends", title: "Electricity Consumption Details & Trends", parent: "utility_electricity_monitoring" },
    { id: "water_dashboard", title: "Water Monitoring Dashboard", parent: "utility_water_monitoring" },
    { id: "water_tanks", title: "Tank & Distribution Monitoring", parent: "utility_water_monitoring" },
    { id: "water_trends", title: "Water Consumption Details & Trends", parent: "utility_water_monitoring" },
    { id: "gas_monitoring", title: "Gas Monitoring", parent: "utility_gas_monitoring" },
    { id: "gas_safety", title: "Gas Meter & Safety Monitoring", parent: "utility_gas_monitoring" },
    { id: "gas_trends", title: "Gas Consumption Details & Trends", parent: "utility_gas_monitoring" },
    { id: "power_dashboard", title: "Power Source Dashboard", parent: "utility_power_source" },
    { id: "power_grid", title: "Grid & Generator Monitoring", parent: "utility_power_source" },
    { id: "power_history", title: "Power Source History & Usage", parent: "utility_power_source" },
    { id: "consumption_dashboard", title: "Overall Consumption Dashboard", parent: "utility_overall_consumption" },
    { id: "consumption_analysis", title: "Consumption Details / Analysis", parent: "utility_overall_consumption" },
    { id: "consumption_comparison", title: "Consumption Comparison & Trends", parent: "utility_overall_consumption" },
    { id: "reading_list", title: "Meter Reading List", parent: "utility_meter_reading" },
    { id: "reading_form", title: "Add/Record Meter Reading", parent: "utility_meter_reading" },
    { id: "reading_detail", title: "Meter Reading Details", parent: "utility_meter_reading" },
    { id: "leak_dashboard", title: "Leak Detection Dashboard", parent: "utility_leak_detection" },
    { id: "leak_list", title: "Active Leak / Incident List", parent: "utility_leak_detection" },
    { id: "leak_detail", title: "Leak Incident Details", parent: "utility_leak_detection" },
    { id: "alert_dashboard", title: "Utility Alerts Dashboard", parent: "utility_alerts" },
    { id: "alert_list", title: "Alerts List", parent: "utility_alerts" },
    { id: "alert_detail", title: "Alert Details", parent: "utility_alerts" },
    { id: "report_dashboard", title: "Utility Reports Dashboard", parent: "utility_reports" },
    { id: "report_builder", title: "Report Builder", parent: "utility_reports" },
    { id: "report_detail", title: "Report Detail", parent: "utility_reports" },
];

const DEFAULT_PAGE = {
    utility_dashboard: "smart_meter_dashboard",
    utility_meter_inventory: "meter_inventory",
    utility_electricity_monitoring: "electricity_monitoring",
    utility_water_monitoring: "water_dashboard",
    utility_gas_monitoring: "gas_monitoring",
    utility_power_source: "power_dashboard",
    utility_overall_consumption: "consumption_dashboard",
    utility_meter_reading: "reading_list",
    utility_leak_detection: "leak_dashboard",
    utility_alerts: "alert_dashboard",
    utility_reports: "report_dashboard",
    utility_settings: "settings",
};

const METER_NEXT = {
    connecting: ["online", "offline", "error"],
    online: ["offline", "error", "maintenance", "connecting", "deactivated"],
    offline: ["connecting", "online", "error", "maintenance", "deactivated"],
    error: ["connecting", "maintenance", "deactivated", "online"],
    maintenance: ["connecting", "online", "deactivated"],
    deactivated: ["connecting"],
};

const POWER_NEXT = {
    grid_active: ["grid_outage", "generator_active"],
    grid_outage: ["generator_active", "power_restored"],
    generator_standby: ["generator_active", "generator_fault"],
    generator_active: ["generator_standby", "generator_fault", "power_restored"],
    generator_fault: ["generator_standby", "generator_active"],
    power_restored: ["grid_active"],
};

const LEAK_NEXT = {
    detected: ["investigating", "action_required"],
    investigating: ["action_required", "resolved"],
    action_required: ["investigating", "resolved"],
    resolved: ["closed"],
    closed: [],
};

const ALERT_NEXT = {
    new: ["acknowledged", "in_progress"],
    acknowledged: ["in_progress"],
    in_progress: ["resolved"],
    resolved: ["closed"],
    closed: [],
};

function extractError(error) {
    const message = error?.data?.message || error?.message || "";
    if (!message || message.includes("Traceback")) {
        return "The request could not be completed.";
    }
    return message;
}

function text(value) {
    if (value === 0) {
        return "0";
    }
    return value || "";
}

export class UtilityManagementApp extends Component {
    static template = "utility_management.App";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");
        this.screens = SCREENS;
        this.sourceScreens = SOURCE_SCREENS;
        const requested =
            this.props.action?.context?.screen ||
            this.props.action?.params?.screen ||
            "";
        const known = SCREENS.some((item) => item.id === requested);
        this.state = useState({
            screen: known ? requested : "",
            page: known ? DEFAULT_PAGE[requested] : "",
            status: known ? "loading" : "error",
            error: known ? "" : "Unknown screen.",
            formError: "",
            notice: "",
            menuOpen: false,
            isManager: false,
            data: {},
            filters: {},
            form: {},
            recordId: false,
            confirm: "",
            busy: false,
            users: [],
            meters: [],
            pager: { limit: 5, offset: 0, total_count: 0 },
            selected: [],
            detailTab: "overview",
            propertyOptions: [],
        });
        this.syncFrame = () => {
            const el = this.root.el;
            if (!el) {
                return;
            }
            const top = Math.max(0, Math.round(el.getBoundingClientRect().top));
            el.style.setProperty("--um-top", `${top}px`);
        };
        onMounted(() => {
            this.syncFrame();
            window.addEventListener("resize", this.syncFrame);
            if (this.state.status !== "error") {
                this.boot();
            }
        });
        onWillUnmount(() => window.removeEventListener("resize", this.syncFrame));
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
    }

    get pageInfo() {
        if (this.state.page === "settings_audit") {
            return { id: "settings_audit", title: "Audit log", screen: "utility_settings" };
        }
        return this.sourceScreens.find((item) => item.id === this.state.page) || {
            title: this.state.screen === "utility_settings" ? "Settings" : this.current.label,
        };
    }

    get areaPages() {
        return this.sourceScreens.filter((item) => item.parent === this.state.screen);
    }

    get filterFields() {
        const page = this.state.page;
        const location = [
            { name: "site_ref", label: "Site" },
        ];
        if (page === "reading_list") {
            return location.concat([
                { name: "search", label: "Search" },
                { name: "source", label: "Source" },
                { name: "status", label: "Status" },
            ]);
        }
        if (["meter_inventory", "leak_list", "alert_list"].includes(page)) {
            return location.concat([
                { name: "search", label: "Search" },
            ]);
        }
        if (page === "settings_audit" && !this.state.recordId) {
            return [
                { name: "search", label: "Search" },
                {
                    name: "event_type",
                    label: "Event",
                    type: "select",
                    options: [
                        "meter_change", "reading_correction", "reading_verification",
                        "alert_change", "leak_change", "config_change", "report_execution", "access_denied",
                    ],
                },
                { name: "outcome", label: "Outcome", type: "select", options: ["success", "denied"] },
                { name: "model_name", label: "Resource" },
                { name: "user_id", label: "User", type: "number" },
            ];
        }
        if (page.endsWith("trends") || page.startsWith("consumption") || page.startsWith("electricity") || page.startsWith("water") || page.startsWith("gas")) {
            return location.concat([
                { name: "grouping", label: "Grouping", type: "select", options: ["day", "week", "month", "year"] },
            ]);
        }
        return [];
    }

    get kpiItems() {
        const data = this.state.data || {};
        const page = this.state.page;
        if (page === "electricity_monitoring" || page === "water_dashboard" || page === "gas_monitoring") {
            return [
                { label: "Consumption", value: text(data.consumption) },
                { label: "Readings", value: text(data.reading_count) },
                { label: "Abnormal", value: text(data.abnormal) },
                { label: "Peak demand", value: text(data.peak_demand) },
            ].filter((item) => item.label !== "Peak demand" || page === "electricity_monitoring");
        }
        if (page === "power_dashboard" || page === "leak_dashboard" || page === "alert_dashboard" || page === "report_dashboard") {
            return Object.keys(data)
                .filter((key) => ["total", "new", "detected", "investigating", "closed", "grid_active", "outages", "definitionCount", "runs", "failed", "in_progress", "resolved"].includes(key))
                .map((key) => ({ label: key.replaceAll("_", " "), value: text(data[key]) }));
        }
        if (page === "consumption_dashboard") {
            return [
                { label: "Electricity", value: text(data.electricity) },
                { label: "Water", value: text(data.water) },
                { label: "Gas", value: text(data.gas) },
            ];
        }
        return [];
    }

    get table() {
        const data = this.state.data || {};
        const page = this.state.page;
        const open = (target, id) => this.openRecord(target, id);
        if (page === "smart_meter_dashboard") {
            return null;
        }
        if (page === "meter_inventory") {
            return {
                selectable: true,
                columns: [
                    { key: "meter_code", label: "Meter" },
                    { key: "name", label: "Name" },
                    { key: "utility_type", label: "Utility" },
                    { key: "property_ref", label: "Property" },
                    { key: "site_ref", label: "Site" },
                    { key: "status", label: "Status", badge: true },
                    { key: "health", label: "Health", badge: true },
                ],
                rows: data.meters || [],
                onOpen: (row) => open("meter_details", row.id),
            };
        }
        if (page === "electricity_buildings") {
            return {
                columns: [
                    { key: "site_ref", label: "Building / site" },
                    { key: "property_ref", label: "Property" },
                    { key: "consumption", label: "Consumption" },
                    { key: "peak_demand", label: "Peak demand" },
                ],
                rows: (data.rows || []).map((row, index) => ({ ...row, id: index })),
            };
        }
        if (page === "water_tanks") {
            return {
                columns: [
                    { key: "meter_code", label: "Tank meter" },
                    { key: "tank_level", label: "Level" },
                    { key: "tank_capacity", label: "Capacity" },
                    { key: "availability", label: "Availability" },
                    { key: "flow_rate", label: "Flow" },
                    { key: "inflow", label: "Inflow" },
                    { key: "outflow", label: "Outflow" },
                    { key: "property_ref", label: "Property" },
                ],
                rows: (data.rows || []).map((row) => ({ ...row, id: row.meter_id })),
                onOpen: (row) => open("meter_details", row.meter_id),
            };
        }
        if (page === "gas_safety") {
            return {
                columns: [
                    { key: "meter_code", label: "Meter" },
                    { key: "status", label: "Connectivity", badge: true },
                    { key: "flow_rate", label: "Flow" },
                    { key: "pressure", label: "Pressure" },
                    { key: "safety_observation", label: "Safety", badge: true },
                    { key: "property_ref", label: "Property" },
                ],
                rows: (data.rows || []).map((row) => ({ ...row, id: row.meter_id })),
                onOpen: (row) => open("meter_details", row.meter_id),
            };
        }
        if (page === "power_grid") {
            return {
                columns: [
                    { key: "name", label: "Source" },
                    { key: "source_kind", label: "Kind" },
                    { key: "status", label: "Status", badge: true },
                    { key: "property_ref", label: "Property" },
                    { key: "fuel_level_percent", label: "Fuel" },
                    { key: "rated_load", label: "Rated load" },
                ],
                rows: data.rows || [],
                onOpen: (row) => this.selectPower(row),
            };
        }
        if (page === "reading_list") {
            return {
                columns: [
                    { key: "name", label: "Reading" },
                    { key: "meter_code", label: "Meter" },
                    { key: "utility_type", label: "Utility" },
                    { key: "observed_at", label: "Observed" },
                    { key: "source", label: "Source" },
                    { key: "status", label: "Status", badge: true },
                    { key: "consumption_qty", label: "Consumption" },
                    { key: "is_abnormal", label: "Abnormal" },
                    { key: "property_ref", label: "Property" },
                ],
                rows: data.rows || [],
                onOpen: (row) => open("reading_detail", row.id),
            };
        }
        if (page === "leak_list" || page === "leak_dashboard") {
            return {
                columns: [
                    { key: "name", label: "Incident" },
                    { key: "leak_type", label: "Type" },
                    { key: "severity", label: "Severity", badge: true },
                    { key: "state", label: "Status", badge: true },
                    { key: "property_ref", label: "Property" },
                    { key: "detected_at", label: "Detected" },
                ],
                rows: page === "leak_dashboard" ? (data.leaks || []) : (data.rows || []),
                onOpen: (row) => open("leak_detail", row.id),
            };
        }
        if (page === "alert_list" || page === "alert_dashboard") {
            return {
                columns: [
                    { key: "name", label: "Alert" },
                    { key: "alert_type", label: "Type" },
                    { key: "severity", label: "Severity", badge: true },
                    { key: "state", label: "Status", badge: true },
                    { key: "observed_value", label: "Value" },
                    { key: "threshold_value", label: "Threshold" },
                    { key: "property_ref", label: "Property" },
                ],
                rows: page === "alert_dashboard" ? (data.alerts || []) : (data.rows || []),
                onOpen: (row) => open("alert_detail", row.id),
            };
        }
        if (page === "consumption_analysis") {
            return {
                columns: [
                    { key: "meter_code", label: "Meter" },
                    { key: "utility_type", label: "Utility" },
                    { key: "property_ref", label: "Property" },
                    { key: "consumption", label: "Consumption" },
                    { key: "peak_demand", label: "Peak demand" },
                    { key: "abnormal", label: "Abnormal" },
                ],
                rows: (data.meters || []).map((row) => ({ ...row, id: row.meter_id })),
                onOpen: (row) => open("meter_details", row.meter_id),
            };
        }
        if (page === "report_detail" && !this.state.recordId) {
            return {
                columns: [
                    { key: "name", label: "Run" },
                    { key: "report_type", label: "Type" },
                    { key: "execution_state", label: "Status", badge: true },
                    { key: "export_format", label: "Format" },
                ],
                rows: data.rows || [],
                onOpen: (row) => open("report_detail", row.id),
            };
        }
        if (page === "report_dashboard" || page === "report_builder") {
            return {
                columns: [
                    { key: "name", label: "Definition" },
                    { key: "report_type", label: "Type" },
                    { key: "grouping", label: "Grouping" },
                    { key: "comparison", label: "Comparison" },
                    { key: "schedule", label: "Schedule" },
                    { key: "property_ref", label: "Property" },
                ],
                rows: data.definitions || [],
                onOpen: (row) => this.editDefinition(row),
            };
        }
        if (page === "settings_audit" && !this.state.recordId) {
            return {
                columns: [
                    { key: "occurred_at", label: "Timestamp" },
                    { key: "event_type", label: "Event", badge: true },
                    { key: "model_name", label: "Resource" },
                    { key: "res_id", label: "Reference" },
                    { key: "user_name", label: "User" },
                    { key: "company_name", label: "Company" },
                    { key: "outcome", label: "Outcome", badge: true },
                    { key: "summary", label: "Description" },
                ],
                rows: data.rows || [],
                onOpen: (row) => this.openAuditEvent(row),
            };
        }
        return null;
    }

    get chartRows() {
        const buckets = this.state.data?.buckets || [];
        const max = Math.max(...buckets.map((row) => Number(row.consumption) || 0), 0);
        return buckets.map((row) => ({
            ...row,
            width: max ? Math.max(2, Math.round((Number(row.consumption) / max) * 100)) : 0,
        }));
    }

    get comparisonCharts() {
        const data = this.state.data?.comparison || this.state.data || {};
        return ["electricity", "water", "gas"].map((utility) => {
            const buckets = data[utility]?.buckets || [];
            const max = Math.max(...buckets.map((row) => Number(row.consumption) || 0), 0);
            return {
                utility,
                previous: data[utility]?.previous_period?.consumption,
                peak: data[utility]?.peak_bucket,
                rows: buckets.map((row) => ({
                    ...row,
                    width: max ? Math.max(2, Math.round((Number(row.consumption) / max) * 100)) : 0,
                })),
            };
        });
    }

    get showPlant() {
        return [
            "smart_meter_dashboard", "meter_inventory",
            "electricity_monitoring", "electricity_buildings", "electricity_trends",
            "water_dashboard", "water_tanks", "water_trends",
            "gas_monitoring", "gas_safety", "gas_trends",
            "power_dashboard", "power_grid",
            "consumption_dashboard", "consumption_analysis", "consumption_comparison",
            "reading_list", "leak_dashboard", "leak_list", "alert_dashboard", "alert_list",
        ].includes(this.state.page);
    }

    get showDates() {
        const page = this.state.page;
        return page === "reading_list" || (page === "settings_audit" && !this.state.recordId) || page.endsWith("trends") || page.startsWith("consumption") || page.startsWith("electricity") || page.startsWith("water") || page.startsWith("gas");
    }

    get usesPager() {
        if (this.state.page === "settings_audit") {
            return !this.state.recordId;
        }
        if (["meter_inventory", "reading_list", "gas_safety", "leak_list", "alert_list"].includes(this.state.page)) {
            return true;
        }
        return this.state.page === "report_detail" && !this.state.recordId;
    }

    get pagerFrom() {
        return this.state.pager.total_count ? this.state.pager.offset + 1 : 0;
    }

    get pagerTo() {
        return Math.min(this.state.pager.offset + this.state.pager.limit, this.state.pager.total_count);
    }

    get pagerPage() {
        if (!this.state.pager.total_count) {
            return 1;
        }
        return Math.floor(this.state.pager.offset / this.state.pager.limit) + 1;
    }

    get pagerPages() {
        if (!this.state.pager.total_count) {
            return 1;
        }
        return Math.ceil(this.state.pager.total_count / this.state.pager.limit);
    }

    get statusSegments() {
        const counts = this.state.data?.counts || {};
        const keys = ["online", "offline", "error", "maintenance", "connecting", "deactivated"];
        const total = keys.reduce((sum, key) => sum + (Number(counts[key]) || 0), 0);
        if (!total) {
            return [];
        }
        return keys.filter((key) => counts[key]).map((key) => ({
            key,
            count: counts[key],
            width: Math.max(4, Math.round((Number(counts[key]) / total) * 100)),
        }));
    }

    get dash() {
        const data = this.state.data || {};
        const counts = data.counts || {};
        const total = Number(data.total) || 0;
        const online = Number(counts.online) || 0;
        const offline = Number(counts.offline) || 0;
        const error = Number(counts.error) || 0;
        const connecting = Number(counts.connecting) || 0;
        const maintenance = Number(counts.maintenance) || 0;
        const deactivated = Number(counts.deactivated) || 0;
        const critical = (data.alerts || []).filter((row) => row.severity === "critical" && row.state !== "resolved" && row.state !== "closed").length;
        const syncIssues = (data.meters || []).filter((row) => row.health === "degraded" || row.health === "failed").length;
        const share = total ? (online / total) * 100 : 0;
        const percent = Number.isInteger(share) ? String(share) : share.toFixed(1);
        return {
            total,
            online,
            offline,
            error,
            critical,
            syncIssues,
            active: online + connecting,
            inactive: offline + deactivated + maintenance,
            percent: `${percent}%`,
        };
    }

    get dashLegend() {
        const counts = this.state.data?.counts || {};
        return ["online", "offline", "connecting", "error", "maintenance", "deactivated"].map((key) => ({
            key,
            label: key.charAt(0).toUpperCase() + key.slice(1),
            count: Number(counts[key]) || 0,
        }));
    }

    readingLabel(row) {
        if (row.latest_reading === false || row.latest_reading === null || row.latest_reading === undefined || row.latest_reading === "") {
            return "—";
        }
        return row.latest_uom ? `${row.latest_reading} ${row.latest_uom}` : String(row.latest_reading);
    }

    propertyLabel(row) {
        return row.property_label || row.property_ref || "—";
    }

    get meterSummary() {
        const counts = this.state.data?.counts || {};
        const summary = this.state.data?.summary || {};
        if (this.state.page === "meter_inventory") {
            return [
                { label: "Electricity", value: summary.electricity || 0 },
                { label: "Water", value: summary.water || 0 },
                { label: "Gas", value: summary.gas || 0 },
            ];
        }
        return [
            { label: "Total", value: this.state.data?.total || 0 },
            { label: "Active", value: (Number(counts.online) || 0) + (Number(counts.connecting) || 0) },
            { label: "Inactive", value: (Number(counts.offline) || 0) + (Number(counts.deactivated) || 0) + (Number(counts.maintenance) || 0) },
        ];
    }

    get attentionItems() {
        const data = this.state.data || {};
        if (this.state.page === "smart_meter_dashboard") {
            const counts = data.counts || {};
            const items = [];
            if (counts.offline) {
                items.push({ label: "Offline meters", value: counts.offline });
            }
            if (counts.error) {
                items.push({ label: "Meters in error", value: counts.error });
            }
            for (const alert of data.alerts || []) {
                if (alert.severity === "critical" || alert.severity === "high") {
                    items.push({ label: alert.name, value: alert.severity, id: alert.id });
                }
            }
            return items;
        }
        if (this.state.page === "meter_inventory") {
            return (data.warnings || []).map((row) => ({
                label: `${row.meter_code} ${row.status}`,
                value: row.health,
            }));
        }
        return (data.warnings || []).map((alert) => ({
            label: alert.name,
            value: alert.severity,
            id: alert.id,
        }));
    }

    get reportTemplates() {
        return [
            { type: "electricity_consumption", title: "Electricity consumption", text: "Verified electricity readings for the selected period." },
            { type: "water_consumption", title: "Water consumption", text: "Verified water readings for the selected period." },
            { type: "gas_consumption", title: "Gas consumption", text: "Verified gas readings for the selected period." },
            { type: "combined_usage", title: "Combined utility usage", text: "Electricity, water, and gas totals by property." },
            { type: "grid_vs_generator", title: "Grid vs generator", text: "Power source status and recorded load." },
            { type: "meter_reading", title: "Meter reading", text: "Reading rows with consumption and demand." },
            { type: "leak_detection", title: "Leak detection", text: "Open and closed leak incidents." },
            { type: "consumption_alert", title: "Consumption alert", text: "Alerts raised from consumption rules." },
            { type: "utility_trend", title: "Utility trend", text: "Consumption buckets compared with the previous period." },
            { type: "utility_performance", title: "Utility performance", text: "Reading, alert, and leak counts for the period." },
        ];
    }

    get consumptionBars() {
        const data = this.state.data || {};
        const items = [
            { label: "Electricity", value: Number(data.electricity) || 0 },
            { label: "Water", value: Number(data.water) || 0 },
            { label: "Gas", value: Number(data.gas) || 0 },
        ];
        const max = Math.max(...items.map((item) => item.value), 0);
        return items.map((item) => ({
            ...item,
            width: max ? Math.max(2, Math.round((item.value / max) * 100)) : 0,
        }));
    }

    get tankCards() {
        const tanks = this.state.page === "water_dashboard" ? (this.state.data?.tanks || []) : (this.state.data?.rows || []);
        return tanks.map((tank) => {
            const capacity = Number(tank.tank_capacity) || 0;
            const level = Number(tank.tank_level) || 0;
            return {
                ...tank,
                percent: capacity > 0 ? Math.max(0, Math.min(100, Math.round((level / capacity) * 100))) : 0,
            };
        });
    }

    get distributionHealth() {
        const cards = this.tankCards.filter((tank) => Number(tank.tank_capacity) > 0);
        if (!cards.length) {
            return null;
        }
        const capacity = cards.reduce((sum, tank) => sum + Number(tank.tank_capacity), 0);
        const level = cards.reduce((sum, tank) => sum + (Number(tank.tank_level) || 0), 0);
        return {
            tanks: cards.length,
            percent: capacity ? Math.round((level / capacity) * 100) : 0,
            availability: cards.reduce((sum, tank) => sum + (Number(tank.availability) || 0), 0),
        };
    }

    get currentSource() {
        const sources = this.state.data?.sources || [];
        return sources.find((source) => source.status === "grid_active") || sources[0] || null;
    }

    get powerWarnings() {
        return (this.state.data?.sources || []).filter((source) => ["grid_outage", "generator_fault"].includes(source.status));
    }

    get trendLine() {
        return this.linePoints(this.chartRows, "consumption");
    }

    get connectivityLine() {
        const history = this.state.data?.history || [];
        const rows = history.map((row) => ({
            value: Number(row.response_ms) > 0 ? Number(row.response_ms) : (row.status === "online" ? 1 : 0),
        }));
        return this.linePoints(rows, "value");
    }

    get powerLine() {
        return this.linePoints(this.state.data?.events || [], "load");
    }

    get reportLine() {
        return this.linePoints(this.state.data?.run?.chart || [], "value");
    }

    get showEmpty() {
        const page = this.state.page;
        if (page === "settings_audit" && this.state.recordId) {
            return false;
        }
        if (["smart_meter_dashboard", "add_configure_meter", "reading_form", "meter_details", "reading_detail", "leak_detail", "alert_detail", "power_history", "report_detail", "settings", "report_builder", "consumption_comparison", "power_grid"].includes(page)) {
            return false;
        }
        if (this.chartRows.length || this.kpiItems.length) {
            return false;
        }
        const rows = this.table?.rows || [];
        return !rows.length;
    }

    toggleMenu() {
        this.state.menuOpen = !this.state.menuOpen;
    }

    closeMenu() {
        this.state.menuOpen = false;
    }

    async boot() {
        this.state.status = "loading";
        this.state.error = "";
        try {
            const health = await this.orm.call("utility.management.ui.api", "health", []);
            this.state.isManager = Boolean(health.is_facility_manager);
            await this.loadPage();
        } catch (error) {
            this.state.status = "error";
            this.state.error = extractError(error);
        }
    }

    async openScreen(screenId) {
        if (!this.screens.some((item) => item.id === screenId)) {
            this.state.status = "error";
            this.state.error = "Unknown screen.";
            return;
        }
        this.state.screen = screenId;
        this.state.page = DEFAULT_PAGE[screenId];
        this.state.recordId = false;
        this.state.filters = {};
        this.state.form = {};
        this.state.pager.offset = 0;
        this.state.selected = [];
        this.state.detailTab = "overview";
        this.state.menuOpen = false;
        this.state.notice = "";
        this.state.formError = "";
        await this.loadPage();
    }

    async openPage(pageId) {
        this.state.page = pageId;
        this.state.pager.offset = 0;
        this.state.selected = [];
        this.state.notice = "";
        this.state.formError = "";
        if (!["meter_details", "reading_detail", "leak_detail", "alert_detail", "power_history", "report_detail"].includes(pageId)) {
            this.state.recordId = false;
        }
        await this.loadPage();
    }

    async openRecord(pageId, recordId) {
        const page = this.sourceScreens.find((item) => item.id === pageId);
        if (!page) {
            return;
        }
        this.state.screen = page.parent;
        this.state.page = pageId;
        this.state.recordId = recordId;
        this.state.menuOpen = false;
        this.state.notice = "";
        this.state.formError = "";
        await this.loadPage();
    }

    async openAudit() {
        this.state.screen = "utility_settings";
        this.state.page = "settings_audit";
        this.state.recordId = false;
        this.state.pager.offset = 0;
        this.state.notice = "";
        this.state.formError = "";
        await this.loadPage();
    }

    async closeAudit() {
        this.state.page = "settings";
        this.state.recordId = false;
        await this.loadPage();
    }

    async openAuditEvent(row) {
        this.state.recordId = row.id;
        this.state.notice = "";
        this.state.formError = "";
        await this.loadPage();
    }

    async closeAuditEvent() {
        this.state.recordId = false;
        await this.loadPage();
    }

    auditLines(payload) {
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
            return [];
        }
        return Object.keys(payload).map((key) => {
            const value = payload[key];
            let text = "—";
            if (value !== false && value !== null && value !== undefined && value !== "") {
                text = typeof value === "object" ? JSON.stringify(value) : String(value);
            }
            return { key, value: text };
        });
    }

    get auditBefore() {
        return this.auditLines(this.state.data?.event?.data_before);
    }

    get auditAfter() {
        return this.auditLines(this.state.data?.event?.data_after);
    }

    filters() {
        const values = {};
        for (const [key, value] of Object.entries(this.state.filters)) {
            if (value) {
                values[key] = value;
            }
        }
        return values;
    }

    async loadPage() {
        this.state.status = "loading";
        this.state.error = "";
        try {
            const page = this.state.page;
            const filters = this.filters();
            if (this.showPlant && !this.state.propertyOptions.length && page !== "smart_meter_dashboard" && page !== "meter_inventory") {
                const listed = await this.call("list_meters", [{ limit: 1, offset: 0 }]);
                this.rememberProperties(listed && listed.properties);
            }
            if (page === "settings") {
                const settings = await this.call("get_settings", []);
                let scopes = [];
                if (this.state.isManager) {
                    scopes = await this.call("list_scopes", []);
                }
                this.state.data = { settings, scopes };
                this.state.form = { ...settings };
            } else if (page === "settings_audit") {
                if (this.state.recordId) {
                    this.state.data = { event: await this.call("get_audit_event", [this.state.recordId]) };
                } else {
                    const pageData = await this.call("list_audit_events", [this.pagedFilters()]);
                    this.state.data = { rows: this.applyPage(pageData) };
                }
            } else if (page === "smart_meter_dashboard") {
                const dash = await this.call("get_dashboard", [filters]);
                const alerts = await this.call("get_alert_overview", [filters]);
                this.rememberProperties(dash.properties);
                this.state.data = { ...dash, alertTotal: alerts.total, alerts: alerts.alerts || [] };
            } else if (page === "meter_inventory") {
                const pageData = await this.call("list_meters", [this.pagedFilters()]);
                const rows = this.applyPage(pageData);
                this.rememberProperties(pageData.properties);
                this.state.data = {
                    meters: rows,
                    summary: pageData.summary || {},
                    warnings: pageData.warnings || [],
                };
            } else if (page === "add_configure_meter") {
                if (!this.state.form.utility_type) {
                    this.state.form = {
                        utility_type: "electricity",
                        meter_role: "consumption",
                        reading_mode: "cumulative",
                        protocol: "manual",
                        ...this.state.form,
                    };
                }
                this.state.data = {};
            } else if (page === "meter_details") {
                if (!this.state.recordId) {
                    this.state.data = {};
                } else {
                    const meter = await this.call("get_meter", [this.state.recordId]);
                    const history = await this.call("list_connectivity", [this.state.recordId]);
                    const readings = await this.call("list_readings", [{ meter_id: this.state.recordId, limit: 5, offset: 0 }]);
                    const alerts = await this.call("list_alerts", [{ meter_id: this.state.recordId }]);
                    this.state.data = {
                        meter,
                        history,
                        readings: readings.rows || readings,
                        alerts: Array.isArray(alerts) ? alerts : (alerts.rows || []),
                    };
                }
            } else if (page === "electricity_monitoring") {
                const overview = await this.call("get_electricity_overview", [filters]);
                const trend = await this.call("get_electricity_trends", [filters]);
                const alerts = await this.call("get_alert_overview", [{ ...filters, utility_type: "electricity" }]);
                this.state.data = { ...overview, buckets: trend.buckets || [], peak_bucket: trend.peak_bucket, warnings: alerts.alerts || [] };
            } else if (page === "electricity_buildings") {
                const rows = await this.call("get_electricity_buildings", [filters]);
                this.state.data = {
                    rows,
                    buckets: rows.map((row) => ({
                        bucket: row.site_ref || row.property_ref || "Unassigned",
                        consumption: row.consumption,
                    })),
                };
            } else if (page === "electricity_trends") {
                this.state.data = await this.call("get_electricity_trends", [filters]);
            } else if (page === "water_dashboard") {
                const overview = await this.call("get_water_overview", [filters]);
                const trend = await this.call("get_water_trends", [filters]);
                const tanks = await this.call("get_water_tanks", [filters]);
                const alerts = await this.call("get_alert_overview", [{ ...filters, utility_type: "water" }]);
                this.state.data = { ...overview, buckets: trend.buckets || [], peak_bucket: trend.peak_bucket, tanks, warnings: alerts.alerts || [] };
            } else if (page === "water_tanks") {
                this.state.data = { rows: await this.call("get_water_tanks", [filters]) };
            } else if (page === "water_trends") {
                this.state.data = await this.call("get_water_trends", [filters]);
            } else if (page === "gas_monitoring") {
                const overview = await this.call("get_gas_overview", [filters]);
                const trend = await this.call("get_gas_trends", [filters]);
                const alerts = await this.call("get_alert_overview", [{ ...filters, utility_type: "gas" }]);
                const safety = Array.isArray(overview.safety) ? overview.safety : [];
                this.state.data = {
                    ...overview,
                    buckets: trend.buckets || [],
                    peak_bucket: trend.peak_bucket,
                    warnings: alerts.alerts || [],
                    safetyWarnings: safety.filter((row) => row.safety_observation === "warning" || row.safety_observation === "critical"),
                };
            } else if (page === "gas_safety") {
                const pageData = await this.call("get_gas_safety", [this.pagedFilters()]);
                this.state.data = { rows: this.applyPage(pageData) };
            } else if (page === "gas_trends") {
                this.state.data = await this.call("get_gas_trends", [filters]);
            } else if (page === "power_dashboard") {
                this.state.data = await this.call("get_power_overview", [filters]);
            } else if (page === "power_grid") {
                this.state.data = { rows: await this.call("list_power_sources", [filters]) };
                this.state.form = { status: "", load: "", fuel_level_percent: "", fuel_consumed: "" };
            } else if (page === "power_history") {
                this.state.data = this.state.recordId
                    ? await this.call("get_power_history", [this.state.recordId])
                    : {};
            } else if (page === "consumption_dashboard") {
                const overview = await this.call("get_consumption_overview", [filters]);
                const comparison = await this.call("get_consumption_comparison", [filters]);
                this.state.data = { ...overview, comparison };
            } else if (page === "consumption_analysis") {
                const analysis = await this.call("get_consumption_analysis", [filters]);
                this.state.data = {
                    properties: analysis.properties || [],
                    meters: analysis.meters || [],
                    abnormal: analysis.abnormal_meters || [],
                };
            } else if (page === "consumption_comparison") {
                this.state.data = await this.call("get_consumption_comparison", [filters]);
            } else if (page === "reading_list") {
                const pageData = await this.call("list_readings", [this.pagedFilters()]);
                this.state.data = { rows: this.applyPage(pageData) };
            } else if (page === "reading_form") {
                this.state.meters = await this.call("list_meters", [{}]);
                if (!this.state.form.source) {
                    this.state.form = { source: "manual", ...this.state.form };
                }
                this.state.data = {};
            } else if (page === "reading_detail") {
                this.state.data = this.state.recordId
                    ? { reading: await this.call("get_reading", [this.state.recordId]) }
                    : {};
            } else if (page === "leak_dashboard") {
                this.state.data = await this.call("get_leak_overview", [filters]);
            } else if (page === "leak_list") {
                const pageData = await this.call("list_leaks", [this.pagedFilters()]);
                this.state.data = { rows: this.applyPage(pageData) };
                this.state.meters = await this.call("list_meters", [{}]);
            } else if (page === "leak_detail") {
                await this.loadUsers();
                this.state.data = this.state.recordId
                    ? { leak: await this.call("get_leak", [this.state.recordId]) }
                    : {};
            } else if (page === "alert_dashboard") {
                this.state.data = await this.call("get_alert_overview", [filters]);
            } else if (page === "alert_list") {
                const pageData = await this.call("list_alerts", [this.pagedFilters()]);
                this.state.data = { rows: this.applyPage(pageData) };
            } else if (page === "alert_detail") {
                const rules = this.state.isManager ? await this.call("list_alert_rules", [{}]) : [];
                this.state.data = {
                    alert: this.state.recordId ? await this.call("get_alert", [this.state.recordId]) : null,
                    rules,
                };
                this.state.meters = await this.call("list_meters", [{}]);
            } else if (page === "report_dashboard") {
                const overview = await this.call("get_report_overview", []);
                const definitions = await this.call("list_report_definitions", []);
                this.state.data = {
                    ...overview,
                    definitionCount: overview.definitions,
                    definitions,
                };
            } else if (page === "report_builder") {
                this.state.meters = await this.call("list_meters", [{}]);
                const definitions = await this.call("list_report_definitions", []);
                this.state.data = { definitions };
                if (!this.state.form.report_type) {
                    this.state.form = {
                        report_type: "electricity_consumption",
                        grouping: "month",
                        comparison: "none",
                        schedule: "none",
                        ...this.state.form,
                    };
                }
            } else if (page === "report_detail") {
                if (this.state.recordId) {
                    this.state.data = { run: await this.call("get_report_run", [this.state.recordId]) };
                } else {
                    const pageData = await this.call("list_report_runs", [this.pagedFilters()]);
                    this.state.data = { rows: this.applyPage(pageData) };
                }
            }
            this.state.status = "ready";
        } catch (error) {
            this.state.status = "error";
            this.state.error = extractError(error);
        }
    }

    call(method, args) {
        return this.orm.call("utility.management.ui.api", method, args);
    }

    async loadUsers() {
        try {
            this.state.users = await this.orm.searchRead(
                "res.users",
                [["share", "=", false]],
                ["name"],
                { limit: 80 }
            );
        } catch {
            this.state.users = [];
        }
    }

    onFilter(ev) {
        this.state.filters[ev.target.name] = ev.target.value;
    }

    onForm(ev) {
        const field = ev.target;
        this.state.form[field.name] = field.type === "checkbox" ? field.checked : field.value;
    }

    async applyFilters() {
        this.state.pager.offset = 0;
        this.state.selected = [];
        await this.loadPage();
    }

    pagedFilters() {
        return {
            ...this.filters(),
            limit: this.state.pager.limit,
            offset: this.state.pager.offset,
        };
    }

    applyPage(payload) {
        if (payload && typeof payload.total_count === "number") {
            this.state.pager.total_count = payload.total_count;
            this.state.pager.limit = payload.limit || this.state.pager.limit;
            this.state.pager.offset = payload.offset || 0;
            return payload.rows || [];
        }
        const rows = Array.isArray(payload) ? payload : [];
        this.state.pager.total_count = rows.length;
        return rows;
    }

    rememberProperties(values) {
        const found = new Set(this.state.propertyOptions);
        for (const value of values || []) {
            if (typeof value === "string" && value) {
                found.add(value);
            } else if (value && value.property_ref) {
                found.add(value.property_ref);
            }
        }
        if (this.state.filters.property_ref) {
            found.add(this.state.filters.property_ref);
        }
        this.state.propertyOptions = [...found].sort();
    }

    linePoints(rows, key) {
        const values = (rows || []).map((row) => Number(row[key]) || 0);
        if (!values.length) {
            return "";
        }
        const max = Math.max(...values);
        const min = Math.min(...values);
        const span = (max - min) || 1;
        return values.map((value, index) => {
            const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
            const y = 36 - ((value - min) / span) * 32;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }

    areaPoints(points) {
        return points ? `${points} 100,40 0,40` : "";
    }

    isSelected(id) {
        return this.state.selected.includes(id);
    }

    toggleSelect(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        const selected = this.state.selected.filter((item) => item !== id);
        if (ev.currentTarget.checked) {
            selected.push(id);
        }
        this.state.selected = selected;
    }

    setDetailTab(tab) {
        this.state.detailTab = tab;
    }

    async changePage(direction) {
        const next = this.state.pager.offset + (direction * this.state.pager.limit);
        if (next < 0 || (this.state.pager.total_count && next >= this.state.pager.total_count)) {
            return;
        }
        this.state.pager.offset = next;
        await this.loadPage();
    }

    async changePageSize(ev) {
        this.state.pager.limit = Number(ev.target.value) || 5;
        this.state.pager.offset = 0;
        await this.loadPage();
    }

    async configureSelected() {
        if (this.state.selected.length !== 1) {
            return;
        }
        const meter = await this.call("get_meter", [this.state.selected[0]]);
        await this.configureMeter(meter);
    }

    askDeactivateSelected() {
        if (this.state.selected.length) {
            this.state.confirm = "deactivate-selected";
        }
    }

    openTemplate(type) {
        this.state.form = {
            report_type: type,
            grouping: "month",
            comparison: "none",
            schedule: "none",
        };
        this.openPage("report_builder");
    }

    cell(row, key) {
        const value = row[key];
        if (value === true) {
            return "Yes";
        }
        if (value === false || value === null || value === undefined || value === "") {
            return "—";
        }
        return value;
    }

    async saveMeter() {
        const values = { ...this.state.form };
        if (!values.name || !values.meter_code || !values.utility_type) {
            this.state.formError = "Name, meter code, and utility are required.";
            return;
        }
        if (values.meter_role === "tank" && !(Number(values.tank_capacity) > 0)) {
            this.state.formError = "A tank meter requires tank capacity greater than zero.";
            return;
        }
        await this.submit("save_meter", [this.numbers(values, ["sync_frequency_minutes", "tank_capacity", "anomaly_percent", "battery_percent"])], "Meter saved.", "meter_details");
    }

    async startNewMeter() {
        this.state.form = {};
        await this.openRecord("add_configure_meter", false);
    }

    async onDashStatus(ev) {
        this.onFilter(ev);
        await this.applyFilters();
    }

    async meterHealthCheck() {
        const meters = this.state.data?.meters || [];
        if (!meters.length) {
            this.state.notice = "No meters to check.";
            return;
        }
        try {
            const result = await this.call("test_meter_connection", [meters[0].id]);
            this.state.notice = result && result.ok ? "Connection succeeded." : "No provider is connected.";
        } catch (error) {
            this.state.formError = extractError(error);
        }
    }

    async configureMeter(meter) {
        this.state.form = { ...meter };
        await this.openPage("add_configure_meter");
    }

    async setMeterStatus(status) {
        if (status === "deactivated") {
            this.state.confirm = "deactivate-meter";
            return;
        }
        await this.applyMeterStatus(status);
    }

    async applyMeterStatus(status) {
        await this.submit("set_meter_status", [this.state.recordId, status, {}], "Meter status updated.", "meter_details");
    }

    async testConnection() {
        const result = await this.call("test_meter_connection", [this.state.recordId]);
        this.state.notice = result.ok ? "Connection succeeded." : "No provider is connected.";
        await this.loadPage();
        this.state.notice = result.ok ? "Connection succeeded." : "No provider is connected.";
    }

    async saveReading() {
        const values = { ...this.state.form };
        if (!values.meter_id || !values.observed_at) {
            this.state.formError = "Meter and observed time are required.";
            return;
        }
        if (new Date(values.observed_at) > new Date()) {
            this.state.formError = "Reading time cannot be in the future.";
            return;
        }
        values.meter_id = Number(values.meter_id);
        values.observed_at = values.observed_at.replace("T", " ");
        this.state.busy = true;
        this.state.formError = "";
        try {
            const created = await this.call("create_reading", [this.numbers(values, [
                "register_value", "interval_quantity", "voltage", "current", "frequency",
                "power_factor", "demand_kw", "load_kw", "flow_rate", "tank_level",
                "inflow", "outflow", "pressure",
            ])]);
            if (this.state.photo && created.reading_id) {
                await this.call("attach_reading_photo", [created.reading_id, this.state.photo]);
            }
            this.state.photo = null;
            this.state.notice = created.status === "duplicate" ? "This reading was already recorded." : "Reading recorded.";
            await this.openRecord("reading_detail", created.reading_id);
            this.state.notice = created.status === "duplicate" ? "This reading was already recorded." : "Reading recorded.";
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    async onPhoto(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const allowed = ["image/jpeg", "image/png", "image/webp"];
        if (!allowed.includes(file.type) || file.size > 5 * 1024 * 1024) {
            this.state.formError = "Meter photos must be a JPEG, PNG, or WebP file of 5 MB or less.";
            return;
        }
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = "";
        bytes.forEach((item) => {
            binary += String.fromCharCode(item);
        });
        this.state.photo = { datas: btoa(binary), filename: file.name, mimetype: file.type };
        this.state.formError = "";
    }

    async verifyReading() {
        await this.submit("verify_reading", [this.state.recordId], "Reading verified.", "reading_detail");
    }

    async invalidateReading() {
        const reason = this.state.form.reason || "";
        if (!reason.trim()) {
            this.state.formError = "An invalidation reason is required.";
            return;
        }
        await this.submit("invalidate_reading", [this.state.recordId, reason], "Reading invalidated.", "reading_detail");
    }

    async correctReading() {
        const notes = this.state.form.notes || this.state.form.reason || "";
        if (!notes.trim()) {
            this.state.formError = "A correction reason is required.";
            return;
        }
        await this.submit("correct_reading", [this.state.recordId, {
            ...this.numbers(this.state.form, ["register_value", "interval_quantity"]),
            notes,
        }], "Reading corrected.", "reading_detail");
    }

    async saveLeak() {
        const values = { ...this.state.form };
        if (!values.leak_type) {
            this.state.formError = "Leak type is required.";
            return;
        }
        if (values.meter_id) {
            values.meter_id = Number(values.meter_id);
        }
        await this.submit("create_leak", [values], "Leak recorded.", "leak_detail");
    }

    async assignLeak(ev) {
        await this.submit("assign_leak", [this.state.recordId, Number(ev.target.value)], "Leak assigned.", "leak_detail");
    }

    async transitionLeak(state) {
        if (["resolved", "closed"].includes(state) && !this.state.isManager) {
            this.state.formError = "Only a Facility Manager can resolve or close a leak.";
            return;
        }
        await this.submit("transition_leak", [this.state.recordId, state], "Leak updated.", "leak_detail");
    }

    async addLeakAction() {
        const note = this.state.form.note || "";
        if (!note.trim()) {
            this.state.formError = "An action note is required.";
            return;
        }
        await this.submit("add_leak_action", [this.state.recordId, {
            entry_kind: this.state.form.entry_kind || "investigation",
            note,
        }], "Action recorded.", "leak_detail");
    }

    async transitionAlert(state) {
        const map = {
            acknowledged: "acknowledge_alert",
            in_progress: "start_alert",
            resolved: "resolve_alert",
            closed: "close_alert",
        };
        if (["resolved", "closed"].includes(state) && !this.state.isManager) {
            this.state.formError = "Only a Facility Manager can resolve or close an alert.";
            return;
        }
        const args = state === "resolved"
            ? [this.state.recordId, this.state.form.resolution_note || ""]
            : [this.state.recordId];
        await this.submit(map[state], args, "Alert updated.", "alert_detail");
    }

    async saveRule() {
        const values = this.numbers({ ...this.state.form }, ["threshold_value", "threshold_percent", "escalation_minutes", "meter_id", "escalate_to_id"]);
        if (!values.name || !values.rule_type) {
            this.state.formError = "Rule name and type are required.";
            return;
        }
        this.state.busy = true;
        try {
            await this.call("save_alert_rule", [values]);
            this.state.notice = "Alert rule saved.";
            this.state.form = {};
            await this.loadPage();
            this.state.notice = "Alert rule saved.";
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    async transitionPower() {
        const status = this.state.form.status;
        if (!this.state.recordId || !status) {
            this.state.formError = "Choose a source and the next status.";
            return;
        }
        const values = {};
        if (this.state.form.load !== "") {
            values.load = Number(this.state.form.load);
        }
        if (this.state.form.fuel_level_percent !== "") {
            values.fuel_level_percent = Number(this.state.form.fuel_level_percent);
        }
        if (this.state.form.fuel_consumed !== "") {
            values.fuel_consumed = Number(this.state.form.fuel_consumed);
        }
        await this.submit("transition_power_source", [this.state.recordId, status, values], "Power source updated.", "power_history");
    }

    selectPower(row) {
        this.state.recordId = row.id;
        this.state.formError = "";
    }

    async saveDefinition() {
        const values = { ...this.state.form };
        if (!values.name || !values.report_type) {
            this.state.formError = "Report name and type are required.";
            return;
        }
        if (values.meter_id) {
            values.meter_id = Number(values.meter_id);
        }
        this.state.busy = true;
        try {
            const saved = await this.call("save_report_definition", [values]);
            this.state.form = { ...this.state.form, id: saved.id };
            this.state.notice = "Report definition saved.";
            await this.loadPage();
            this.state.notice = "Report definition saved.";
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    editDefinition(row) {
        this.state.screen = "utility_reports";
        this.state.page = "report_builder";
        this.state.form = { ...row };
        this.state.notice = "";
        this.loadPage();
    }

    async runReport(format) {
        const definitionId = this.state.form.id;
        if (!definitionId) {
            this.state.formError = "Save the report definition before running it.";
            return;
        }
        this.state.busy = true;
        try {
            const run = await this.call("run_report", [definitionId, format]);
            this.state.notice = run.execution_state === "failed"
                ? "Report failed."
                : "Report completed.";
            await this.openRecord("report_detail", run.id);
            this.state.notice = run.execution_state === "failed" ? "Report failed." : "Report completed.";
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    async saveSettings() {
        await this.submit("save_settings", [this.state.form], "Settings saved.", "settings");
    }

    async saveScope() {
        const values = { ...this.state.form };
        if (!values.user_id || !values.dimension || !values.ref_code) {
            this.state.formError = "User, dimension, and reference code are required.";
            return;
        }
        values.user_id = Number(values.user_id);
        this.state.busy = true;
        try {
            await this.call("save_scope", [values]);
            this.state.notice = "Scope saved.";
            this.state.form = { ...this.state.data.settings };
            await this.loadPage();
            this.state.notice = "Scope saved.";
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    async deactivateScope(scope) {
        await this.call("save_scope", [{ id: scope.id, active: false }]);
        this.state.notice = "Scope deactivated.";
        await this.loadPage();
        this.state.notice = "Scope deactivated.";
    }

    async downloadFile(attachmentId) {
        try {
            const file = await this.call("download_private_file", [attachmentId]);
            const binary = atob(file.datas || "");
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index++) {
                bytes[index] = binary.charCodeAt(index);
            }
            const url = URL.createObjectURL(new Blob([bytes], { type: file.mimetype || "application/octet-stream" }));
            const link = document.createElement("a");
            link.href = url;
            link.download = file.name || "utility-file";
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            this.state.formError = extractError(error);
        }
    }

    async submit(method, args, notice, pageId) {
        this.state.busy = true;
        this.state.formError = "";
        try {
            const result = await this.call(method, args);
            const recordId = result?.id || result?.reading_id || this.state.recordId;
            this.state.notice = notice;
            if (pageId === "meter_details" || pageId === "reading_detail" || pageId === "leak_detail" || pageId === "power_history" || pageId === "report_detail") {
                await this.openRecord(pageId, recordId);
            } else {
                await this.openPage(pageId);
            }
            this.state.notice = notice;
        } catch (error) {
            this.state.formError = extractError(error);
            this.state.status = "ready";
        } finally {
            this.state.busy = false;
        }
    }

    numbers(values, names) {
        const copy = { ...values };
        for (const name of names) {
            if (copy[name] !== undefined && copy[name] !== "") {
                copy[name] = Number(copy[name]);
            }
        }
        return copy;
    }

    nextStatuses(kind) {
        const data = this.state.data || {};
        if (kind === "meter") {
            return METER_NEXT[data.meter?.status] || [];
        }
        if (kind === "leak") {
            const states = LEAK_NEXT[data.leak?.state] || [];
            return this.state.isManager ? states : states.filter((item) => !["resolved", "closed"].includes(item));
        }
        if (kind === "alert") {
            const states = ALERT_NEXT[data.alert?.state] || [];
            return this.state.isManager ? states : states.filter((item) => !["resolved", "closed"].includes(item));
        }
        if (kind === "power") {
            const source = (data.rows || []).find((row) => row.id === this.state.recordId);
            return POWER_NEXT[source?.status] || [];
        }
        return [];
    }

    askDeactivate() {
        this.state.confirm = "deactivate-meter";
    }

    async confirmYes() {
        const action = this.state.confirm;
        this.state.confirm = "";
        if (action === "deactivate-meter") {
            await this.applyMeterStatus("deactivated");
        }
        if (action === "deactivate-selected") {
            this.state.busy = true;
            try {
                for (const id of this.state.selected) {
                    await this.call("set_meter_status", [id, "deactivated", {}]);
                }
                this.state.selected = [];
                this.state.notice = "Selected meters deactivated.";
                await this.loadPage();
                this.state.notice = "Selected meters deactivated.";
            } catch (error) {
                this.state.formError = extractError(error);
                this.state.status = "ready";
            } finally {
                this.state.busy = false;
            }
        }
    }

    confirmNo() {
        this.state.confirm = "";
    }
}

registry.category("actions").add("utility_management_app", UtilityManagementApp);
