import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class AnalyticsDashboard extends RaScreen {
    static template = "reports_analytics.Dashboard";

    setup() {
        super.setup();
        this.ui = useState({ tab: this.props.action?.tag?.includes("management") ? "management" : "analytics", data: {}, management: {} });
    }

    async load() {
        this.ui.data = await this.orm.call("analytics.dashboard.service", "get_analytics_dashboard", [this.state.filters]);
        if (this.ui.tab === "management") {
            this.ui.management = await this.orm.call("analytics.dashboard.service", "get_management_dashboard", [this.state.filters]);
        }
    }

    async setTab(tab) {
        this.ui.tab = tab;
        await this.reload();
    }

    get kpis() {
        return this.ui.data.kpis || [];
    }

    get performance() {
        return this.ui.data.performance || { labels: [], series: [{ data: [] }] };
    }

    get modules() {
        return this.ui.data.modules || [];
    }

    get attention() {
        return this.ui.data.attention || [];
    }
}

registry.category("actions").add("reports_analytics.action_dashboard", AnalyticsDashboard);
registry.category("actions").add("reports_analytics.action_management", AnalyticsDashboard);
