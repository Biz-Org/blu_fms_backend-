import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class KpiDashboard extends RaScreen {
    static template = "reports_analytics.Kpis";

    setup() {
        super.setup();
        this.ui = useState({ data: { kpis: [], chart: { labels: [], series: [] } } });
    }

    async load() {
        this.ui.data = await this.orm.call("analytics.kpi", "get_dashboard_payload", [this.state.filters]);
    }

    async createDashboard() {
        await this.orm.call("analytics.dashboard", "action_create_from_ui", [{
            name: "KPI Dashboard",
            dashboard_type: "operational",
            kpi_ids: (this.ui.data.kpis || []).map((row) => row.id),
        }]);
        this.notification.add("Dashboard definition saved.", { type: "success" });
    }
}

registry.category("actions").add("reports_analytics.action_kpis", KpiDashboard);
