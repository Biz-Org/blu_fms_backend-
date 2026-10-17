/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { MaintenancePlantDashboardScreen } from "./plant_dashboard_screen";

/**
 * Dashboard client action — content only.
 * Sidebar is provided globally by PlantMaintenanceGlobalSidebar.
 */
export class MaintenancePlantApp extends Component {
    static template = "maintenance.PlantApp";
    static components = { MaintenancePlantDashboardScreen };
    static props = { ...standardActionServiceProps };
}

registry.category("actions").add("maintenance_plant_app", MaintenancePlantApp, { force: true });
