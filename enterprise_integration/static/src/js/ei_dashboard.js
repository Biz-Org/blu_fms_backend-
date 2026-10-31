/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class EiDashboard extends Component {
    static template = "enterprise_integration.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            kpis: {},
            health: {},
            sync: {},
            api: {},
            recentLogs: [],
            connectors: [],
            healthTotal: 1,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [
                activeIntegrations,
                connectedConnectors,
                failedOps,
                syncSuccess,
                syncPending,
                syncRunning,
                syncFailed,
                syncConflicts,
                healthy,
                degraded,
                down,
                disconnected,
                apiSuccess,
                apiFailed,
                webhookSuccess,
                webhookFailed,
                recentLogs,
                connectors,
            ] = await Promise.all([
                this.orm.searchCount("ei.integration", [["state", "=", "active"]]),
                this.orm.searchCount("ei.connector", [["state", "=", "connected"]]),
                this.orm.searchCount("ei.log", [["level", "in", ["failed", "timeout", "rejected"]]]),
                this.orm.searchCount("ei.sync.run", [["state", "=", "completed"]]),
                this.orm.searchCount("ei.sync.run", [["state", "=", "pending"]]),
                this.orm.searchCount("ei.sync.run", [["state", "=", "running"]]),
                this.orm.searchCount("ei.sync.run", [["state", "=", "failed"]]),
                this.orm.searchCount("ei.sync.run", [["records_conflict", ">", 0]]),
                this.orm.searchCount("ei.connector", [["health_state", "=", "healthy"]]),
                this.orm.searchCount("ei.connector", [["health_state", "=", "degraded"]]),
                this.orm.searchCount("ei.connector", [["health_state", "=", "down"]]),
                this.orm.searchCount("ei.connector", [["state", "in", ["disconnected", "disabled"]]]),
                this.orm.searchCount("ei.log", [["category", "=", "api"], ["level", "=", "success"]]),
                this.orm.searchCount("ei.log", [["category", "=", "api"], ["level", "in", ["failed", "rejected", "timeout"]]]),
                this.orm.searchCount("ei.log", [["category", "=", "webhook"], ["level", "=", "success"]]),
                this.orm.searchCount("ei.log", [["category", "=", "webhook"], ["level", "in", ["failed", "retrying"]]]),
                this.orm.searchRead(
                    "ei.log",
                    [],
                    ["name", "category", "level", "create_date", "correlation_id", "operation"],
                    { limit: 8, order: "create_date desc" }
                ),
                this.orm.searchRead(
                    "ei.connector",
                    [],
                    ["name", "category", "state", "health_state", "is_mock", "last_health_at"],
                    { limit: 6, order: "write_date desc" }
                ),
            ]);

            this.state.kpis = {
                activeIntegrations,
                connectedConnectors,
                failedOps,
                syncSuccess,
                syncPending,
            };
            this.state.health = { healthy, warning: degraded, error: down, disconnected };
            this.state.healthTotal = Math.max(1, healthy + degraded + down + disconnected);
            this.state.sync = {
                running: syncRunning,
                failed: syncFailed,
                pending: syncPending,
                conflicts: syncConflicts,
            };
            this.state.api = {
                requests: apiSuccess + apiFailed,
                success: apiSuccess,
                failed: apiFailed,
                webhookDeliveries: webhookSuccess,
                webhookFailed,
            };
            this.state.recentLogs = recentLogs;
            this.state.connectors = connectors;
        } catch (err) {
            this.state.error = (err && err.message) || "Failed to load dashboard data.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    formatCount(n) {
        const v = Number(n) || 0;
        if (v >= 1000) {
            return `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k`;
        }
        return String(v);
    }

    avatarLetter(c) {
        const map = { erp: "E", crm: "C", bank: "B", whatsapp: "W", legacy: "L" };
        return map[c.category] || (c.name || "?").charAt(0).toUpperCase();
    }

    categoryLabel(cat) {
        const map = {
            erp: "ERP",
            crm: "CRM",
            bank: "Banking",
            whatsapp: "Messaging",
            legacy: "Legacy",
        };
        return map[cat] || cat || "—";
    }

    healthClass(state) {
        if (state === "healthy") {
            return "";
        }
        if (state === "degraded") {
            return "warn";
        }
        return "bad";
    }

    healthWidth(state) {
        if (state === "healthy") {
            return "width: 92%";
        }
        if (state === "degraded") {
            return "width: 48%";
        }
        return "width: 14%";
    }

    meterWidth(count) {
        const pct = Math.min(100, Math.round((Number(count) || 0) / this.state.healthTotal * 100));
        return `width: ${Math.max(pct, count ? 8 : 0)}%`;
    }

    openApiWebhook() {
        this.action.doAction("enterprise_integration.action_ei_api_webhook");
    }

    openConnectors() {
        this.action.doAction("enterprise_integration.action_ei_connectors");
    }

    openSync() {
        this.action.doAction("enterprise_integration.action_ei_sync");
    }

    openMaster() {
        this.action.doAction("enterprise_integration.action_ei_master");
    }

    openMonitoring() {
        this.action.doAction("enterprise_integration.action_ei_monitoring");
    }

    async refresh() {
        await this.loadData();
    }
}

registry.category("actions").add("ei_dashboard", EiDashboard);
