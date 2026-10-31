/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaOccupancy extends Component {
    static template = "video_analytics.Occupancy";
    static props = VaScreenProps;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            zones: [],
            snapshots: [],
            trend: [],
            kpis: {},
        });
        onWillStart(() => this.load());
    }

    get crowdSnapshots() {
        return (this.state.snapshots || []).filter((row) => row.event_id || row.over_threshold).slice(0, 8);
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("va.ui.api", "get_occupancy_data", []);
            this.state.zones = data.zones || [];
            this.state.snapshots = data.snapshots || [];
            this.state.trend = data.trend || [];
            this.state.kpis = data.kpis || {};
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.loading = false;
    }
}
