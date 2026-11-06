/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, applyShellFilters, compactFilters, display, extractError } from "../cc_utils";

const FEATURED_SITES = [
    { id: "p1", name: "Plant 1 - Northern Facility", operational_status: "normal", alerts_active: "4", incidents_open: "1", equipment: "241/252", utilization: "83%", health: 96, latest_activity_at: "2026-09-23 10:42:00" },
    { id: "p3", name: "Plant 3 - Eastern Hub", operational_status: "emergency", alerts_active: "8", incidents_open: "3", equipment: "18/250", utilization: "95%", health: 61, latest_activity_at: "2026-09-23 10:40:00" },
    { id: "p2", name: "Plant 2 - Southern Annex", operational_status: "normal", alerts_active: "0", incidents_open: "0", equipment: "120/120", utilization: "65%", health: 99, latest_activity_at: "2026-09-23 10:32:00" },
    { id: "p4", name: "Plant 4 - Western Distribution", operational_status: "degraded", alerts_active: "2", incidents_open: "0", equipment: "23/31", utilization: "88%", health: 82, latest_activity_at: "2026-09-23 10:41:00" },
];

function previewSites() {
    const extra = [];
    for (let index = 5; index <= 24; index++) {
        extra.push({
            id: "p" + index,
            name: "Plant " + index,
            operational_status: "normal",
            alerts_active: "0",
            incidents_open: "0",
            equipment: "10/10",
            utilization: "70%",
            health: 90,
            latest_activity_at: "2026-09-23 10:00:00",
        });
    }
    return FEATURED_SITES.concat(extra);
}

export class MonitoringScreen extends Component {
    static template = "command_center.Monitoring";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.display = display;
        this.state = useState({
            loading: true,
            error: null,
            sites: [],
            siteOptions: [],
            filters: { site_id: "", operational_status: "" },
            range: "30",
            page: 1,
        });
        applyShellFilters(this.state.filters, this.props);
        onWillStart(() => this.refresh());
        onWillUpdateProps((next) => {
            if (next.shellSiteId !== this.props.shellSiteId) {
                applyShellFilters(this.state.filters, next);
                this.refresh();
            }
        });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("cc.ui.api", "get_monitoring_data", [
                compactFilters({
                    ...this.state.filters,
                    site_id: this.state.filters.site_id ? Number(this.state.filters.site_id) : "",
                }),
            ]);
            this.state.sites = data.sites || [];
            if (!this.state.filters.site_id) {
                this.state.siteOptions = data.sites || [];
            }
        } catch (err) {
            this.state.error = extractError(err);
            this.state.sites = [];
        } finally {
            this.state.loading = false;
        }
    }

    get isPreview() {
        return !(this.state.sites || []).length;
    }

    get displaySites() {
        return this.isPreview ? previewSites() : this.state.sites || [];
    }

    get pagedSites() {
        const start = (this.state.page - 1) * 4;
        return this.displaySites.slice(start, start + 4);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.displaySites.length / 4));
    }

    get pageStart() {
        return this.displaySites.length ? (this.state.page - 1) * 4 + 1 : 0;
    }

    get pageEnd() {
        return Math.min(this.state.page * 4, this.displaySites.length);
    }

    pagePrev() {
        this.state.page = Math.max(1, this.state.page - 1);
    }

    pageNext() {
        this.state.page = Math.min(this.pageCount, this.state.page + 1);
    }

    get siteKpis() {
        if (this.isPreview) {
            return [
                { key: "total", label: "Total Sites", value: 24, icon: "fa-sitemap", className: "" },
                { key: "normal", label: "Online", value: 22, icon: "fa-circle-o", className: "cc-stat-blue" },
                { key: "degraded", label: "Degraded", value: 1, icon: "fa-exclamation-triangle", className: "cc-stat-orange" },
                { key: "emergency", label: "Critical", value: 1, icon: "fa-circle", className: "cc-stat-red" },
                { key: "offline", label: "Offline", value: 0, icon: "fa-circle-o", className: "" },
                { key: "health", label: "Operational Health", value: "92%", icon: "fa-shield", className: "cc-stat-violet" },
            ];
        }
        const sites = this.state.sites || [];
        const count = (status) => sites.filter((site) => site.operational_status === status).length;
        const total = sites.length;
        const normal = count("normal");
        return [
            { key: "total", label: "Total Sites", value: total, icon: "fa-sitemap", className: "" },
            { key: "normal", label: "Online", value: normal, icon: "fa-circle-o", className: "cc-stat-blue" },
            { key: "degraded", label: "Degraded", value: count("degraded"), icon: "fa-exclamation-triangle", className: "cc-stat-orange" },
            { key: "emergency", label: "Critical", value: count("emergency"), icon: "fa-circle", className: "cc-stat-red" },
            { key: "offline", label: "Offline", value: count("offline"), icon: "fa-circle-o", className: "" },
            { key: "health", label: "Operational Health", value: total ? Math.round((normal / total) * 100) + "%" : "—", icon: "fa-shield", className: "cc-stat-violet" },
        ];
    }

    get telemetry() {
        if (this.isPreview) {
            return [
                { key: "eq", label: "Equipment Online", value: "98.2%", bars: 5, icon: "fa-sliders" },
                { key: "util", label: "Utility Status", value: "Stable", bars: 4, icon: "fa-sliders" },
                { key: "prod", label: "Production", value: "1,240 u/h" },
                { key: "temp", label: "Core Temp Avg", value: "42.5°C" },
                { key: "power", label: "Power Draw", value: "4.2 MW" },
                { key: "sys", label: "System Health", value: "Nominal", hint: "All services responding" },
            ];
        }
        const sites = this.state.sites || [];
        const total = sites.length || 1;
        const online = sites.filter((site) => site.operational_status === "normal").length;
        const critical = sites.filter((site) => site.operational_status === "emergency").length;
        const pct = Math.round((online / total) * 100);
        return [
            { key: "eq", label: "Equipment Online", value: pct + "%", bars: Math.max(1, Math.round(pct / 20)), icon: "fa-sliders" },
            { key: "util", label: "Utility Status", value: critical ? "Degraded" : "Stable", bars: critical ? 2 : 4, icon: "fa-sliders" },
            { key: "prod", label: "Production", value: "—" },
            { key: "temp", label: "Core Temp Avg", value: "—" },
            { key: "power", label: "Power Draw", value: "—" },
            { key: "sys", label: "System Health", value: critical ? "Attention" : "Nominal", hint: critical ? "Emergency sites present" : "All services responding" },
        ];
    }

    healthWidth(site) {
        if (site.health) {
            return site.health;
        }
        if (site.operational_status === "normal") {
            return 96;
        }
        if (site.operational_status === "degraded") {
            return 82;
        }
        if (site.operational_status === "emergency") {
            return 61;
        }
        return 8;
    }

    healthClass(site) {
        if (site.operational_status === "emergency") {
            return "cc-bar-crit";
        }
        if (site.operational_status === "degraded") {
            return "cc-bar-mid";
        }
        return "";
    }

    statusDot(site) {
        if (site.operational_status === "emergency") {
            return "cc-dot-on";
        }
        if (site.operational_status === "degraded") {
            return "cc-dot-warn";
        }
        if (site.operational_status === "normal") {
            return "cc-dot-ok";
        }
        return "";
    }

    statusLabel(status) {
        if (status === "normal") {
            return "Online";
        }
        if (status === "emergency") {
            return "Critical";
        }
        if (status === "degraded") {
            return "Degraded";
        }
        if (status === "offline") {
            return "Offline";
        }
        return display(status);
    }

    formatTime(value) {
        if (!value) {
            return "—";
        }
        const stamp = String(value).includes("T") ? value : String(value).replace(" ", "T");
        const date = new Date(stamp);
        if (Number.isNaN(date.getTime())) {
            return display(value);
        }
        return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
}
