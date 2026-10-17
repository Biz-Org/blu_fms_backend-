/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const RUL_EMBED_VERSION = "1.0.120";

/**
 * Full RUL dashboard via HTTP iframe (no Html field — Odoo strips tags/CSS).
 */
export class MaintenanceRulTobmEmbedAction extends Component {
    static template = "maintenance.RulTobmEmbedAction";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ iframeKey: 0 });
        this._onMessage = (ev) => this._handleIframeMessage(ev);
        this._switchInFlight = false;

        onMounted(() => {
            document.documentElement.classList.add("o_maint_rul_lock_scroll");
            document.body.classList.add("o_maint_rul_fullscreen_body");
            const action = document.querySelector(".o_action:has(.o_maint_rul_embed_host)");
            if (action) {
                action.classList.add("o_maint_rul_action");
                action.closest(".o_action_manager")?.classList.add("o_maint_rul_action_manager");
            }
            window.addEventListener("message", this._onMessage);
        });

        onWillUnmount(() => {
            window.removeEventListener("message", this._onMessage);
            document.documentElement.classList.remove("o_maint_rul_lock_scroll");
            document.body.classList.remove("o_maint_rul_fullscreen_body");
            document.querySelectorAll(".o_maint_rul_action").forEach((el) => {
                el.classList.remove("o_maint_rul_action");
            });
            document.querySelectorAll(".o_maint_rul_action_manager").forEach((el) => {
                el.classList.remove("o_maint_rul_action_manager");
            });
        });
    }

    get dashboardId() {
        const params = this.props.action?.params || {};
        if (params.res_id) {
            return params.res_id;
        }
        const ctx = this.props.action?.context || {};
        if (ctx.active_id) {
            return ctx.active_id;
        }
        return 1;
    }

    get iframeSrc() {
        const key = this.state.iframeKey;
        return `/maintenance/rul_tobm/dashboard/${this.dashboardId}?v=${RUL_EMBED_VERSION}&k=${key}`;
    }

    async _handleIframeMessage(ev) {
        if (ev.data?.type !== "maintenance_rul_set_equipment") {
            return;
        }
        const eqId = ev.data.equipment_id;
        const dashId = this.dashboardId;
        if (!dashId || !eqId || this._switchInFlight) {
            return;
        }
        this._switchInFlight = true;
        try {
            await this.orm.write("maintenance.rul.tobm.dashboard", [dashId], {
                equipment_id: eqId,
            });
            await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "action_refresh_rul_tobm_data",
                [[dashId]]
            );
            this.state.iframeKey += 1;
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

registry.category("actions").add("maintenance_rul_tobm_embed", MaintenanceRulTobmEmbedAction);
