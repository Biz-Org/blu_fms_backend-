import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

export const CA_NAV = [
    {
        id: "dashboard",
        label: "Dashboard",
        icon: "fa-th-large",
        xmlid: "compliance_audit_management.action_ca_dashboard_ui",
        tag: "compliance_audit_management.action_dashboard",
    },
    {
        id: "activities",
        label: "Compliance Activities",
        icon: "fa-check-square-o",
        xmlid: "compliance_audit_management.action_ca_activities_ui",
        tag: "compliance_audit_management.action_activities",
    },
    {
        id: "documents",
        label: "Compliance Documents",
        icon: "fa-folder-open-o",
        xmlid: "compliance_audit_management.action_ca_documents_ui",
        tag: "compliance_audit_management.action_documents",
    },
    {
        id: "calendar",
        label: "Compliance Calendar",
        icon: "fa-calendar",
        xmlid: "compliance_audit_management.action_ca_calendar_ui",
        tag: "compliance_audit_management.action_calendar",
    },
    {
        id: "audits",
        label: "Audits & Inspections",
        icon: "fa-clipboard",
        xmlid: "compliance_audit_management.action_ca_audits_ui",
        tag: "compliance_audit_management.action_audits",
    },
    {
        id: "non_compliance",
        label: "Non-Compliance",
        icon: "fa-exclamation-triangle",
        xmlid: "compliance_audit_management.action_ca_nc_ui",
        tag: "compliance_audit_management.action_non_compliance",
    },
    {
        id: "regulatory",
        label: "Regulatory Reporting",
        icon: "fa-file-text-o",
        xmlid: "compliance_audit_management.action_ca_regulatory_ui",
        tag: "compliance_audit_management.action_regulatory",
    },
    {
        id: "reports",
        label: "Compliance Reports",
        icon: "fa-bar-chart",
        xmlid: "compliance_audit_management.action_ca_reports_ui",
        tag: "compliance_audit_management.action_reports",
    },
];

export class CaAppShell extends Component {
    static template = "compliance_audit_management.CaAppShell";
    static props = {
        active: String,
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.user = user;
        this.state = useState({
            isManager: false,
            isAuditor: false,
            isSystem: false,
        });
        onWillStart(async () => {
            const [isManager, isAuditor, isSystem] = await Promise.all([
                user.hasGroup("compliance_audit_management.group_compliance_manager"),
                user.hasGroup("compliance_audit_management.group_compliance_auditor"),
                user.hasGroup("base.group_system"),
            ]);
            Object.assign(this.state, { isManager, isAuditor, isSystem });
        });
    }

    get nav() {
        return CA_NAV;
    }

    get canOpenSettings() {
        return this.state.isSystem || this.state.isManager;
    }

    get roleLabel() {
        if (this.state.isManager) {
            return "Compliance Manager";
        }
        if (this.state.isAuditor) {
            return "Compliance Auditor";
        }
        return "Compliance";
    }

    get avatarUrl() {
        return `/web/image/res.users/${user.userId}/avatar_128`;
    }

    open(item) {
        this.action.doAction(item.xmlid, { clearBreadcrumbs: true, forceLeave: true });
    }

    openProfile() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            res_id: user.userId,
            views: [[false, "form"]],
            target: "new",
            name: "User Profile",
        });
    }

    openSettings() {
        this.action.doAction("base_setup.action_general_configuration", {
            clearBreadcrumbs: true,
        });
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }
}
