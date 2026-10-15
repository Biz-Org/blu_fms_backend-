import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class ReportsScreen extends RaScreen {
    static template = "reports_analytics.Reports";

    setup() {
        super.setup();
        this.ui = useState({
            search: "",
            module: "",
            report_type: "",
            status: "",
            rows: [],
            total: 0,
            page: 1,
        });
    }

    get activeNav() {
        return "reports";
    }

    get libraryMode() {
        return false;
    }

    async load() {
        const result = await this.orm.call("analytics.dashboard.service", "search_reports", [{
            search: this.ui.search,
            module: this.ui.module,
            report_type: this.ui.report_type,
            status: this.ui.status,
            library: this.libraryMode,
            offset: (this.ui.page - 1) * 20,
            limit: 20,
        }]);
        this.ui.rows = result.rows || [];
        this.ui.total = result.total || 0;
    }

    reset() {
        Object.assign(this.ui, { search: "", module: "", report_type: "", status: "", page: 1 });
        this.reload();
    }

    createReport() {
        this.action.doAction("reports_analytics.action_ra_builder", { clearBreadcrumbs: true });
    }

    openReport(row) {
        this.action.doAction("reports_analytics.action_ra_preview", {
            additionalContext: { report_id: row.id, execution_id: row.last_execution_id },
        });
    }

    editReport(row) {
        this.action.doAction("reports_analytics.action_ra_builder", {
            additionalContext: { report_id: row.id },
        });
    }
}

export class LibraryScreen extends ReportsScreen {
    static template = "reports_analytics.Library";
    get activeNav() {
        return "library";
    }
    get libraryMode() {
        return true;
    }
}

registry.category("actions").add("reports_analytics.action_reports", ReportsScreen);
registry.category("actions").add("reports_analytics.action_library", LibraryScreen);
