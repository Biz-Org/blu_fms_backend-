import { Component } from "@odoo/owl";

export class AiAppShell extends Component {
    static template = "ai_copilot.AppShell";
    static props = {
        panel: String,
        apps: { type: Array, optional: true },
        canAdmin: { type: Boolean, optional: true },
        userName: { type: String, optional: true },
        companyName: { type: String, optional: true },
        navOpen: { type: Boolean, optional: true },
        onPanel: Function,
        onApp: Function,
        onToggleNav: Function,
    };

    get apps() {
        return this.props.apps || [];
    }
}
