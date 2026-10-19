/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "dashboard", label: "ESG Dashboard", icon: "fa-th-large" },
    { id: "energy", label: "Energy Tracking", icon: "fa-bolt" },
    { id: "water", label: "Water Management", icon: "fa-tint" },
    { id: "carbon", label: "Carbon Footprint", icon: "fa-cloud" },
    { id: "kpis", label: "Sustainability KPIs", icon: "fa-bar-chart" },
    { id: "energy_analysis", label: "Energy Analysis", icon: "fa-line-chart" },
    { id: "water_analysis", label: "Water Usage Analysis", icon: "fa-area-chart" },
    { id: "emissions", label: "Carbon Emissions", icon: "fa-leaf" },
    { id: "targets", label: "Sustainability Targets", icon: "fa-bullseye" },
    { id: "reporting", label: "ESG Reporting", icon: "fa-file-text-o" },
];

const STATUS = {
    on_track: "On Track",
    review: "Review",
    focus: "Focus",
    at_risk: "At Risk",
    achieved: "Achieved",
    below: "Below Target",
    off_track: "Off Track",
    monitor: "Monitor",
    optimized: "Optimized",
    critical: "Critical",
    stable: "Stable",
    increased: "Increased",
};

export class EsgPortal extends Component {
    static template = "esg_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.navItems = NAV;
        this.state = useState({
            page: "dashboard",
            loading: true,
            saving: false,
            data: {},
            search: "",
            filters: { property_id: "0", building_id: "0", period: "ytd" },
            show: "",
            targetId: false,
            targetFilter: "all",
            reportTemplate: "energy",
            reading: this.emptyReading("energy"),
            kpi: { name: "", category: "energy", target: "", unit: "kWh", direction: "lower", actual: "" },
            target: this.emptyTarget(),
        });
        onWillStart(() => this.load());
    }

    emptyReading(metric) {
        const today = new Date().toISOString().slice(0, 10);
        return { metric, property_id: "", building_id: "", date: today, value: "", scope: "2", peak: false, segment: "office" };
    }

    emptyTarget() {
        return { name: "", subtitle: "", category: "energy", metric: "energy", measure: "total", direction: "lower", baseline: "", target_value: "", unit: "kWh", due_date: "" };
    }

    async load() {
        const firstLoad = !this.state.data.properties;
        if (firstLoad) {
            this.state.loading = true;
        }
        try {
            const data = await this.orm.call("esg.portal", "get_dashboard_data", [this.state.filters]);
            this.state.data = data;
            const applied = data.filters || {};
            this.state.filters.property_id = String(applied.property_id || 0);
            this.state.filters.building_id = String(applied.building_id || 0);
            this.state.filters.period = applied.period || "ytd";
        } catch (error) {
            this.notification.add(error?.data?.message || "Could not load ESG data.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async call(method, args) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("esg.portal", method, args);
            this.state.show = "";
            this.notification.add("Saved.", { type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        this.state.search = "";
        this.state.show = "";
    }

    pageTitle() {
        return (NAV.find((item) => item.id === this.state.page) || NAV[0]).label;
    }

    dash() { return this.state.data.dashboard || {}; }
    energy() { return this.state.data.energy || {}; }
    water() { return this.state.data.water || {}; }
    carbon() { return this.state.data.carbon || {}; }
    analysis() { return this.state.data.analysis || {}; }
    waterAnalysis() { return this.state.data.water_analysis || {}; }
    emissions() { return this.state.data.emissions || {}; }
    kpis() { return this.state.data.kpis || []; }
    targets() { return this.state.data.targets || []; }
    activities() { return this.state.data.activities || []; }
    reports() { return this.state.data.reports || []; }

    properties() { return this.state.data.properties || []; }

    buildings() {
        const pid = Number(this.state.filters.property_id || 0);
        const rows = this.state.data.buildings || [];
        return pid ? rows.filter((row) => row.property_id === pid) : rows;
    }

    onPropertyChange(ev) {
        this.state.filters.property_id = ev.target.value;
        const current = String(this.state.filters.building_id || "0");
        const allowed = this.buildings();
        if (current !== "0" && !allowed.some((row) => String(row.id) === current)) {
            this.state.filters.building_id = "0";
        }
    }

    formBuildings() {
        const pid = Number(this.state.reading.property_id || 0);
        const rows = this.state.data.buildings || [];
        return pid ? rows.filter((row) => row.property_id === pid) : rows;
    }

    statusLabel(key) { return STATUS[key] || key; }

    deltaClass(value, invert) {
        const good = invert ? value > 0 : value < 0;
        if (!value) return "is-flat";
        return good ? "is-good" : "is-bad";
    }

    matches(row) {
        const query = (this.state.search || "").trim().toLowerCase();
        if (!query) return true;
        return JSON.stringify(row).toLowerCase().includes(query);
    }

    visible(rows) { return (rows || []).filter((row) => this.matches(row)); }

    targetCount(mode) {
        return this.targets().filter((row) => {
            if (mode === "on_track") return row.status === "on_track" || row.status === "review";
            if (mode === "at_risk") return row.status === "at_risk" || row.status === "below";
            if (mode === "achieved") return row.status === "achieved";
            return true;
        }).length;
    }

    filteredTargets() {
        const mode = this.state.targetFilter;
        return this.visible(this.targets()).filter((row) => {
            if (mode === "on_track") return row.status === "on_track" || row.status === "review";
            if (mode === "at_risk") return row.status === "at_risk" || row.status === "below";
            if (mode === "achieved") return row.status === "achieved";
            return true;
        });
    }

    categoryBars() {
        const groups = {};
        for (const row of this.targets()) {
            groups[row.category] = groups[row.category] || [];
            groups[row.category].push(row.achievement);
        }
        return Object.keys(groups).map((key) => {
            const values = groups[key];
            const avg = Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
            return { label: key, pct: avg };
        });
    }

    overall() {
        const rows = this.targets();
        if (!rows.length) return 0;
        return Math.round(rows.reduce((sum, row) => sum + row.achievement, 0) / rows.length);
    }

    share(part, total) {
        if (!total) return 0;
        return Math.round((part / total) * 100);
    }

    donutStyle(parts) {
        let cursor = 0;
        const colors = ["#7c3aed", "#c4b5fd", "#ede9fe", "#a78bfa", "#8b5cf6"];
        const stops = (parts || []).map((part, index) => {
            const start = cursor;
            cursor += Number(part.pct || 0);
            return `${part.color || colors[index % colors.length]} ${start}% ${cursor}%`;
        });
        return `background: conic-gradient(${stops.join(", ") || "#efeaff 0 100%"})`;
    }

    linePoints(series) {
        const rows = series || [];
        if (!rows.length) return "";
        const values = rows.map((row) => Number(row.value) || 0);
        const rawMax = Math.max(...values, 1);
        const rawMin = Math.min(...values);
        const pad = Math.max((rawMax - rawMin) * 0.25, rawMax * 0.04);
        const min = Math.max(0, rawMin - pad);
        const max = rawMax + pad;
        const span = Math.max(max - min, 1);
        const top = 10;
        const inner = 76;
        return rows.map((row, index) => {
            const x = rows.length === 1 ? 140 : (index / (rows.length - 1)) * 280;
            const y = top + (1 - ((Number(row.value) || 0) - min) / span) * inner;
            return `${Math.round(x)},${Math.round(y)}`;
        }).join(" ");
    }

    openReading(metric) {
        this.state.reading = this.emptyReading(metric);
        this.state.show = "reading";
    }

    waterGoal(row) {
        const fill = Math.max(0, Math.min(100, Number(row.goal_fill) || 0));
        return [
            { pct: fill, color: "#7c3aed" },
            { pct: 100 - fill, color: "#efeaff" },
        ];
    }

    energyChart(series) {
        const rows = series || [];
        const width = 640;
        const height = 132;
        const left = 24;
        const right = 24;
        const top = 18;
        const bottom = 22;
        const values = rows.map((row) => Number(row.value) || 0);
        const rawMax = Math.max(...values, 1);
        const rawMin = values.length ? Math.min(...values) : 0;
        const pad = Math.max((rawMax - rawMin) * 0.2, rawMax * 0.04);
        const min = Math.max(0, rawMin - pad);
        const max = rawMax + pad;
        const span = Math.max(max - min, 1);
        const innerW = width - left - right;
        const innerH = height - top - bottom;
        const dots = rows.map((row, index) => {
            const x = rows.length === 1 ? left + innerW / 2 : left + (index / (rows.length - 1)) * innerW;
            const y = top + (1 - ((Number(row.value) || 0) - min) / span) * innerH;
            return {
                x: Math.round(x * 10) / 10,
                y: Math.round(y * 10) / 10,
                label: row.label,
                value: row.label_value,
            };
        });
        const line = dots.map((dot) => `${dot.x},${dot.y}`).join(" ");
        const area = dots.length
            ? `M ${dots[0].x} ${top + innerH} L ${dots.map((dot) => `${dot.x} ${dot.y}`).join(" L ")} L ${dots[dots.length - 1].x} ${top + innerH} Z`
            : "";
        return { dots, line, area, baseline: top + innerH, labelY: height - 4 };
    }

    async applyFilters() {
        await this.load();
    }

    async saveReading() {
        await this.call("add_reading", [{ ...this.state.reading, filters: this.state.filters }]);
        this.state.reading = this.emptyReading(this.state.reading.metric);
    }

    async saveKpi() {
        await this.call("add_kpi", [{ ...this.state.kpi, filters: this.state.filters }]);
        this.state.kpi = { name: "", category: "energy", target: "", unit: "kWh", direction: "lower", actual: "" };
    }

    async saveTarget() {
        const payload = { ...this.state.target, filters: this.state.filters };
        if (this.state.targetId) {
            await this.call("update_target", [this.state.targetId, payload]);
        } else {
            await this.call("add_target", [payload]);
        }
        this.state.targetId = false;
        this.state.target = this.emptyTarget();
    }

    editTarget(row) {
        this.state.targetId = row.id;
        this.state.show = "target";
        this.state.target = {
            name: row.name,
            subtitle: row.subtitle,
            category: row.category,
            metric: row.metric,
            measure: row.measure,
            direction: row.direction,
            baseline: row.baseline,
            target_value: row.target,
            unit: row.unit,
            due_date: row.due_date,
        };
        this.state.page = "targets";
    }

    async generateReport() {
        await this.call("generate_report", [{
            template: this.state.reportTemplate,
            property_id: this.state.filters.property_id,
            building_id: this.state.filters.building_id,
            filters: this.state.filters,
        }]);
    }

    async download(template) {
        try {
            const file = await this.orm.call("esg.portal", "report_file", [template || this.state.reportTemplate, this.state.filters]);
            const blob = new Blob([file.content], { type: "text/csv;charset=utf-8" });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = file.filename;
            link.click();
            URL.revokeObjectURL(link.href);
        } catch (error) {
            this.notification.add(error?.data?.message || "Export failed.", { type: "danger" });
        }
    }
}

registry.category("actions").add("esg_management.portal", EsgPortal);
