/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { PLANT_SIDEBAR_SECTIONS, isMaintenanceApp } from "./plant_sidebar_data";

const HIDE_TOP = "o_pm_hide_top_sections";
const HAS_SIDEBAR = "o_pm_has_sidebar";
const COLLAPSED = "o_pm_sidebar_collapsed";
const SELECTED_REQUEST_KEY = "maintenance_selected_request_id";

/**
 * Persistent vertical sidebar for the whole Maintenance app.
 * Workflow menus keep the currently selected maintenance.request context.
 */
export class PlantMaintenanceGlobalSidebar extends Component {
    static template = "maintenance.PlantGlobalSidebar";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.menu = useService("menu");
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            visible: false,
            activeItem: "dash_home",
            sidebarCollapsed: false,
            selectedRequestId: this._readStoredRequestId(),
        });

        this._onAppChanged = () => this._syncVisibility();
        this._onActionUpdate = () => this._rememberRequestFromController();
        onMounted(() => {
            this.env.bus.addEventListener("MENUS:APP-CHANGED", this._onAppChanged);
            this.env.bus.addEventListener("ACTION_MANAGER:UPDATE", this._onActionUpdate);
            this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", this._onActionUpdate);
            this._syncVisibility();
            this._rememberRequestFromController();
        });
        onWillUnmount(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", this._onAppChanged);
            this.env.bus.removeEventListener("ACTION_MANAGER:UPDATE", this._onActionUpdate);
            this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", this._onActionUpdate);
            document.body.classList.remove(HIDE_TOP, HAS_SIDEBAR, COLLAPSED);
        });
    }

    get sections() {
        return PLANT_SIDEBAR_SECTIONS;
    }

    // The Odoo top bar is hidden in Maintenance, so its app switcher lives here.
    get apps() {
        return this.menu.getApps() || [];
    }

    openApp(app) {
        if (app) {
            this.menu.selectMenu(app);
        }
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }

    _readStoredRequestId() {
        try {
            const raw = sessionStorage.getItem(SELECTED_REQUEST_KEY);
            const id = raw ? Number(raw) : 0;
            return Number.isInteger(id) && id > 0 ? id : false;
        } catch {
            return false;
        }
    }

    _storeRequestId(requestId) {
        const id = Number(requestId);
        if (!Number.isInteger(id) || id <= 0) {
            return;
        }
        this.state.selectedRequestId = id;
        try {
            sessionStorage.setItem(SELECTED_REQUEST_KEY, String(id));
        } catch {
            // ignore storage errors
        }
    }

    _clearStoredRequestId() {
        this.state.selectedRequestId = false;
        try {
            sessionStorage.removeItem(SELECTED_REQUEST_KEY);
        } catch {
            // ignore
        }
    }

    _getControllerRequestId() {
        const ctrl = this.action.currentController;
        if (!ctrl) {
            return false;
        }
        const props = ctrl.props || {};
        const act = ctrl.action || {};
        const model = props.resModel || act.res_model;
        if (model !== "maintenance.request") {
            return false;
        }
        const resId = props.resId || act.res_id;
        if (!resId || resId === "new") {
            return false;
        }
        const id = Number(resId);
        return Number.isInteger(id) && id > 0 ? id : false;
    }

    _rememberRequestFromController() {
        const id = this._getControllerRequestId();
        if (id) {
            this._storeRequestId(id);
        }
    }

    _getSelectedRequestId() {
        return this._getControllerRequestId() || this.state.selectedRequestId || this._readStoredRequestId();
    }

    _syncVisibility() {
        const visible = isMaintenanceApp(this.menu.getCurrentApp());
        this.state.visible = visible;
        document.body.classList.toggle(HIDE_TOP, visible);
        document.body.classList.toggle(HAS_SIDEBAR, visible);
        document.body.classList.toggle(COLLAPSED, visible && this.state.sidebarCollapsed);
    }

    isChildActive(childId) {
        return this.state.activeItem === childId;
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
        document.body.classList.toggle(COLLAPSED, this.state.sidebarCollapsed);
    }

    async _resolveFormViewId(formViewRef) {
        if (!formViewRef || !formViewRef.includes(".")) {
            return false;
        }
        const [module, name] = formViewRef.split(".");
        try {
            const result = await this.orm.call("ir.model.data", "check_object_reference", [
                module,
                name,
            ]);
            // Odoo returns [model_name, res_id]
            if (Array.isArray(result) && result[1]) {
                return result[1];
            }
        } catch {
            // fall through
        }
        return false;
    }

    _extractFormViewId(action) {
        if (!action) {
            return false;
        }
        const views = action.views || [];
        const formEntry = views.find((v) => Array.isArray(v) && v[1] === "form" && v[0]);
        if (formEntry) {
            return formEntry[0];
        }
        // Only trust view_id when the action is already form-only
        if (action.view_mode === "form" && action.view_id) {
            return action.view_id;
        }
        return false;
    }

    async _openWorkflowForRequest(child, requestId) {
        // Seed lines / business rules via server method when possible.
        let action = null;
        try {
            action = await this.orm.call(
                "maintenance.request",
                child.workflowMethod,
                [[requestId]]
            );
        } catch {
            action = null;
        }

        const formViewRef =
            child.formViewRef ||
            (action && action.context && action.context.form_view_ref) ||
            false;
        let viewId = this._extractFormViewId(action);
        if (!viewId && formViewRef) {
            viewId = await this._resolveFormViewId(formViewRef);
        }
        if (!viewId && !formViewRef) {
            return false;
        }

        // Fresh act_window — ActionManager must not reuse the prior form/list.
        const forced = {
            // Stored action id keeps this screen in the URL so browser Back reopens it.
            id: (action && action.id) || undefined,
            type: "ir.actions.act_window",
            name: (action && action.name) || child.label,
            res_model: "maintenance.request",
            res_id: requestId,
            view_mode: "form",
            views: [[viewId || false, "form"]],
            view_id: viewId || false,
            target: "current",
            context: {
                ...((action && action.context) || {}),
                active_id: requestId,
                active_ids: [requestId],
                form_view_ref: formViewRef || undefined,
                pm_workflow_step: formViewRef || undefined,
                pm_nav_token: `${child.id}-${requestId}-${Date.now()}`,
            },
        };

        await this.action.doAction(forced, {
            clearBreadcrumbs: true,
            stackPosition: "replaceCurrentAction",
        });
        this._storeRequestId(requestId);
        return true;
    }

    async onNavigate(child) {
        this.state.activeItem = child.id;
        if (!child.xmlId) {
            return;
        }

        // Keep remembering the open request before leaving the screen.
        this._rememberRequestFromController();

        if (child.keepRequestContext && child.workflowMethod) {
            const requestId = this._getSelectedRequestId();
            if (requestId) {
                try {
                    const opened = await this._openWorkflowForRequest(child, requestId);
                    if (opened) {
                        this._ensureMaintenanceApp();
                        this._syncVisibility();
                        return;
                    }
                } catch (err) {
                    const message =
                        err?.data?.message ||
                        err?.message ||
                        _t("Could not open this step for the selected request.");
                    this.notification.add(message, { type: "danger" });
                    // Fall through to list if the record is missing/invalid.
                    this._clearStoredRequestId();
                }
            } else {
                this.notification.add(
                    _t("Open a maintenance request first, then use Planning, Manpower, Spares, Work Orders, or RCA from the sidebar."),
                    { type: "warning" }
                );
            }
        }

        await this.action.doAction(child.xmlId, {
            clearBreadcrumbs: true,
            stackPosition: "replaceCurrentAction",
        });
        this._ensureMaintenanceApp();
        this._syncVisibility();
        this._rememberRequestFromController();
    }

    _ensureMaintenanceApp() {
        const app = this.menu.getCurrentApp();
        if (!isMaintenanceApp(app)) {
            const maint = (this.menu.getApps() || []).find((a) => isMaintenanceApp(a));
            if (maint) {
                this.menu.setCurrentMenu(maint);
            }
        }
    }
}

registry.category("main_components").add(
    "PlantMaintenanceGlobalSidebar",
    { Component: PlantMaintenanceGlobalSidebar },
    { force: true }
);
