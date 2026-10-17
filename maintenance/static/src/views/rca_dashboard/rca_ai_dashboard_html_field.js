/** @odoo-module **/

import { Component, markup, onMounted, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Renders RCA dashboard HTML directly in DOM (no iframe). */
export class RcaAiDashboardHtmlField extends Component {
    static template = "maintenance.RcaAiDashboardHtmlField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.rootRef = useRef("root");
        onMounted(() => this._bindRcaTabs());
        onPatched(() => this._bindRcaTabs());
    }

    _bindRcaTabs() {
        const host = this.rootRef.el;
        if (!host) {
            return;
        }
        const dash = host.querySelector(".o_pm_ai_rca_dash");
        if (!dash || dash.dataset.rcaTabsBound === "1") {
            return;
        }
        dash.dataset.rcaTabsBound = "1";
        dash.addEventListener("click", (ev) => {
            const tab = ev.target.closest(".o_pm_rca_view_tab");
            if (!tab || !dash.contains(tab)) {
                return;
            }
            const key = tab.dataset.rcaTab;
            dash.querySelectorAll(".o_pm_rca_view_tab").forEach((el) => {
                el.classList.toggle("is-active", el === tab);
            });
            dash.querySelectorAll(".o_pm_rca_view_panel").forEach((el) => {
                el.classList.toggle("is-visible", el.dataset.rcaPanel === key);
            });
            dash.dataset.rcaActiveTab = key;
        });
    }

    get htmlValue() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return markup("");
        }
        return value?.constructor?.name === "Markup" ? value : markup(value);
    }
}

export const rcaAiDashboardHtmlField = {
    component: RcaAiDashboardHtmlField,
    supportedTypes: ["html"],
};

registry.category("fields").add("rca_ai_dashboard_html", rcaAiDashboardHtmlField);
