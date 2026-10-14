import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class CcPollVote extends Component {
    static template = "community_communication.PollVote";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ payload: null, selected: [], confirmed: false });
        onWillStart(() => this.reload());
    }

    get recordId() {
        return this.props.record?.resId;
    }

    async reload() {
        if (!this.recordId) {
            return;
        }
        this.state.payload = await this.orm.call(
            "community.communication.poll",
            "get_vote_payload",
            [this.recordId]
        );
        this.state.confirmed = Boolean(this.state.payload.has_voted);
    }

    toggle(optionId) {
        if (this.state.payload.response_type === "single") {
            this.state.selected = [optionId];
            return;
        }
        if (this.state.selected.includes(optionId)) {
            this.state.selected = this.state.selected.filter((id) => id !== optionId);
        } else {
            this.state.selected = [...this.state.selected, optionId];
        }
    }

    async submit() {
        this.state.payload = await this.orm.call(
            "community.communication.poll",
            "action_vote",
            [this.recordId, this.state.selected]
        );
        this.state.confirmed = true;
        this.notification.add("Your vote has been recorded", { type: "success" });
    }
}

export const ccPollVote = { component: CcPollVote };
registry.category("view_widgets").add("cc_poll_vote", ccPollVote);
