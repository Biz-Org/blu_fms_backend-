import { Component, onWillStart, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class CcDiscussionThread extends Component {
    static template = "community_communication.DiscussionThread";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ payload: null, reply: "" });
        onWillStart(() => this.reload());
    }

    get recordId() {
        return this.props.record?.resId;
    }

    async reload() {
        if (!this.recordId) {
            this.state.payload = null;
            return;
        }
        this.state.payload = await this.orm.call(
            "community.communication.discussion",
            "get_thread_payload",
            [this.recordId]
        );
    }

    body(html) {
        return html ? markup(html) : "";
    }

    async follow() {
        await this.orm.call("community.communication.discussion", "action_follow", [this.recordId]);
        await this.reload();
    }

    async unfollow() {
        await this.orm.call("community.communication.discussion", "action_unfollow", [this.recordId]);
        await this.reload();
    }

    async react(type) {
        await this.orm.call("community.communication.discussion", "action_react", [this.recordId, type]);
        await this.reload();
    }

    async moderate(method) {
        await this.orm.call("community.communication.discussion", method, [this.recordId]);
        await this.reload();
    }

    async postReply() {
        if (!this.state.reply.trim()) {
            return;
        }
        await this.orm.call("community.communication.discussion", "action_post_comment", [
            this.recordId,
            this.state.reply,
        ]);
        this.state.reply = "";
        this.notification.add("Reply posted", { type: "success" });
        await this.reload();
    }
}

export const ccDiscussionThread = { component: CcDiscussionThread };
registry.category("view_widgets").add("cc_discussion_thread", ccDiscussionThread);
