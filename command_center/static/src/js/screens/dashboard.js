/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, display, extractError, workflowSteps } from "../cc_utils";

export class DashboardScreen extends Component {
    static template = "command_center.Dashboard";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.display = display;
        this.state = useState({
            loading: true,
            error: null,
            kpis: null,
            recent_activity: [],
            sites_summary: [],
        });
        onWillStart(() => this.refresh());
        this.workflowSteps = workflowSteps(null, "module");
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("cc.ui.api", "get_dashboard_data", []);
            this.state.kpis = data.kpis || {};
            this.state.recent_activity = data.recent_activity || [];
            this.state.sites_summary = data.sites_summary || [];
        } catch (err) {
            this.state.error = extractError(err);
            this.state.kpis = null;
            this.state.recent_activity = [];
            this.state.sites_summary = [];
        } finally {
            this.state.loading = false;
        }
    }

    get isPreview() {
        const kpis = this.state.kpis || {};
        return !(
            Number(kpis.sites_total) ||
            Number(kpis.alerts_active) ||
            Number(kpis.incidents_open) ||
            Number(kpis.emergencies_active) ||
            (this.state.recent_activity || []).length ||
            (this.state.sites_summary || []).length
        );
    }

    get kpiItems() {
        if (this.isPreview) {
            return [
                { key: "sites_total", label: "Total Sites", value: 24, hint: "22 Online", hintIcon: "fa-circle cc-hint-ok", icon: "fa-building-o", className: "" },
                { key: "alerts_active", label: "Active Alerts", value: 18, hint: "4 Critical", hintIcon: "fa-exclamation-triangle cc-hint-warn", icon: "fa-exclamation-triangle", className: "cc-kpi-alert" },
                { key: "incidents_open", label: "Open Incidents", value: 7, hint: "2 High Priority", hintIcon: "fa-circle cc-hint-mid", icon: "fa-exclamation-circle", className: "" },
                { key: "emergencies_active", label: "Emergency Events", value: 2, hint: "1 Active", hintIcon: "fa-circle cc-hint-crit", icon: "fa-warning", className: "cc-kpi-emergency" },
                { key: "health", label: "Operational Health", value: "92%", hint: "+4% vs last week", hintIcon: "fa-arrow-up cc-hint-ok", icon: "fa-heartbeat", className: "" },
                { key: "unresolved_overdue", label: "Escalations", value: 5, hint: "2 Awaiting Response", hintIcon: "fa-clock-o", icon: "fa-level-up", className: "" },
            ];
        }
        const kpis = this.state.kpis || {};
        const total = Number(kpis.sites_total) || 0;
        const operational = Number(kpis.sites_operational) || 0;
        const critical = Number(kpis.alerts_critical) || 0;
        const highIncidents = Number(kpis.incidents_high) || 0;
        const emergencies = Number(kpis.emergencies_active) || 0;
        const overdue = Number(kpis.unresolved_overdue) || 0;
        const health = total ? Math.round((operational / total) * 100) + "%" : "0%";
        return [
            { key: "sites_total", label: "Total Sites", value: total, hint: operational + " Online", hintIcon: "fa-circle cc-hint-ok", icon: "fa-building-o", className: "" },
            { key: "alerts_active", label: "Active Alerts", value: Number(kpis.alerts_active) || 0, hint: critical + " Critical", hintIcon: "fa-exclamation-triangle cc-hint-warn", icon: "fa-exclamation-triangle", className: "cc-kpi-alert" },
            { key: "incidents_open", label: "Open Incidents", value: Number(kpis.incidents_open) || 0, hint: highIncidents + " High Priority", hintIcon: "fa-circle cc-hint-mid", icon: "fa-exclamation-circle", className: "" },
            { key: "emergencies_active", label: "Emergency Events", value: emergencies, hint: emergencies + " Active", hintIcon: "fa-circle cc-hint-crit", icon: "fa-warning", className: emergencies ? "cc-kpi-emergency" : "" },
            { key: "health", label: "Operational Health", value: health, hint: operational + " of " + total + " sites", hintIcon: "fa-arrow-up cc-hint-ok", icon: "fa-heartbeat", className: "" },
            { key: "unresolved_overdue", label: "Escalations", value: overdue, hint: overdue + " Awaiting Response", hintIcon: "fa-clock-o", icon: "fa-level-up", className: "" },
        ];
    }

    get visibleActivity() {
        if (this.isPreview) {
            return [
                { id: "p1", model: "cc.alert", at: "2026-09-23 10:42:00", site_name: "Plant Alpha - NY", name: "Power Grid Fluctuation", event_type: "Infrastructure", severity: "critical", state: "investigating" },
                { id: "p2", model: "cc.incident", at: "2026-09-23 10:15:00", site_name: "Facility Beta - TX", name: "Mould Line Jammed", event_type: "Production", severity: "high", state: "assigned" },
                { id: "p3", model: "cc.alert", at: "2026-09-23 09:30:00", site_name: "Plant Delta - OH", name: "Mixer Sensor Drift", event_type: "Equipment", severity: "medium", state: "open" },
                { id: "p4", model: "cc.incident", at: "2026-09-23 08:45:00", site_name: "Depot Gamma - FL", name: "Network Latency Spike", event_type: "IT System", severity: "low", state: "resolved" },
                { id: "p5", model: "cc.alert", at: "2026-09-23 08:10:00", site_name: "Plant Alpha - NY", name: "Routine Safety Check", event_type: "Audit", severity: "low", state: "completed" },
            ];
        }
        const query = (this.props.shellSearch || "").toLowerCase();
        const siteId = this.props.shellSiteId ? Number(this.props.shellSiteId) : 0;
        return (this.state.recent_activity || []).filter((row) => {
            if (siteId && Number(row.site_id) !== siteId) {
                return false;
            }
            if (!query) {
                return true;
            }
            return [row.name, row.model, row.state, row.site_name, row.event_type, row.severity]
                .join(" ")
                .toLowerCase()
                .includes(query);
        });
    }

    get visibleSites() {
        const siteId = this.props.shellSiteId ? Number(this.props.shellSiteId) : 0;
        const query = (this.props.shellSearch || "").toLowerCase();
        return (this.state.sites_summary || []).filter((site) => {
            if (siteId && site.id !== siteId) {
                return false;
            }
            if (!query) {
                return true;
            }
            return [site.name, site.code, site.operational_status].join(" ").toLowerCase().includes(query);
        });
    }

    get siteStatus() {
        if (this.isPreview) {
            return [
                { key: "online", label: "Online", value: 22, className: "cc-dot-ok" },
                { key: "warning", label: "Warning", value: 1, className: "cc-dot-warn" },
                { key: "critical", label: "Critical", value: 1, className: "cc-dot-on" },
                { key: "offline", label: "Offline", value: 0, className: "" },
            ];
        }
        const sites = this.visibleSites;
        return [
            { key: "online", label: "Online", value: sites.filter((site) => site.operational_status === "normal").length, className: "cc-dot-ok" },
            { key: "warning", label: "Warning", value: sites.filter((site) => site.operational_status === "degraded").length, className: "cc-dot-warn" },
            { key: "critical", label: "Critical", value: sites.filter((site) => site.operational_status === "emergency").length, className: "cc-dot-on" },
            { key: "offline", label: "Offline", value: sites.filter((site) => site.operational_status === "offline").length, className: "" },
        ];
    }

    get actionQueue() {
        if (this.isPreview) {
            return [
                { key: "emergency", label: "Acknowledge Emergency (Site 4)", screen: "emergency" },
                { key: "critical", label: "Review 4 Critical Alerts", screen: "alerts" },
                { key: "incidents", label: "Assign 2 Open Incidents", screen: "incidents" },
            ];
        }
        const kpis = this.state.kpis || {};
        const emergencies = Number(kpis.emergencies_active) || 0;
        const critical = Number(kpis.alerts_critical) || 0;
        const incidents = Number(kpis.incidents_open) || 0;
        return [
            {
                key: "emergency",
                label: emergencies ? "Acknowledge Emergency (" + emergencies + ")" : "Acknowledge Emergency",
                screen: "emergency",
            },
            {
                key: "critical",
                label: "Review " + critical + " Critical Alerts",
                screen: "alerts",
            },
            {
                key: "incidents",
                label: "Assign " + incidents + " Open Incidents",
                screen: "incidents",
            },
        ];
    }

    get queueTotal() {
        return this.actionQueue.length;
    }

    get alertSummary() {
        if (this.isPreview) {
            return [
                { key: "critical", label: "Critical", value: 4, className: "cc-dot-on" },
                { key: "high", label: "High", value: 6, className: "cc-dot-warn" },
                { key: "medium", label: "Medium", value: 3, className: "cc-dot-mid" },
                { key: "low", label: "Low", value: 0, className: "cc-dot-low" },
            ];
        }
        const kpis = this.state.kpis || {};
        return [
            { key: "critical", label: "Critical", value: Number(kpis.alerts_critical) || 0, className: "cc-dot-on" },
            { key: "high", label: "High", value: Number(kpis.alerts_high) || 0, className: "cc-dot-warn" },
            { key: "medium", label: "Medium", value: Number(kpis.alerts_medium) || 0, className: "cc-dot-mid" },
            { key: "low", label: "Low", value: Number(kpis.alerts_low) || 0, className: "cc-dot-low" },
        ];
    }

    get hasTrend() {
        return this.isPreview || Boolean(
            Number((this.state.kpis || {}).sites_total) ||
            Number((this.state.kpis || {}).alerts_active) ||
            Number((this.state.kpis || {}).incidents_open) ||
            Number((this.state.kpis || {}).emergencies_active)
        );
    }

    get trendLine() {
        return "0,80 80,78 160,76 240,70 320,28 400,8";
    }

    get trendFill() {
        return "0,80 80,78 160,76 240,70 320,28 400,8 400,160 0,160";
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

    eventType(row) {
        return row.event_type || (row.model === "cc.incident" ? "Incident" : "Alert");
    }

    openScreen(screen) {
        if (this.props.navigate) {
            this.props.navigate(screen);
        }
    }

    openActivity(row) {
        this.openScreen(row.model === "cc.incident" ? "incidents" : "alerts");
    }
}
