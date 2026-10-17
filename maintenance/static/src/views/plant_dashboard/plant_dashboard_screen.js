/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const EMPTY_DATA = {
    kpis: [],
    equipmentHealth: [],
    requestStatus: [],
    workOrderStatus: [],
    upcomingMaintenance: [],
    recentWorkOrders: [],
    attentionEquipment: [],
    weeklyTrend: [],
    meta: {},
    teamOptions: [{ value: "all", label: _t("All Teams") }],
    domainOptions: [
        { value: "all", label: _t("All Maintenance") },
        { value: "plant", label: _t("Plant Maintenance") },
        { value: "facility", label: _t("Facility Management") },
    ],
};

export class MaintenancePlantDashboardScreen extends Component {
    static template = "maintenance.PlantDashboardScreen";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            openDropdown: null,
            team: "all",
            maintenanceDomain: "all",
            data: { ...EMPTY_DATA },
        });
        onWillStart(() => this.loadData());
    }

    get teamLabel() {
        const opt = this.state.data.teamOptions.find((o) => o.value === String(this.state.team));
        return opt?.label || _t("All Teams");
    }

    get domainLabel() {
        const opt = (this.state.data.domainOptions || []).find(
            (o) => o.value === String(this.state.maintenanceDomain)
        );
        return opt?.label || _t("All Maintenance");
    }

    get pageTitle() {
        return this.state.data.meta?.title || _t("Maintenance Dashboard");
    }

    get pageSubtitle() {
        return (
            this.state.data.meta?.subtitle ||
            _t("Live equipment health, requests, work orders, and upcoming preventive work.")
        );
    }

    get donutStyle() {
        const items = this.state.data.equipmentHealth || [];
        if (!items.length) {
            return "background: #e5e7eb;";
        }
        const colors = {
            success: "#10b981",
            warning: "#f59e0b",
            danger: "#ef4444",
            muted: "#9ca3af",
            info: "#3b82f6",
            purple: "#7c3aed",
        };
        let cursor = 0;
        const parts = [];
        for (const item of items) {
            const start = cursor;
            cursor += item.pct || 0;
            parts.push(`${colors[item.variant] || "#9ca3af"} ${start}% ${cursor}%`);
        }
        if (cursor < 100) {
            parts.push(`#e5e7eb ${cursor}% 100%`);
        }
        return `background: conic-gradient(${parts.join(", ")});`;
    }

    closeDropdowns() {
        this.state.openDropdown = null;
    }

    toggleDropdown(name, ev) {
        ev?.stopPropagation?.();
        this.state.openDropdown = this.state.openDropdown === name ? null : name;
    }

    setTeam(value) {
        this.state.team = value;
        this.state.openDropdown = null;
        this.loadData();
    }

    setDomain(value) {
        this.state.maintenanceDomain = value;
        this.state.team = "all";
        this.state.openDropdown = null;
        this.loadData();
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await this.orm.call("maintenance.team", "get_plant_app_dashboard", [], {
                filters: {
                    team_id: this.state.team,
                    maintenance_domain: this.state.maintenanceDomain,
                },
            });
            this.state.data = { ...EMPTY_DATA, ...payload };
            const trend = (payload.weeklyTrend || []).map((week) => ({
                ...week,
                createdHeight: week.created ? Math.max(week.createdPct || 0, 8) : 0,
                closedHeight: week.closed ? Math.max(week.closedPct || 0, 8) : 0,
                createdTitle: `Created: ${week.created}`,
                closedTitle: `Completed: ${week.closed}`,
            }));
            this.state.data.weeklyTrend = trend;
        } catch (err) {
            this.state.error = err?.data?.message || err?.message || _t("Could not load dashboard.");
        } finally {
            this.state.loading = false;
        }
    }

    openRequest(id) {
        if (!id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "maintenance.request",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openEquipment(id) {
        if (!id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "maintenance.equipment",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onAction(name) {
        this.closeDropdowns();
        if (name === "refresh") {
            await this.loadData();
            this.notification.add(_t("Dashboard refreshed."), { type: "success" });
            return;
        }
        if (name === "equipment") {
            this.action.doAction("maintenance.maintenance_equipment_overview_action");
            return;
        }
        if (name === "requests") {
            this.action.doAction("maintenance.hr_equipment_request_action");
            return;
        }
        if (name === "work_orders") {
            this.action.doAction("maintenance.maintenance_work_orders_action");
            return;
        }
        if (name === "new_request") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("New Maintenance Request"),
                res_model: "maintenance.request",
                views: [[false, "form"]],
                target: "current",
            });
        }
    }
}
