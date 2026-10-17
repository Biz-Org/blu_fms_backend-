/** @odoo-module **/

import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

const RCA_METHOD_ACTIONS = {
    fishbone: "action_open_rca_fishbone",
    why_why: "action_open_rca_why_why",
    dependency: "action_open_rca_dependency_mapping",
    failure_tree: "action_open_rca_failure_tree",
};

const RCA_REPLACE_NAV_BUTTONS = new Set([
    "action_open_plant_rca_dashboard",
    "action_open_agile_rca_dashboard",
    "action_open_why_rca_dashboard",
    "action_open_capa_rca_dashboard",
    "action_open_rca_mom_form",
    "action_open_rca_fishbone",
    "action_open_rca_why_why",
    "action_open_rca_dependency_mapping",
    "action_open_rca_failure_tree",
    "action_open_rca_mom_full",
    "action_open_rca_excel_import",
    "action_download_rca_excel_template",
]);

const RCA_ACTION_OPTIONS = {
    clearBreadcrumbs: true,
    stackPosition: "replaceCurrentAction",
};

const RCA_FORM_CLASS_MARKERS = [
    "o_pm_rca_fullscreen_form",
    "o_pm_plant_rca_form",
    "o_pm_agile_rca_form",
    "o_pm_why_rca_form",
    "o_pm_capa_rca_form",
];

function _isRcaDashboardFormEl(el) {
    return el && RCA_FORM_CLASS_MARKERS.some((cls) => el.classList.contains(cls));
}

export class MaintenanceRcaAiDashboardFormController extends formView.Controller {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this._actionRoot = null;
        this._navClickHandler = this._onRcaNavClick.bind(this);
        this._issueClickHandler = this._onDashboardIssueClick.bind(this);

        onMounted(() => this._onFormMounted());
        onPatched(() => {
            this._resetDashboardBindings();
            this._bindRcaMethodTabs();
            this._bindRcaHeaderNav();
            this._bindDashboardIssueList();
        });
        onWillUnmount(() => {
            if (this._actionRoot) {
                this._actionRoot.classList.remove("o_pm_rca_action");
                this._actionRoot = null;
            }
            document.body.classList.remove("o_pm_rca_fullscreen_body");
            const formEl = this._getFormEl();
            formEl?.removeEventListener("click", this._navClickHandler, true);
            formEl?.removeEventListener("click", this._issueClickHandler);
        });
    }

    /** Odoo 18 form root may omit .o_form_view — match arch classes from this.el. */
    _getFormEl() {
        if (_isRcaDashboardFormEl(this.el)) {
            return this.el;
        }
        for (const cls of RCA_FORM_CLASS_MARKERS) {
            const found = document.querySelector(`.${cls}`);
            if (found) {
                return found;
            }
        }
        return null;
    }

    _prepareRcaFormShell(formEl) {
        if (!formEl) {
            return;
        }
        formEl.classList.add("o_form_view");
        document.body.classList.add("o_pm_rca_fullscreen_body");
    }

    _resetDashboardBindings() {
        const formEl = this._getFormEl();
        if (!formEl) {
            return;
        }
        delete formEl.dataset.pmIssueBound;
        delete formEl.dataset.pmNavCapture;
        formEl.querySelectorAll(".o_pm_ai_rca_method_tab").forEach((tab) => {
            delete tab.dataset.rcaNavBound;
        });
        const dash = formEl.querySelector(".o_pm_ai_rca_dash");
        if (dash) {
            delete dash.dataset.rcaTabsBound;
        }
    }

    _onFormMounted() {
        const formEl = this._getFormEl();
        this._prepareRcaFormShell(formEl);
        this._actionRoot = formEl?.closest(".o_action") || null;
        if (this._actionRoot) {
            this._actionRoot.classList.add("o_pm_rca_action");
        }
        this._normalizeStackedUrl();
        this._resetDashboardBindings();
        this._bindRcaMethodTabs();
        this._bindRcaHeaderNav();
        this._bindDashboardIssueList();
    }

    /** Fix broken layout from stacked rca-mom / ai-plant-rca URLs in the address bar. */
    _normalizeStackedUrl() {
        const resId = this.model.root.resId;
        if (!resId) {
            return;
        }
        const path = window.location.pathname || "";
        const plantHits = (path.match(/ai-plant-rca/g) || []).length;
        const agileHits = (path.match(/ai-agile-rca/g) || []).length;
        const whyHits = (path.match(/ai-why-rca/g) || []).length;
        const capaHits = (path.match(/ai-capa-rca/g) || []).length;
        const momHits = (path.match(/rca-mom/g) || []).length;
        const stacked = plantHits + agileHits + whyHits + capaHits + momHits;
        if (stacked > 1 || path.split("maintenance.request").length > 2) {
            const db = new URLSearchParams(window.location.search).get("db");
            const q = db ? `?db=${db}` : "";
            const formEl = this._getFormEl();
            let base = "ai-plant-rca";
            if (formEl?.classList.contains("o_pm_agile_rca_form")) {
                base = "ai-agile-rca";
            } else if (formEl?.classList.contains("o_pm_why_rca_form")) {
                base = "ai-why-rca";
            } else if (formEl?.classList.contains("o_pm_capa_rca_form")) {
                base = "ai-capa-rca";
            } else if (
                formEl?.classList.contains("o_pm_rca_fullscreen_form") &&
                !formEl.classList.contains("o_pm_plant_rca_form")
            ) {
                base = "rca-mom";
            }
            window.location.replace(`${window.location.origin}/odoo/${base}/${resId}${q}`);
        }
    }

    _bindRcaHeaderNav() {
        const formEl = this._getFormEl();
        if (!formEl || formEl.dataset.pmNavCapture === "1") {
            return;
        }
        formEl.dataset.pmNavCapture = "1";
        formEl.addEventListener("click", this._navClickHandler, true);
    }

    async _onRcaNavClick(ev) {
        const btn = ev.target.closest("button[name]");
        if (!btn || !RCA_REPLACE_NAV_BUTTONS.has(btn.getAttribute("name"))) {
            return;
        }
        const resId = this.model.root.resId;
        if (!resId) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();

        const method = btn.getAttribute("name");
        const action = await this.orm.call("maintenance.request", method, [[resId]]);
        if (action) {
            await this.actionService.doAction(action, RCA_ACTION_OPTIONS);
        }
    }

    _resolveIssueNavigationMethod(formEl) {
        if (formEl.classList.contains("o_pm_plant_rca_form")) {
            return "action_open_plant_rca_dashboard";
        }
        if (formEl.classList.contains("o_pm_why_rca_form")) {
            return "action_open_why_rca_dashboard";
        }
        if (formEl.classList.contains("o_pm_capa_rca_form")) {
            return "action_open_capa_rca_dashboard";
        }
        if (formEl.classList.contains("o_pm_agile_rca_form")) {
            return "action_open_agile_rca_dashboard";
        }
        return "action_open_rca_fishbone";
    }

    _bindDashboardIssueList() {
        const formEl = this._getFormEl();
        if (!formEl || !_isRcaDashboardFormEl(formEl)) {
            return;
        }
        if (formEl.dataset.pmIssueBound === "1") {
            return;
        }
        formEl.dataset.pmIssueBound = "1";
        formEl.addEventListener("click", this._issueClickHandler);
    }

    async _onDashboardIssueClick(ev) {
        const row = ev.target.closest(
            ".o_pm_fb_issue_row[data-request-id], .o_pm_ai_rca_issue[data-request-id], .o_pm_plant_issue[data-request-id], .o_pm_why_issue_row[data-request-id], .o_pm_capa_issue_row[data-request-id]"
        );
        if (!row || row.classList.contains("is-active")) {
            return;
        }
        const resId = parseInt(row.dataset.requestId, 10);
        const currentId = this.model.root.resId;
        if (!resId || resId === currentId) {
            return;
        }
        ev.preventDefault();
        const formEl = this._getFormEl();
        const method = this._resolveIssueNavigationMethod(formEl);
        const action = await this.orm.call("maintenance.request", method, [[resId]]);
        if (action) {
            await this.actionService.doAction(action, RCA_ACTION_OPTIONS);
        }
    }

    _bindRcaMethodTabs() {
        const formEl = this._getFormEl();
        if (!formEl) {
            return;
        }
        const resId = this.model.root.resId;
        if (!resId) {
            return;
        }
        formEl.querySelectorAll(".o_pm_ai_rca_method_tab").forEach((tab) => {
            if (tab.dataset.rcaNavBound === "1") {
                return;
            }
            tab.dataset.rcaNavBound = "1";
            tab.style.cursor = "pointer";
            const navigate = async () => {
                const method = tab.dataset.rcaMethod;
                if (!method || tab.classList.contains("is-active")) {
                    return;
                }
                const actionMethod = RCA_METHOD_ACTIONS[method];
                if (!actionMethod) {
                    return;
                }
                const action = await this.orm.call(
                    "maintenance.request",
                    actionMethod,
                    [[resId]]
                );
                if (action) {
                    await this.actionService.doAction(action, RCA_ACTION_OPTIONS);
                }
            };
            tab.addEventListener("click", navigate);
            tab.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate();
                }
            });
        });
    }

    async save(params) {
        const saved = await super.save(params);
        const formEl = this._getFormEl();
        if (saved && formEl && this.model.root.resId) {
            await this.orm.call("maintenance.request", "action_refresh_rca_dashboards", [
                [this.model.root.resId],
            ]);
            await this.model.root.load();
            this._resetDashboardBindings();
            this._bindRcaMethodTabs();
            this._bindRcaHeaderNav();
            this._bindDashboardIssueList();
        }
        return saved;
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_refresh_rca_dashboards" && this.model.root.resId) {
            await this.orm.call("maintenance.request", "action_refresh_rca_dashboards", [
                [this.model.root.resId],
            ]);
            await this.model.root.load();
            this._resetDashboardBindings();
            this._bindRcaMethodTabs();
            this._bindRcaHeaderNav();
            this._bindDashboardIssueList();
            return;
        }
        return super.beforeExecuteActionButton(clickParams);
    }
}

export const maintenanceRcaAiDashboardFormView = {
    ...formView,
    Controller: MaintenanceRcaAiDashboardFormController,
};

registry.category("views").add("maintenance_rca_ai_dashboard", maintenanceRcaAiDashboardFormView);
