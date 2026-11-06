/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, VaFormatMixin, VaScreenProps } from "../va_utils";

export class VaCctv extends Component {
    static template = "video_analytics.Cctv";
    static props = VaScreenProps;
    static pageSize = 8;

    setup() {
        Object.assign(this, VaFormatMixin);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            search: "",
            status: "",
            cameras: [],
            selected: null,
            location: "",
            kpis: {},
            actionBusy: false,
            filtersOpen: false,
            viewMode: "grid",
            pageIndex: 0,
        });
        onWillStart(() => this.load());
    }

    get locations() {
        const groups = {};
        for (const cam of this.state.cameras) {
            const name = cam.location_label || "Unassigned";
            if (!groups[name]) {
                groups[name] = [];
            }
            groups[name].push(cam);
        }
        const items = Object.keys(groups).map((name) => ({
            key: name,
            name,
            label: name,
            count: groups[name].length,
            cameras: groups[name],
        }));
        return [
            { key: "all", name: "", label: "All locations", count: this.state.cameras.length, cameras: this.state.cameras },
            ...items,
        ];
    }

    get visibleCameras() {
        const loc = this.locations.find((item) => item.name === this.state.location);
        return loc ? loc.cameras : this.state.cameras;
    }

    get maxPage() {
        const total = this.visibleCameras.length;
        if (!total) {
            return 0;
        }
        return Math.max(0, Math.ceil(total / this.constructor.pageSize) - 1);
    }

    get pagedCameras() {
        const size = this.constructor.pageSize;
        const start = this.state.pageIndex * size;
        return this.visibleCameras.slice(start, start + size);
    }

    get showingLabel() {
        const total = this.visibleCameras.length;
        if (!total) {
            return "Showing 0 of 0 cameras";
        }
        const size = this.constructor.pageSize;
        const start = this.state.pageIndex * size + 1;
        const end = Math.min(total, start + this.pagedCameras.length - 1);
        const loc = this.state.location || "all locations";
        return `Showing ${start}–${end} of ${total} in ${loc}`;
    }

    selectLocation(ev) {
        this.state.location = ev.currentTarget.dataset.location || "";
        this.state.pageIndex = 0;
    }

    toggleFilters() {
        this.state.filtersOpen = !this.state.filtersOpen;
    }

    showGrid() {
        this.state.viewMode = "grid";
    }

    showList() {
        this.state.viewMode = "list";
    }

    prevPage() {
        this.state.pageIndex = Math.max(0, this.state.pageIndex - 1);
    }

    nextPage() {
        this.state.pageIndex = Math.min(this.maxPage, this.state.pageIndex + 1);
    }

    applyFilters() {
        this.state.pageIndex = 0;
        this.load();
    }

    async load(cameraId) {
        const selectedId = typeof cameraId === "number" ? cameraId : (this.state.selected && this.state.selected.id) || false;
        const blocking = this.state.loading;
        this.state.error = null;
        try {
            const data = await this.orm.call("va.ui.api", "get_cctv_data", [{
                search: this.props.searchQuery || this.state.search,
                status: this.state.status,
                camera_id: selectedId,
            }]);
            this.state.cameras = data.cameras || [];
            this.state.selected = data.selected || null;
            this.state.kpis = data.kpis || {};
            if (this.state.pageIndex > this.maxPage) {
                this.state.pageIndex = this.maxPage;
            }
        } catch (err) {
            this.state.error = extractError(err);
        }
        if (blocking) {
            this.state.loading = false;
        }
    }

    selectCamera(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.load(id);
    }

    async testConnection() {
        if (!this.state.selected || !this.props.session.can_test_connection) {
            return;
        }
        this.state.actionBusy = true;
        try {
            const result = await this.orm.call("va.ui.api", "run_camera_action", [
                this.state.selected.id,
                "test_connection",
            ]);
            this.notification.add(result.message || "Connection test completed.", { type: "info" });
            await this.load(this.state.selected.id);
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.actionBusy = false;
    }

    async resolveStream() {
        if (!this.state.selected) {
            return;
        }
        this.state.actionBusy = true;
        try {
            const result = await this.orm.call("va.ui.api", "run_camera_action", [
                this.state.selected.id,
                "resolve_stream",
            ]);
            this.notification.add(
                result.available ? "Stored stream metadata is available." : "No stream URL is stored for this camera.",
                { type: "info" }
            );
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.actionBusy = false;
    }

    async setStatus(ev) {
        if (!this.state.selected || !this.props.session.can_manage_cameras) {
            return;
        }
        const status = ev.currentTarget.dataset.status;
        this.state.actionBusy = true;
        try {
            await this.orm.call("va.ui.api", "run_camera_action", [
                this.state.selected.id,
                "set_status",
                { status },
            ]);
            await this.load(this.state.selected.id);
        } catch (err) {
            this.state.error = extractError(err);
        }
        this.state.actionBusy = false;
    }
}
