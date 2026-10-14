import { Component } from "@odoo/owl";
import { CaAppShell, CA_NAV } from "@compliance_audit_management/owl/ui/ca_shell";

/** Kept for asset compatibility; all primary screens are now real OWL boards. */
export class CaPlaceholderScreen extends Component {
    static template = "compliance_audit_management.Placeholder";
    static components = { CaAppShell };
    static props = ["*"];

    get navId() {
        const tag = this.props.action?.tag || "";
        const item = CA_NAV.find((entry) => entry.tag === tag);
        return item?.id || "dashboard";
    }

    get copy() {
        return {
            title: "Compliance & Audit",
            hint: "This screen is scheduled for a later phase.",
        };
    }
}
