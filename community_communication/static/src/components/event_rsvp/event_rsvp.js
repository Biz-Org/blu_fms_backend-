import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class CcEventRsvp extends Component {
    static template = "community_communication.EventRsvp";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ registration: null, error: "" });
    }

    get event() {
        return this.props.record?.data || {};
    }

    async register() {
        this.state.error = "";
        try {
            await this.orm.call(
                "community.communication.event",
                "action_register",
                [this.props.record.resId]
            );
            this.state.registration = await this.orm.call(
                "community.communication.event",
                "get_my_registration",
                [this.props.record.resId]
            );
            this.notification.add(
                this.state.registration.state === "waitlisted" ? "You are on the waitlist" : "Registration confirmed",
                { type: "success" }
            );
        } catch (error) {
            this.state.error = error.data?.message || error.message || "Unable to register";
        }
    }
}

export const ccEventRsvp = { component: CcEventRsvp };
registry.category("view_widgets").add("cc_event_rsvp", ccEventRsvp);
