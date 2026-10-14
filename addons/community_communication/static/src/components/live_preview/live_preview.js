import { Component, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class CcLivePreview extends Component {
    static template = "community_communication.LivePreview";
    static props = { ...standardWidgetProps, record: { type: Object, optional: true } };

    get record() {
        return this.props.record;
    }

    get data() {
        return this.record?.data || {};
    }

    get model() {
        return this.record?.resModel || "";
    }

    get title() {
        return this.data.title || this.data.question || this.data.name || this.data.subject || "Untitled";
    }

    get category() {
        return this.data.category || "";
    }

    get bodyHtml() {
        const raw = this.data.body || this.data.description || "";
        return raw ? markup(raw) : "";
    }

    get options() {
        const list = this.data.option_ids;
        if (!list?.records) {
            return [];
        }
        return list.records.map((rec) => rec.data.name).filter(Boolean);
    }

    get audience() {
        const map = {
            community: "Entire Community",
            buildings: "Specific Buildings",
            groups: "Resident Groups",
        };
        return map[this.data.audience_type] || "Entire Community";
    }

    get kicker() {
        if (this.model.includes("poll")) {
            return "Resident preview";
        }
        if (this.model.includes("event")) {
            return "Event preview";
        }
        if (this.model.includes("notice")) {
            return "Notice board preview";
        }
        return "Preview";
    }
}

export const ccLivePreview = { component: CcLivePreview };
registry.category("view_widgets").add("cc_live_preview", ccLivePreview);
