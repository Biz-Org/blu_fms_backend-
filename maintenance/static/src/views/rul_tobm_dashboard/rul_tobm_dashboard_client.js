/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { loadBundle } from "@web/core/assets";
import { ensureRulTobmInlineStyles } from "./rul_tobm_inline_styles";
import { buildRulTobmChartConfig } from "./rul_tobm_chart";

export class MaintenanceRulTobmDashboardClient extends Component {
    static template = "maintenance.RulTobmDashboardClient";
    static props = {
        embedded: { type: Boolean, optional: true },
        resId: { type: Number, optional: true },
        dashboardKey: { type: String, optional: true },
        record: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.menu = useService("menu");
        this.notification = useService("notification");
        this.canvasRef = useRef("chartCanvas");
        this.chart = null;
        this.state = useState({
            loading: true,
            data: null,
            error: null,
            openDropdown: null,
            revision: 0,
        });
        this._onDocClick = (ev) => {
            if (!ev.target.closest(".o_maint_rul_filter_drop")) {
                this.state.openDropdown = null;
            }
        };
        this._actionRoot = null;

        onWillStart(async () => {
            ensureRulTobmInlineStyles();
            await loadBundle("web.chartjs_lib");
            if (!this.props.embedded) {
                await this.loadDashboard(this._resolveResId());
                this._ensureMaintenanceMenuBar();
            }
        });

        useEffect(
            () => {
                if (!this.props.embedded) {
                    return;
                }
                const resId = this._resolveResId();
                if (resId) {
                    this.loadDashboard(resId);
                }
            },
            () => [this.props.embedded, this.props.dashboardKey, this.props.resId]
        );

        onMounted(() => {
            ensureRulTobmInlineStyles();
            if (!this.props.embedded) {
                this._ensureMaintenanceMenuBar();
            }
            this._prepareRulClientShell();
            document.addEventListener("click", this._onDocClick, true);
            this._renderChart();
        });

        onPatched(() => {
            ensureRulTobmInlineStyles();
            this._renderChart();
        });

        onWillUnmount(() => {
            this._destroyChart();
            window.removeEventListener("resize", this._onWindowResize);
            document.removeEventListener("click", this._onDocClick, true);
            [
                "maintenance_rul_tobm_inline_v1086",
                "maintenance_rul_tobm_inline_v1087",
                "maintenance_rul_tobm_inline_v1088",
                "maintenance_rul_tobm_inline_v1089",
                "maintenance_rul_tobm_inline_v1090",
                "maintenance_rul_tobm_inline_v1091",
                "maintenance_rul_tobm_inline_v1092",
                "maintenance_rul_tobm_inline_v1093",
                "maintenance_rul_tobm_inline_v1094",
                "maintenance_rul_tobm_inline_v1095",
                "maintenance_rul_tobm_inline_v1096",
                "maintenance_rul_tobm_inline_v1097",
                "maintenance_rul_tobm_inline_v1098",
            ].forEach((id) => document.getElementById(id)?.remove());
            document.getElementById("maintenance_rul_tobm_inline_v1099")?.remove();
            document.getElementById("maintenance_rul_tobm_inline_v1100")?.remove();
            document.getElementById("maintenance_rul_tobm_inline_v1101")?.remove();
            document.getElementById("maintenance_rul_tobm_inline_v1102")?.remove();
            if (!this.props.embedded) {
                document.body.classList.remove("o_pm_rca_fullscreen_body");
            }
            if (this._actionRoot) {
                this._actionRoot.classList.remove("o_maint_rul_action");
                this._actionRoot.classList.remove("o_pm_rca_action");
                this._actionRoot = null;
            }
            window.removeEventListener("resize", this._onWindowResize);
        });
    }

    _resolveResId() {
        if (this.props.resId) {
            return this.props.resId;
        }
        const fromAction = this.props.action?.params?.res_id;
        if (fromAction) {
            return fromAction;
        }
        const ctx = this.props.action?.context || {};
        return ctx.active_id || ctx.res_id || null;
    }

    _destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    /**
     * Activate the purple Odoo section bar:
     * Maintenance | Dashboard | Operations | Planning | Analysis | Reporting | …
     */
    _ensureMaintenanceMenuBar() {
        const current = this.menu.getCurrentApp();
        if (current?.xmlid === "maintenance.menu_maintenance_title") {
            return;
        }
        const apps = this.menu.getApps();
        const maintApp =
            apps.find((m) => m.xmlid === "maintenance.menu_maintenance_title") ||
            apps.find((m) => (m.name || "").trim() === "Maintenance");
        if (maintApp) {
            this.menu.setCurrentMenu(maintApp);
            browser.sessionStorage.setItem("menu_id", String(maintApp.id));
        }
    }

    _renderChart() {
        const canvas = this.canvasRef.el;
        const chartData = this.state.data?.chart;
        if (!canvas || !chartData?.points?.length) {
            this._destroyChart();
            return;
        }
        this._destroyChart();
        const config = buildRulTobmChartConfig(chartData);
        this.chart = new Chart(canvas, config);
    }

    _prepareRulClientShell() {
        const nav =
            document.querySelector(".o_main_navbar") ||
            document.querySelector(".o_navbar");
        const navH = nav ? Math.ceil(nav.getBoundingClientRect().height) : 46;
        document.body.style.setProperty("--maint-rul-nav-offset", `${navH}px`);

        if (this.props.embedded) {
            this._onWindowResize = () => {
                const navbar =
                    document.querySelector(".o_main_navbar") ||
                    document.querySelector(".o_navbar");
                const h = navbar ? Math.ceil(navbar.getBoundingClientRect().height) : 46;
                document.body.style.setProperty("--maint-rul-nav-offset", `${h}px`);
                this.chart?.resize();
            };
            window.addEventListener("resize", this._onWindowResize);
            return;
        }

        document.body.classList.add("o_pm_rca_fullscreen_body");
        const clientEl =
            document.querySelector(".o_maint_rul_client:not(.o_maint_rul_embedded)") ||
            document.querySelector(".o_maint_rul_dashboard_host");
        this._actionRoot = clientEl?.closest(".o_action") || null;
        if (this._actionRoot) {
            this._actionRoot.classList.add("o_pm_rca_action");
            this._actionRoot.classList.add("o_maint_rul_action");
        }
        this._onWindowResize = () => {
            const navbar =
                document.querySelector(".o_main_navbar") ||
                document.querySelector(".o_navbar");
            const h = navbar ? Math.ceil(navbar.getBoundingClientRect().height) : 46;
            document.body.style.setProperty("--maint-rul-nav-offset", `${h}px`);
            this.chart?.resize();
        };
        window.addEventListener("resize", this._onWindowResize);
    }

    async loadDashboard(resId = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const args = resId ? [resId] : [];
            const data = await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "get_dashboard_payload",
                args
            );
            if (!data || !data.kpis) {
                this.state.data = null;
                this.state.error = _t("Could not load report data. Restart Odoo and try again.");
                return;
            }
            if (!data.phases) {
                data.phases = {
                    rul_width: 75,
                    tobm_width: 10,
                    maint_width: 15,
                    rul_label: "RUL (75%)",
                    tobm_label: "TOBM Window (10%)",
                    maint_label: "Maintenance (15%)",
                    failure_rul_label: "Failure Threshold (25%)",
                };
            }
            this._setDashboardData(data);
        } catch (err) {
            this.state.data = null;
            this.state.error =
                err?.data?.message || err?.message || _t("Could not load the RUL & TOBM report.");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    _setDashboardData(data) {
        this.state.data = {
            ...data,
            kpis: { ...data.kpis },
            filters: { ...data.filters },
            detail: data.detail ? { ...data.detail } : data.detail,
        };
        this.state.revision = (this.state.revision || 0) + 1;
        this.state.openDropdown = null;
        ensureRulTobmInlineStyles();
        this._renderChart();
    }

    toggleDropdown(name, ev) {
        ev?.stopPropagation();
        this.state.openDropdown = this.state.openDropdown === name ? null : name;
    }

    async applyFilters(filterPatch) {
        const recordId = this.state.data?.record_id;
        if (!recordId) {
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "apply_dashboard_filters",
                [[recordId], filterPatch]
            );
            this._setDashboardData(data);
            if (this.props.embedded && this.props.record?.load) {
                await this.props.record.load();
            }
        } catch (err) {
            const message =
                err?.data?.message || err?.message || _t("Could not update filters.");
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onSelectCategory(categoryId, ev) {
        ev?.stopPropagation();
        this.applyFilters({ category_id: categoryId || false });
    }

    onSelectPeriod(days, ev) {
        ev?.stopPropagation();
        this.applyFilters({ analysis_period_days: days });
    }

    onSelectEquipment(equipmentId, ev) {
        ev?.stopPropagation();
        this.applyFilters({ equipment_id: equipmentId });
    }

    async onOpenMaintenanceTeams(ev) {
        ev?.stopPropagation();
        try {
            const action = await this.orm.call(
                "maintenance.rul.tobm.dashboard",
                "action_open_maintenance_teams",
                []
            );
            if (action) {
                this.action.doAction(action);
            }
        } catch (err) {
            const message =
                err?.data?.message || err?.message || _t("Could not open Maintenance Teams.");
            this.notification.add(message, { type: "danger" });
        }
    }
}

registry.category("actions").add("maintenance_rul_tobm_dashboard", MaintenanceRulTobmDashboardClient);
