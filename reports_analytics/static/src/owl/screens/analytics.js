import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

const TAB_MAP = {
    "reports_analytics.action_operational": "operational",
    "reports_analytics.action_financial": "financial",
    "reports_analytics.action_trends": "trends",
    "reports_analytics.action_cross_module": "cross",
    "reports_analytics.action_predictive": "predictive",
};

export class AnalyticsHub extends RaScreen {
    static template = "reports_analytics.AnalyticsHub";

    setup() {
        super.setup();
        this.ui = useState({
            tab: TAB_MAP[this.props.action?.tag] || "operational",
            operational: { kpis: [], maintenance: {}, vendors: {} },
            financial: { kpis: [], available: false },
            trends: { kpis: [], chart: {}, metrics: [] },
            cross: { sources: [], chart: {}, insight: false },
            predictive: { items: [], available: false, reason: "" },
            moduleA: false,
            moduleB: false,
            metric: "",
        });
    }

    get activeNav() {
        return this.ui.tab === "operational" ? "operational" : this.ui.tab;
    }

    async load() {
        if (this.ui.tab === "operational") {
            this.ui.operational = await this.orm.call("analytics.dashboard.service", "get_operational_analytics", [this.state.filters]);
        } else if (this.ui.tab === "financial") {
            this.ui.financial = await this.orm.call("analytics.dashboard.service", "get_financial_analytics", [this.state.filters]);
        } else if (this.ui.tab === "trends") {
            this.ui.trends = await this.orm.call("analytics.dashboard.service", "get_trend_analysis", [{
                ...this.state.filters,
                metric: this.ui.metric,
            }]);
        } else if (this.ui.tab === "cross") {
            this.ui.cross = await this.orm.call("analytics.dashboard.service", "get_cross_module", [{
                module_a: this.ui.moduleA,
                module_b: this.ui.moduleB,
                date_range: this.state.filters.date_range,
            }]);
        } else {
            this.ui.predictive = await this.orm.call("analytics.dashboard.service", "get_predictive_analytics", [this.state.filters]);
        }
    }

    setTab(tab) {
        const xmlid = {
            operational: "reports_analytics.action_ra_operational",
            financial: "reports_analytics.action_ra_financial",
            trends: "reports_analytics.action_ra_trends",
            cross: "reports_analytics.action_ra_cross_module",
            predictive: "reports_analytics.action_ra_predictive",
        }[tab];
        this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }

    async analyze() {
        await this.reload();
    }
}

registry.category("actions").add("reports_analytics.action_operational", AnalyticsHub);
registry.category("actions").add("reports_analytics.action_financial", AnalyticsHub);
registry.category("actions").add("reports_analytics.action_trends", AnalyticsHub);
registry.category("actions").add("reports_analytics.action_cross_module", AnalyticsHub);
registry.category("actions").add("reports_analytics.action_predictive", AnalyticsHub);
