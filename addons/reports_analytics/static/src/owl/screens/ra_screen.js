import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { RaAppShell } from "@reports_analytics/owl/ui/ra_shell";
import { RA_COMPONENTS } from "@reports_analytics/owl/ui/ra_ui";

export class RaScreen extends Component {
    static components = { RaAppShell, ...RA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            bootstrap: { sources: [], properties: [], buildings: [], users: [], groups: {} },
            showAnalysis: false,
            analysis: { analysis_type: "operational", module: "", metric: "", date_range: "last_30" },
            filters: { date_range: "last_30", property_id: "", building_id: "" },
        });
        onWillStart(async () => {
            try {
                this.state.bootstrap = await this.orm.call("analytics.dashboard.service", "get_bootstrap", []);
            } catch (error) {
                this.state.error = error?.data?.message || error?.message || "Could not load analytics.";
            }
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        try {
            await this.load();
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || "Could not load this screen.";
        } finally {
            this.state.loading = false;
        }
    }

    async load() {}

    openAnalysis() {
        this.state.showAnalysis = true;
    }

    closeAnalysis() {
        this.state.showAnalysis = false;
    }

    async runAnalysis() {
        const result = await this.orm.call("analytics.dashboard.service", "run_analysis", [this.state.analysis]);
        this.state.showAnalysis = false;
        this.action.doAction(result.tag, { clearBreadcrumbs: true });
    }

    openClient(xmlid, extra = {}) {
        this.action.doAction(xmlid, { clearBreadcrumbs: true, additionalContext: extra });
    }
}
