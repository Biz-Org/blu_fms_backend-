/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaDashboard extends Component {
    static template = "video_analytics.Dashboard";
    static props = VaScreenProps;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            data: { kpis: {}, recent_events: [], recent_detections: [], zones: [] },
        });
        onWillStart(() => this.load());
    }

    healthWidth(key) {
        const total = Number(this.state.data.kpis.cameras_total) || 0;
        const value = Number(this.state.data.kpis[key]) || 0;
        return this.meterWidth(total ? (value / total) * 100 : 0);
    }

    goPlayback() {
        if (this.props.onNavigate) {
            this.props.onNavigate("playback");
        }
    }

    get flow() {
        return this.workflowInfo(false);
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("va.ui.api", "get_dashboard_data", []);
            this.state.data.zones = this.state.data.zones || [];
            this.state.data.recent_events = this.state.data.recent_events || [];
            this.state.data.kpis = this.state.data.kpis || {};
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.loading = false;
    }
}
