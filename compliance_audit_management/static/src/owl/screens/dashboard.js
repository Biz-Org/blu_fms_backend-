import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { CaAppShell, CA_NAV } from "@compliance_audit_management/owl/ui/ca_shell";
import { CA_COMPONENTS } from "@compliance_audit_management/owl/ui/ca_ui";

export class ComplianceDashboard extends Component {
    static template = "compliance_audit_management.Dashboard";
    static components = { CaAppShell, ...CA_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            isManager: false,
            isAuditor: false,
        });
        onWillStart(async () => {
            const [isManager, isAuditor] = await Promise.all([
                user.hasGroup("compliance_audit_management.group_compliance_manager"),
                user.hasGroup("compliance_audit_management.group_compliance_auditor"),
            ]);
            this.state.isManager = isManager;
            this.state.isAuditor = isAuditor;
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("compliance.dashboard", "get_dashboard_data", []);
        } catch (error) {
            this.state.data = null;
            this.state.error = error?.data?.message || error?.message || "Could not load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || {
            kpis: {},
            health_by_category: [],
            attention: [],
            upcoming_activities: [],
        };
    }

    get kpis() {
        return this.data.kpis || {};
    }

    get overallCompliance() {
        return `${this.kpis.overall_compliance_rate ?? 0}%`;
    }

    get canLogActivity() {
        return this.state.isManager;
    }

    openNav(tag) {
        const item = CA_NAV.find((entry) => entry.tag === tag);
        this.action.doAction(item?.xmlid || tag, { clearBreadcrumbs: true, forceLeave: true });
    }

    openNative(xmlid) {
        this.action.doAction(xmlid);
    }

    openLogActivity() {
        this.action.doAction("compliance_audit_management.action_ca_activities_ui", {
            additionalContext: { ca_mode: "create" },
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    openAttention(item) {
        if (item?.action_xmlid) {
            this.action.doAction(item.action_xmlid, { clearBreadcrumbs: true, forceLeave: true });
            return;
        }
        if (item?.res_model && item?.res_id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: item.res_model,
                res_id: item.res_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }

    formatDue(value) {
        if (!value) {
            return "";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }
}

registry.category("actions").add("compliance_audit_management.action_dashboard", ComplianceDashboard);
