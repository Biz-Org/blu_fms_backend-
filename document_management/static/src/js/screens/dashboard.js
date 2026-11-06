/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, display, extractError, formatBytes, formatLabel } from "../dm_utils";

export class DashboardScreen extends Component {
    static template = "document_management.Dashboard";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            kpis: null,
            recent: [],
            distribution: [],
            status_summary: {},
            quick_action_counts: {},
            showFilters: false,
            query: this.props.shellSearch || "",
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("document.management.ui.api", "get_dashboard_data", []);
            this.state.kpis = data.kpis || {};
            this.state.recent = data.recent || [];
            this.state.distribution = data.distribution || [];
            this.state.status_summary = data.status_summary || {};
            this.state.quick_action_counts = data.quick_action_counts || {};
        } catch (err) {
            this.state.error = extractError(err);
            this.state.kpis = null;
            this.state.recent = [];
            this.state.distribution = [];
        } finally {
            this.state.loading = false;
        }
    }

    get isEmpty() {
        return !(this.state.recent || []).length && !(Number((this.state.kpis || {}).documents_total));
    }

    get storageLabel() {
        return formatBytes((this.state.kpis || {}).storage_used);
    }

    count(value) {
        return Number(value || 0).toLocaleString();
    }

    display(value) {
        return display(value);
    }

    label(value) {
        return formatLabel(value);
    }

    badgeClass(state) {
        if (state === "approved") {
            return "dm-badge-ok";
        }
        if (state === "pending_approval") {
            return "dm-badge-warn";
        }
        if (state === "rejected" || state === "expired") {
            return "dm-badge-danger";
        }
        return "dm-badge-muted";
    }

    barStyle(count) {
        const max = Math.max(...(this.state.distribution || []).map((row) => Number(row.count) || 0), 1);
        const height = Math.max(8, Math.round((Number(count) || 0) / max * 140));
        return `height:${height}px`;
    }

    openScreen(screen, documentId) {
        if (this.props.navigate) {
            this.props.navigate(screen, documentId ? { documentId } : {});
        }
    }

    openRecent(ev) {
        this.openScreen("details", Number(ev.currentTarget.dataset.id));
    }

    goUpload() {
        this.openScreen("upload");
    }

    goApproval() {
        this.openScreen("approval");
    }

    goRepository() {
        this.openScreen("repository");
    }

    goSearch() {
        if (this.props.navigate) {
            this.props.navigate("search");
        }
    }

    toggleFilters() {
        this.state.showFilters = !this.state.showFilters;
    }
}
