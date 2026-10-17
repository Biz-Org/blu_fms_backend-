/** @odoo-module **/

import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillUnmount, useEffect } from "@odoo/owl";
import { ensureRulTobmInlineStyles } from "./rul_tobm_inline_styles";

const FILTER_FIELDS = [
    "analysis_period_days",
    "fleet_vehicle_scope",
    "category_id",
    "equipment_id",
];

export class MaintenanceRulTobmFormController extends formView.Controller {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this._busChannel = null;
        this._filterDebounce = null;
        this._lastFilterSnapshot = undefined;
        this._reloadInFlight = false;
        this._onBusRefresh = (payload) => {
            const companyId =
                this.model.root.data.company_id && this.model.root.data.company_id[0];
            if (companyId && payload.company_id === companyId) {
                this._reloadDashboard(false);
            }
        };

        this._actionRoot = null;

        onMounted(() => {
            ensureRulTobmInlineStyles();
            this._prepareRulFormShell();
            this._subscribeBus();
            this._onWindowFocus = () => this._reloadDashboard(false);
            window.addEventListener("focus", this._onWindowFocus);
        });
        onPatched(() => this._prepareRulFormShell());
        onWillUnmount(() => {
            if (this._actionRoot) {
                this._actionRoot.classList.remove("o_pm_rca_action");
                this._actionRoot = null;
            }
            document.body.classList.remove("o_pm_rca_fullscreen_body");
            this._unsubscribeBus();
            if (this._onWindowFocus) {
                window.removeEventListener("focus", this._onWindowFocus);
            }
            if (this._filterDebounce) {
                clearTimeout(this._filterDebounce);
            }
        });

        useEffect(
            () => {
                const record = this.model.root;
                if (!record?.resId) {
                    return;
                }
                const snapshot = JSON.stringify(
                    FILTER_FIELDS.map((fieldName) => record.data[fieldName])
                );
                if (
                    this._lastFilterSnapshot !== undefined &&
                    this._lastFilterSnapshot !== snapshot
                ) {
                    this._scheduleFilterApply();
                }
                this._lastFilterSnapshot = snapshot;
            },
            () => {
                const record = this.model.root;
                if (!record?.resId) {
                    return [record?.resId];
                }
                return FILTER_FIELDS.map((fieldName) => record.data[fieldName]);
            }
        );
    }

    _getFormEl() {
        if (this.el?.classList?.contains("o_maint_rul_form")) {
            return this.el;
        }
        return document.querySelector(".o_maint_rul_form");
    }

    _prepareRulFormShell() {
        const formEl = this._getFormEl();
        if (!formEl) {
            return;
        }
        formEl.classList.add("o_form_view");
        document.body.classList.add("o_pm_rca_fullscreen_body");
        const nav =
            document.querySelector(".o_main_navbar") ||
            document.querySelector(".o_navbar");
        const navH = nav ? Math.ceil(nav.getBoundingClientRect().height) : 46;
        document.body.style.setProperty("--maint-rul-nav-offset", `${navH}px`);
        this._actionRoot = formEl.closest(".o_action") || null;
        if (this._actionRoot) {
            this._actionRoot.classList.add("o_pm_rca_action");
        }
    }

    _subscribeBus() {
        const companyId =
            this.model.root.data.company_id && this.model.root.data.company_id[0];
        if (!companyId) {
            return;
        }
        this._busChannel = `maintenance_rul_tobm_${companyId}`;
        this.busService.addChannel(this._busChannel);
        this.busService.subscribe("maintenance/rul_tobm_refresh", this._onBusRefresh);
        this.busService.start();
    }

    _unsubscribeBus() {
        if (!this._busChannel) {
            return;
        }
        this.busService.unsubscribe("maintenance/rul_tobm_refresh", this._onBusRefresh);
        this.busService.deleteChannel(this._busChannel);
        this._busChannel = null;
    }

    _scheduleFilterApply() {
        if (this._filterDebounce) {
            clearTimeout(this._filterDebounce);
        }
        this._filterDebounce = setTimeout(() => this._reloadDashboard(true), 600);
    }

    async _reloadDashboard(showToast) {
        const record = this.model.root;
        if (!record?.resId || this._reloadInFlight) {
            return;
        }
        this._reloadInFlight = true;
        try {
            if (record.dirty) {
                await record.save();
            }
            await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "action_refresh_rul_tobm_data",
                [[record.resId]]
            );
            await record.load();
            if (showToast) {
                this.notification.add("RUL & TOBM report updated.", { type: "success" });
            }
        } catch (err) {
            const message =
                err?.data?.message ||
                err?.message ||
                "Could not update the report. Check filter values and try again.";
            const lowered = String(message).toLowerCase();
            if (
                !lowered.includes("couldn't be established or was interrupted") &&
                !lowered.includes("connection to")
            ) {
                this.notification.add(message, { type: "danger" });
            }
        } finally {
            this._reloadInFlight = false;
        }
    }
}

export const maintenanceRulTobmFormView = {
    ...formView,
    Controller: MaintenanceRulTobmFormController,
};

registry.category("views").add("maintenance_rul_tobm_dashboard", maintenanceRulTobmFormView);
