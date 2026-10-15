import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class ReportBuilder extends RaScreen {
    static template = "reports_analytics.Builder";

    setup() {
        super.setup();
        this.ui = useState({
            reportId: this.props.action?.context?.report_id || false,
            name: "",
            report_type: "tabular",
            description: "",
            visualization: "table",
            data_source_id: false,
            fields: [],
            selected: [],
            metrics: [],
            selectedMetrics: [],
            grouping: [],
            filters: { date_range: "last_30", property_id: "", category: "", status: "" },
            preview: null,
            busy: "",
        });
    }

    async load() {
        if (!this.ui.data_source_id && this.state.bootstrap.sources.length) {
            const first = this.state.bootstrap.sources.find((row) => row.available) || this.state.bootstrap.sources[0];
            this.ui.data_source_id = first.id;
        }
        if (this.ui.reportId) {
            const detail = await this.orm.call("analytics.report", "ui_detail", [this.ui.reportId]);
            this.ui.name = detail.name;
            this.ui.report_type = detail.report_type;
            this.ui.visualization = detail.visualization;
            this.ui.data_source_id = detail.data_source_id;
            this.ui.selected = detail.config.fields || [];
            this.ui.selectedMetrics = (detail.config.metrics || []).map((row) => row.name);
            this.ui.grouping = detail.config.grouping || [];
            this.ui.filters = Object.assign(this.ui.filters, detail.config.filters || {});
        }
        await this.loadSchema();
    }

    async loadSchema() {
        if (!this.ui.data_source_id) {
            return;
        }
        const schema = await this.orm.call("analytics.query.engine", "get_source_schema", [this.ui.data_source_id]);
        this.ui.fields = schema.fields || [];
        this.ui.metrics = schema.metrics || [];
        if (!schema.available) {
            this.ui.preview = { available: false, reason: schema.reason, rows: [], columns: [], kpis: [] };
        }
    }

    async onSourceChange(ev) {
        this.ui.data_source_id = parseInt(ev.target.value, 10);
        this.ui.selected = [];
        this.ui.selectedMetrics = [];
        await this.loadSchema();
        await this.preview();
    }

    toggleField(name) {
        const selected = new Set(this.ui.selected);
        if (selected.has(name)) {
            selected.delete(name);
        } else {
            selected.add(name);
        }
        this.ui.selected = [...selected];
    }

    toggleMetric(name) {
        const selected = new Set(this.ui.selectedMetrics);
        if (selected.has(name)) {
            selected.delete(name);
        } else {
            selected.add(name);
        }
        this.ui.selectedMetrics = [...selected];
    }

    selectAll() {
        this.ui.selected = this.ui.fields.map((field) => field.name).slice(0, 12);
    }

    clearAll() {
        this.ui.selectedMetrics = [];
    }

    setViz(value) {
        this.ui.visualization = value;
    }

    get previewRows() {
        return (this.ui.preview?.rows || []).slice(0, 5);
    }

    builderPayload() {
        return {
            name: this.ui.name,
            report_type: this.ui.report_type,
            description: this.ui.description,
            visualization: this.ui.visualization,
            data_source_id: this.ui.data_source_id,
            config: {
                data_source_id: this.ui.data_source_id,
                visualization: this.ui.visualization,
                report_type: this.ui.report_type,
                fields: this.ui.selected,
                grouping: this.ui.grouping,
                metrics: this.ui.metrics.filter((metric) => this.ui.selectedMetrics.includes(metric.name)),
                filters: this.ui.filters,
            },
        };
    }

    async preview() {
        this.ui.preview = await this.orm.call("analytics.report", "action_preview_config", [this.builderPayload().config]);
    }

    async saveDraft() {
        this.ui.busy = "draft";
        const detail = await this.orm.call("analytics.report", "action_save_draft", [this.builderPayload(), this.ui.reportId || false]);
        this.ui.reportId = detail.id;
        this.ui.busy = "";
        this.notification.add("Draft saved.", { type: "success" });
    }

    async generate() {
        this.ui.busy = "generate";
        const result = await this.orm.call("analytics.report", "action_generate", [this.builderPayload(), this.ui.reportId || false]);
        this.ui.reportId = result.report.id;
        this.ui.preview = result.execution.result;
        this.ui.busy = "";
        this.action.doAction("reports_analytics.action_ra_preview", {
            additionalContext: { report_id: result.report.id, execution_id: result.execution.id },
        });
    }

    cancel() {
        this.action.doAction("reports_analytics.action_ra_reports", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("reports_analytics.action_builder", ReportBuilder);
