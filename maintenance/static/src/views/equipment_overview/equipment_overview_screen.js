/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const EMPTY = {
    kpis: [],
    cards: [],
    counts: {},
    meta: {},
    teamOptions: [{ value: "all", label: _t("All Teams") }],
    categoryOptions: [{ value: "all", label: _t("All Types") }],
    domainOptions: [
        { value: "all", label: _t("All Maintenance") },
        { value: "plant", label: _t("Plant Maintenance") },
        { value: "facility", label: _t("Facility Management") },
    ],
    statusOptions: [{ value: "all", label: _t("All Status") }],
    sortOptions: [{ value: "name_asc", label: _t("Name (A-Z)") }],
};

export class MaintenanceEquipmentOverviewScreen extends Component {
    static template = "maintenance.EquipmentOverviewScreen";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            viewMode: "card",
            openDropdown: null,
            searchDraft: "",
            status: "all",
            team: "all",
            category: "all",
            maintenanceDomain: "all",
            sort: "name_asc",
            data: { ...EMPTY },
        });
        onWillStart(() => this.loadData());
    }

    get teamLabel() {
        return this.state.data.teamOptions.find((o) => o.value === String(this.state.team))?.label || _t("All Teams");
    }

    get domainLabel() {
        return (
            (this.state.data.domainOptions || []).find(
                (o) => o.value === String(this.state.maintenanceDomain)
            )?.label || _t("All Maintenance")
        );
    }

    get pageTitle() {
        return this.state.data.meta?.title || _t("Equipment & Assets");
    }

    get pageSubtitle() {
        return (
            this.state.data.meta?.subtitle ||
            _t("Manage industrial equipment and facility assets.")
        );
    }

    get statusLabel() {
        return this.state.data.statusOptions.find((o) => o.value === this.state.status)?.label || _t("All Status");
    }

    get categoryLabel() {
        return this.state.data.categoryOptions.find((o) => o.value === String(this.state.category))?.label || _t("All Types");
    }

    get sortLabel() {
        return this.state.data.sortOptions.find((o) => o.value === this.state.sort)?.label || _t("Name (A-Z)");
    }

    isFilterActive(key, value) {
        return String(this.state[key]) === String(value);
    }

    closeDropdowns() {
        this.state.openDropdown = null;
    }

    toggleDropdown(name, ev) {
        ev?.stopPropagation?.();
        this.state.openDropdown = this.state.openDropdown === name ? null : name;
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    onSearchInput(ev) {
        this.state.searchDraft = ev.target.value || "";
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadData(), 280);
    }

    setFilter(key, value) {
        this.state[key] = value;
        if (key === "maintenanceDomain") {
            this.state.category = "all";
            this.state.team = "all";
        }
        this.state.openDropdown = null;
        this.loadData();
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await this.orm.call("maintenance.equipment", "get_equipment_overview", [], {
                filters: {
                    search: this.state.searchDraft,
                    status: this.state.status,
                    team_id: this.state.team,
                    category_id: this.state.category,
                    maintenance_domain: this.state.maintenanceDomain,
                    sort: this.state.sort,
                },
            });
            this.state.data = { ...EMPTY, ...payload };
        } catch (err) {
            this.state.error = err?.data?.message || err?.message || _t("Could not load equipment.");
        } finally {
            this.state.loading = false;
        }
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

    newRequest(equipmentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Maintenance Request"),
            res_model: "maintenance.request",
            views: [[false, "form"]],
            target: "current",
            context: equipmentId ? { default_equipment_id: equipmentId } : {},
        });
    }

    onAction(name) {
        this.closeDropdowns();
        if (name === "refresh") {
            this.loadData();
            return;
        }
        if (name === "new") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("New Equipment"),
                res_model: "maintenance.equipment",
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        if (name === "import") {
            this.action.doAction("maintenance.action_maintenance_equipment_import_wizard");
            return;
        }
        if (name === "uploads") {
            this.action.doAction("maintenance.action_maintenance_equipment_import_log");
            return;
        }
        if (name === "list_action") {
            this.action.doAction("maintenance.hr_equipment_action");
        }
    }
}
