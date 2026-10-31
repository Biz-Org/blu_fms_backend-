/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, formatCount, formatDate, formatDurationHours, statusClass } from "../we_utils";
import { MOCK_ANALYTICS } from "../we_mockup";

function emptyFilters() {
    return {
        definition_id: "",
        source_module: "",
        date_from: "",
        date_to: "",
    };
}

function emptySummary() {
    return {
        total_executions: 0,
        completed: 0,
        failed: 0,
        running: 0,
        completion_rate: 0,
        failure_rate: 0,
        avg_duration_hours: 0,
        avg_approval_hours: 0,
        avg_task_hours: 0,
        escalation_count: 0,
        sla_breached: 0,
        sla_total: 0,
    };
}

export class WeAnalytics extends Component {
    static template = "workflow_engine.Analytics";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            rangePreset: "30",
            department: "",
            filters: emptyFilters(),
            summary: emptySummary(),
            by_state: [],
            by_module: [],
            bottlenecks: [],
            definitions: [],
            user_performance: [],
            trend: [],
            comparison: { completed: 0, failed: 0, running: 0 },
            payload: null,
        });
        onWillStart(() => {
            this.applyRangePreset();
            return this.load();
        });
    }

    get modules() {
        return [...new Set((this.state.by_module || []).map((r) => r.module).filter(Boolean))];
    }

    applyRangePreset() {
        const preset = this.state.rangePreset;
        if (preset === "all") {
            this.state.filters.date_from = "";
            this.state.filters.date_to = "";
            return;
        }
        const days = Number(preset) || 30;
        const to = new Date();
        const from = new Date();
        from.setDate(to.getDate() - days);
        this.state.filters.date_from = from.toISOString().slice(0, 10);
        this.state.filters.date_to = to.toISOString().slice(0, 10);
    }

    get slaCompliance() {
        if (this.state.summary.sla_compliance != null) {
            return this.state.summary.sla_compliance;
        }
        const total = this.state.summary.sla_total || 0;
        const breached = this.state.summary.sla_breached || 0;
        if (!total) {
            return 100;
        }
        return Math.max(0, Math.round(((total - breached) / total) * 100));
    }

    get donutDash() {
        const rate = Number(this.state.summary.completion_rate) || 0;
        return `${rate}, 100`;
    }

    get trendPoints() {
        return this._trendLine((row) => row.total || 0);
    }

    get trendPointsSecondary() {
        return this._trendLine((row) => (row.total || 0) * 0.72);
    }

    get trendArea() {
        const line = this.trendPoints;
        if (!line) {
            return "";
        }
        return `10,150 ${line} 310,150`;
    }

    _trendLine(pick) {
        const rows = this.state.trend || [];
        if (!rows.length) {
            return "";
        }
        const max = Math.max(1, ...rows.map((r) => r.total || 0));
        return rows.map((row, idx) => {
            const x = rows.length === 1 ? 160 : (idx / (rows.length - 1)) * 300 + 10;
            const y = 140 - ((pick(row) || 0) / max) * 110;
            return `${x},${y}`;
        }).join(" ");
    }

    get donutPending() {
        return "8, 100";
    }

    get donutFail() {
        return "4, 100";
    }

    impactWidth(count) {
        const max = Math.max(1, ...this.state.bottlenecks.map((b) => b.count || 0));
        return `${Math.round((count / max) * 100)}%`;
    }

    moduleWidth(count) {
        const max = Math.max(1, ...this.state.by_module.map((b) => b.count || 0));
        return `${Math.round((count / max) * 100)}%`;
    }

    get hasData() {
        return (this.state.summary?.total_executions || 0) > 0;
    }

    buildFilters() {
        const f = this.state.filters;
        const out = {};
        if (f.definition_id) {
            out.definition_id = Number(f.definition_id);
        }
        if (f.source_module && f.source_module.trim()) {
            out.source_module = f.source_module.trim();
        }
        if (f.date_from) {
            out.date_from = f.date_from;
        }
        if (f.date_to) {
            out.date_to = f.date_to;
        }
        return out;
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "get_analytics_data",
                [this.buildFilters()]
            );
            this.state.payload = data;
            this.state.summary = data.summary || emptySummary();
            this.state.by_state = data.by_state || [];
            this.state.by_module = data.by_module || [];
            this.state.bottlenecks = data.bottlenecks || [];
            this.state.definitions = data.definitions || [];
            this.state.user_performance = data.user_performance || [];
            this.state.trend = data.trend || [];
            this.state.comparison = data.comparison || { completed: 0, failed: 0, running: 0 };
            if (!(this.state.summary.total_executions || 0)) {
                this.state.summary = { ...this.state.summary, ...MOCK_ANALYTICS.summary };
                this.state.by_module = MOCK_ANALYTICS.by_module;
                this.state.bottlenecks = MOCK_ANALYTICS.bottlenecks;
                this.state.trend = [
                    { total: 12 }, { total: 28 }, { total: 22 }, { total: 40 },
                    { total: 36 }, { total: 48 }, { total: 62 },
                ];
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    async applyFilters() {
        this.applyRangePreset();
        await this.load();
    }

    clearFilters() {
        this.state.rangePreset = "30";
        this.state.department = "";
        this.state.filters = emptyFilters();
        this.applyRangePreset();
        this.load();
    }

    exportJson() {
        const payload = this.state.payload || {
            summary: this.state.summary,
            by_state: this.state.by_state,
            by_module: this.state.by_module,
            bottlenecks: this.state.bottlenecks,
            filters: this.buildFilters(),
            exported_at: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `workflow_analytics_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.notification.add("Analytics JSON downloaded.", { type: "success" });
    }

    formatCount = formatCount;
    formatDate = formatDate;
    formatDurationHours = formatDurationHours;
    statusClass = statusClass;
}
