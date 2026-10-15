import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class AiCopilotSystray extends Component {
    static template = "ai_copilot.Systray";
    static props = {};

    setup() {
        this.action = useService("action");
        this.state = useState({ allowed: false });
        onWillStart(async () => {
            this.state.allowed = await user.hasGroup("ai_copilot.group_copilot_user");
        });
    }

    open() {
        const current = this.action.currentController;
        const context = {};
        const resModel = current?.props?.resModel || current?.action?.res_model;
        const resId = current?.props?.resId || current?.action?.res_id;
        if (resModel) {
            context.ai_model = resModel;
            context.ai_res_id = resId || false;
        }
        this.action.doAction("ai_copilot.action_ai_copilot", {
            additionalContext: context,
            clearBreadcrumbs: true,
        });
    }
}

registry.category("systray").add("ai_copilot.Systray", { Component: AiCopilotSystray }, { sequence: 25 });
