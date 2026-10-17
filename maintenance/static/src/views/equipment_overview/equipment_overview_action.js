/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { MaintenanceEquipmentOverviewScreen } from "./equipment_overview_screen";

export class MaintenanceEquipmentOverviewApp extends Component {
    static template = "maintenance.EquipmentOverviewApp";
    static components = { MaintenanceEquipmentOverviewScreen };
    static props = { ...standardActionServiceProps };
}

registry.category("actions").add(
    "maintenance_equipment_overview",
    MaintenanceEquipmentOverviewApp,
    { force: true }
);
