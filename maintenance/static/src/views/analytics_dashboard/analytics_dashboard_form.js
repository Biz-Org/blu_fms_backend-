/** @odoo-module **/



import { formView } from "@web/views/form/form_view";

import { registry } from "@web/core/registry";

import { useService } from "@web/core/utils/hooks";

import { onMounted, onWillUnmount, useEffect } from "@odoo/owl";



const FILTER_FIELDS = [

    "analytics_mode",

    "analysis_period_days",

    "fleet_vehicle_scope",

    "use_case_request_id",

];



export class MaintenanceAnalyticsFormController extends formView.Controller {

    setup() {

        super.setup();

        this.orm = useService("orm");

        this.busService = useService("bus_service");

        this.notification = useService("notification");

        this._busChannel = null;

        this._filterDebounce = null;

        this._lastFilterSnapshot = undefined;

        this._onBusRefresh = (payload) => {

            const companyId =

                this.model.root.data.company_id && this.model.root.data.company_id[0];

            if (companyId && payload.company_id === companyId) {

                this._reloadDashboard(false);

            }

        };



        onMounted(() => {

            this._subscribeBus();

            this._onWindowFocus = () => this._reloadDashboard(false);

            window.addEventListener("focus", this._onWindowFocus);

        });

        onWillUnmount(() => {

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



    _subscribeBus() {

        const companyId =

            this.model.root.data.company_id && this.model.root.data.company_id[0];

        if (!companyId) {

            return;

        }

        this._busChannel = `maintenance_analytics_${companyId}`;

        this.busService.addChannel(this._busChannel);

        this.busService.subscribe("maintenance/analytics_refresh", this._onBusRefresh);

        this.busService.start();

    }



    _unsubscribeBus() {

        if (!this._busChannel) {

            return;

        }

        this.busService.unsubscribe("maintenance/analytics_refresh", this._onBusRefresh);

        this.busService.deleteChannel(this._busChannel);

        this._busChannel = null;

    }



    _scheduleFilterApply() {

        if (this._filterDebounce) {

            clearTimeout(this._filterDebounce);

        }

        this._filterDebounce = setTimeout(() => this._reloadDashboard(true), 700);

    }



    async _reloadDashboard(showToast) {

        const record = this.model.root;

        if (!record?.resId) {

            return;

        }

        try {

            if (record.dirty) {

                await record.save();

            }

            await this.orm.call(

                "maintenance.analytics.dashboard",

                "action_refresh_analytics",

                [[record.resId]]

            );

            await record.load();

            if (showToast) {

                this.notification.add("Dashboard updated.", { type: "success" });

            }

        } catch {

            // Validation on filter fields — user can correct and retry.

        }

    }



    async afterExecuteActionButton(clickParams) {

        if (clickParams.name === "action_refresh_analytics") {

            await this.model.root.load();

            this.notification.add("Dashboard updated.", { type: "success" });

        }

    }

}



export const maintenanceAnalyticsFormView = {

    ...formView,

    Controller: MaintenanceAnalyticsFormController,

};



registry.category("views").add("maintenance_analytics_dashboard", maintenanceAnalyticsFormView);

