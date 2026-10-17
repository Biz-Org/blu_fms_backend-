/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const RUL_FRAME_VERSION = "1.0.120";

/**
 * Embeds the RUL dashboard via iframe URL (Odoo strips iframe tags from Html fields).
 */
export class RulTobmDashboardHtmlField extends Component {
    static template = "maintenance.RulTobmDashboardHtmlField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.rootRef = useRef("root");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._onMessage = (ev) => this._handleIframeMessage(ev);
        this._switchInFlight = false;

        onMounted(() => {
            this._prepareRulFormShell();
            window.addEventListener("message", this._onMessage);
        });
        onWillUnmount(() => {
            window.removeEventListener("message", this._onMessage);
            this._teardownRulFormShell();
        });
    }

    get iframeSrc() {
        const id = this.props.record.resId;
        if (!id) {
            return "";
        }
        let url = `/maintenance/rul_tobm/dashboard/${id}?v=${RUL_FRAME_VERSION}`;
        const eq = this.props.record.data.equipment_id;
        if (eq && eq[0]) {
            url += `&equipment_id=${eq[0]}`;
        }
        return url;
    }

    _prepareRulFormShell() {
        const formEl =
            this.rootRef.el?.closest(".o_maint_rul_form") ||
            document.querySelector(".o_maint_rul_form");
        if (!formEl) {
            return;
        }
        document.documentElement.classList.add("o_maint_rul_lock_scroll");
        document.body.classList.add("o_maint_rul_fullscreen_body");
        const action =
            formEl.closest(".o_action") ||
            document.querySelector(".o_action:has(.o_maint_rul_form)") ||
            null;
        if (action) {
            action.classList.add("o_maint_rul_action");
        }
        action?.closest(".o_action_manager")?.classList.add("o_maint_rul_action_manager");
    }

    _teardownRulFormShell() {
        document.documentElement.classList.remove("o_maint_rul_lock_scroll");
        document.body.classList.remove("o_maint_rul_fullscreen_body");
        document.querySelectorAll(".o_maint_rul_action").forEach((el) => {
            el.classList.remove("o_maint_rul_action");
        });
        document.querySelectorAll(".o_maint_rul_action_manager").forEach((el) => {
            el.classList.remove("o_maint_rul_action_manager");
        });
    }

    async _handleIframeMessage(ev) {
        if (ev.data?.type !== "maintenance_rul_set_equipment") {
            return;
        }
        const eqId = ev.data.equipment_id;
        const record = this.props.record;
        if (!record?.resId || !eqId || this._switchInFlight) {
            return;
        }
        this._switchInFlight = true;
        try {
            await record.update({ equipment_id: eqId });
            if (record.dirty) {
                await record.save();
            }
            await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "action_refresh_rul_tobm_data",
                [[record.resId]]
            );
            await record.load();
        } catch (err) {
            const message =
                err?.data?.message || err?.message || "Could not switch equipment.";
            const lowered = String(message).toLowerCase();
            if (
                !lowered.includes("couldn't be established or was interrupted") &&
                !lowered.includes("connection to")
            ) {
                this.notification.add(message, { type: "danger" });
            }
        } finally {
            this._switchInFlight = false;
        }
    }
}

export const rulTobmDashboardHtmlField = {
    component: RulTobmDashboardHtmlField,
    supportedTypes: ["html"],
};

registry.category("fields").add("rul_tobm_dashboard_html", rulTobmDashboardHtmlField);
