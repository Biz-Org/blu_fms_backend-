/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { MaintenanceRulTobmDashboardClient } from "./rul_tobm_dashboard_client";

/**
 * Embeds the native Owl RUL dashboard inside a standard form view (purple Odoo menu bar).
 */
export class RulTobmOwlDashboardField extends Component {
    static template = "maintenance.RulTobmOwlDashboardField";
    static components = { MaintenanceRulTobmDashboardClient };
    static props = {
        ...standardFieldProps,
    };

    get dashboardKey() {
        const record = this.props.record;
        if (!record?.resId) {
            return "";
        }
        const data = record.data;
        return [
            record.resId,
            data.analysis_period_days,
            data.fleet_vehicle_scope,
            data.category_id,
            data.equipment_id,
        ].join("|");
    }
}

export const rulTobmOwlDashboardField = {
    component: RulTobmOwlDashboardField,
    supportedTypes: ["char", "text", "html"],
};

registry.category("fields").add("rul_tobm_owl_dashboard", rulTobmOwlDashboardField);
