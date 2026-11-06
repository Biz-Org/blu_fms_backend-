/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaDetection extends Component {
    static template = "video_analytics.Detection";
    static props = VaScreenProps;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            filters: { detection_type: "", state: "", zone_id: "" },
            detections: [],
            zones: [],
            rules: [],
            cameras: [],
            kpis: {},
        });
        onWillStart(() => this.load());
    }

    async load() {
        const blocking = this.state.loading;
        this.state.error = null;
        try {
            const data = await this.orm.call("va.ui.api", "get_detection_data", [this.state.filters]);
            this.state.detections = data.detections || [];
            this.state.zones = data.zones || [];
            this.state.rules = data.rules || [];
            this.state.cameras = data.cameras || [];
            this.state.kpis = data.kpis || {};
        } catch (err) {
            this.state.error = extractError(err);
        }
        if (blocking) {
            this.state.loading = false;
        }
    }

    get selectedZoneName() {
        const id = Number(this.state.filters.zone_id);
        if (!id) {
            return "";
        }
        const zone = this.state.zones.find((item) => item.id === id);
        return zone ? zone.name : "";
    }

    get liveCamera() {
        const first = this.state.detections[0];
        if (first && first.camera_name) {
            return { name: first.camera_name, zone: first.zone_name || this.selectedZoneName };
        }
        const camera = this.state.cameras[0];
        if (camera) {
            return { name: camera.name, zone: this.selectedZoneName };
        }
        return null;
    }

    get liveCameraLabel() {
        const cam = this.liveCamera;
        if (!cam) {
            return "";
        }
        if (cam.zone) {
            return `${cam.name} (${cam.zone})`.toUpperCase();
        }
        return String(cam.name).toUpperCase();
    }

    get liveEvidenceUrl() {
        const row = this.state.detections.find((item) => item.evidence_url);
        return row ? row.evidence_url : "";
    }

    get liveAlert() {
        return this.state.detections.find((row) => row.detection_type === "intrusion" && (row.state === "new" || row.state === "linked")) || null;
    }

    get overlayDetections() {
        return this.state.detections.slice(0, 2).map((row, index) => ({
            id: row.id,
            tone: row.detection_type === "ppe_violation" || row.detection_type === "intrusion" || row.detection_type === "fire_smoke" ? "danger" : "ok",
            slot: index === 0 ? "mid" : "right",
            title: `${row.detection_type_label} ${this.formatConfidence(row.confidence)}`,
            meta: row.zone_name || row.state_label || "",
        }));
    }

    get recentDetections() {
        return this.state.detections.slice(0, 8).map((row) => ({
            ...row,
            tone: this.rowTone(row),
        }));
    }

    get hasTrend() {
        const value = this.state.kpis.active_trend_pct;
        return value !== false && value !== null && value !== undefined;
    }

    get trendDown() {
        return this.hasTrend && Number(this.state.kpis.active_trend_pct) <= 0;
    }

    get trendAbs() {
        return Math.abs(Number(this.state.kpis.active_trend_pct) || 0);
    }

    get ppeComplianceLabel() {
        const value = this.state.kpis.ppe_compliance;
        if (value === false || value === null || value === undefined) {
            return "—";
        }
        return this.formatPercent(value);
    }

    get ppeStatus() {
        if (this.state.kpis.ppe_compliance === false || this.state.kpis.ppe_compliance === null || this.state.kpis.ppe_compliance === undefined) {
            return "No PPE records";
        }
        return this.state.kpis.ppe_compliance >= 95 ? "Stable" : "Watch";
    }

    get healthHint() {
        const total = Number(this.state.kpis.cameras_total) || 0;
        const online = Number(this.state.kpis.cameras_online) || 0;
        if (!total) {
            return "No cameras";
        }
        if (online === total) {
            return "All nodes up";
        }
        return `${online} / ${total} online`;
    }

    get thresholdValue() {
        const stored = this.state.kpis.confidence_threshold;
        if (stored === false || stored === null || stored === undefined) {
            return 0;
        }
        return stored;
    }

    get monitoringActive() {
        return this.state.rules.some((rule) => rule.active);
    }

    get autoLog() {
        return this.state.rules.some((rule) => rule.create_event);
    }

    get typeSummary() {
        const labels = [
            { type: "intrusion", label: "Restricted area intrusion", icon: "fa-ban", tone: "danger" },
            { type: "fire_smoke", label: "Fire / Smoke", icon: "fa-fire", tone: "warn" },
            { type: "ppe_violation", label: "PPE violation", icon: "fa-shield", tone: "warn" },
            { type: "vehicle_speeding", label: "Vehicle speeding", icon: "fa-truck", tone: "danger" },
            { type: "crowd_density", label: "Crowd density", icon: "fa-users", tone: "warn" },
            { type: "object_detection", label: "Object detection", icon: "fa-cube", tone: "success" },
        ];
        const counts = this.state.kpis.type_counts_today || {};
        return labels.map((item) => ({
            ...item,
            count: counts[item.type] || 0,
        }));
    }

    rowTone(row) {
        if (row.state === "dismissed") {
            return "success";
        }
        if (row.detection_type === "object_detection") {
            return "success";
        }
        if (row.detection_type === "ppe_violation" || row.detection_type === "crowd_density") {
            return "warn";
        }
        return "danger";
    }

    goAlerts() {
        if (this.props.onNavigate) {
            this.props.onNavigate("alerts");
        }
    }

    goPlayback() {
        if (this.props.onNavigate) {
            this.props.onNavigate("playback");
        }
    }

    get flow() {
        return this.workflowInfo(false, { highlight: "detection" });
    }
}
