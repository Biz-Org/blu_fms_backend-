import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class ReportPreview extends RaScreen {
    static template = "reports_analytics.Preview";

    setup() {
        super.setup();
        this.ui = useState({
            reportId: this.props.action?.context?.report_id || false,
            executionId: this.props.action?.context?.execution_id || false,
            detail: {},
            result: {},
        });
    }

    async load() {
        if (!this.ui.reportId) {
            return;
        }
        this.ui.detail = await this.orm.call("analytics.report", "ui_detail", [this.ui.reportId]);
        this.ui.result = this.ui.detail.last_result || {};
        if (this.ui.executionId) {
            const execution = await this.orm.call("analytics.report.execution", "ui_payload", [this.ui.executionId]);
            this.ui.result = execution.result || this.ui.result;
            this.ui.execution = execution;
        }
    }

    exportUrl(format) {
        const executionId = this.ui.executionId || this.ui.detail.last_execution_id;
        if (!executionId) {
            return "#";
        }
        return `/reports_analytics/execution/${executionId}/export?export_format=${format}`;
    }

    async generate() {
        const result = await this.orm.call("analytics.report", "action_generate", [{}, this.ui.reportId]);
        this.ui.executionId = result.execution.id;
        this.ui.result = result.execution.result;
        this.ui.detail = result.report;
    }
}

registry.category("actions").add("reports_analytics.action_preview", ReportPreview);
