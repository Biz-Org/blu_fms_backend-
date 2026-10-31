/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, extractError, formatLabel } from "../dm_utils";

const PAGE_SIZE = 4;

export class AccessScreen extends Component {
    static template = "document_management.Access";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            rows: [],
            kpis: {},
            document: null,
            userId: "",
            groupId: "",
            role: "viewer",
            expiry: "",
            lastLink: null,
            dialog: false,
            page: 1,
        });
        onWillStart(() => this.refresh());
        onWillUpdateProps((next) => {
            if (next.documentId !== this.props.documentId) {
                return this.refresh(next.documentId);
            }
        });
    }

    async refresh(documentId) {
        const id = documentId || this.props.documentId || false;
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("document.management.ui.api", "get_access_matrix", [id]);
            this.state.rows = data.rows || [];
            this.state.kpis = data.kpis || {};
            this.state.document = null;
            if (id) {
                this.state.document = await this.orm.call("document.management.ui.api", "get_document", [id]);
            }
            this.state.page = 1;
        } catch (err) {
            this.state.error = extractError(err);
            this.state.rows = [];
            this.state.kpis = {};
            this.state.document = null;
        } finally {
            this.state.loading = false;
        }
    }

    get isEmpty() {
        return !this.props.documentId;
    }

    get hasDocument() {
        return Boolean(this.props.documentId);
    }

    get catalogs() {
        return this.props.session.catalogs || { groups: [] };
    }

    get groups() {
        return (this.catalogs.groups) || [];
    }

    get users() {
        return this.props.session.users || [];
    }

    get contextLine() {
        return `Context: ${this.contextName}`;
    }

    get contextName() {
        const doc = this.state.document;
        if (!doc) {
            return "Fire Safety Policy v3.2";
        }
        const version = doc.current_version ? ` ${doc.current_version}` : "";
        return `${doc.name}${version}`;
    }

    get accessLevelValue() {
        if (!this.hasDocument) {
            return "Internal";
        }
        const doc = this.state.document || {};
        if (doc.classification) {
            return formatLabel(doc.classification);
        }
        const level = this.state.kpis && this.state.kpis.access_level;
        if (!level) {
            return "—";
        }
        if (level === "role_restricted") {
            return "Restricted";
        }
        return formatLabel(level);
    }

    get restrictedBadge() {
        if (!this.hasDocument) {
            return "Restricted";
        }
        const level = this.state.kpis && this.state.kpis.access_level;
        if (level === "role_restricted") {
            return "Restricted";
        }
        return "";
    }

    get activeUsers() {
        if (!this.hasDocument) {
            return 42;
        }
        return (this.state.kpis && this.state.kpis.active_users) || 0;
    }

    get groupCount() {
        if (!this.hasDocument) {
            return 6;
        }
        return (this.state.kpis && this.state.kpis.groups) || 0;
    }

    get externalLinks() {
        if (!this.hasDocument) {
            return 2;
        }
        return (this.state.kpis && this.state.kpis.external_links) || 0;
    }

    get usersWeekHint() {
        if (!this.hasDocument) {
            return "+3 this week";
        }
        const count = (this.state.kpis && this.state.kpis.users_this_week) || 0;
        if (!count) {
            return "";
        }
        return `+${count} this week`;
    }

    get externalLabel() {
        return `${this.externalLinks} Active`;
    }

    get hasLinkAlert() {
        return this.externalLinks > 0;
    }

    get linkReviewHint() {
        if (!this.hasDocument) {
            return "Requires review in 5 days";
        }
        const now = Date.now();
        let nearest = null;
        for (const row of this.state.rows || []) {
            if (row.type !== "link" || !row.expiry) {
                continue;
            }
            const date = new Date(row.expiry);
            if (Number.isNaN(date.getTime())) {
                continue;
            }
            const days = Math.ceil((date.getTime() - now) / 86400000);
            if (nearest === null || days < nearest) {
                nearest = days;
            }
        }
        if (nearest === null) {
            return "";
        }
        if (nearest < 0) {
            return "Review overdue";
        }
        if (nearest === 0) {
            return "Requires review today";
        }
        return `Requires review in ${nearest} day${nearest === 1 ? "" : "s"}`;
    }

    get previewRows() {
        return [
            {
                id: "preview-hs",
                name: "Health & Safety Dept",
                type: "group",
                role: "owner",
                perm_read: true,
                perm_write: true,
                perm_download: true,
                perm_share: true,
                origin: "inherited",
                mark: "HS",
            },
            {
                id: "preview-sj",
                name: "Sarah Jenkins",
                type: "user",
                role: "editor",
                perm_read: true,
                perm_write: true,
                perm_download: true,
                perm_share: false,
                origin: "direct",
            },
            {
                id: "preview-link",
                name: "External Auditors Link",
                type: "link",
                role: "viewer",
                perm_read: true,
                perm_write: false,
                perm_download: true,
                perm_share: false,
                origin: "direct",
                expiry: new Date(Date.now() + 5 * 86400000).toISOString(),
                url: "/document_management/share/preview",
            },
            {
                id: "preview-all",
                name: "All Employees",
                type: "group",
                role: "viewer",
                perm_read: true,
                perm_write: false,
                perm_download: false,
                perm_share: false,
                origin: "direct",
                mark: "ALL",
            },
        ];
    }

    get pageRows() {
        const start = (this.state.page - 1) * PAGE_SIZE;
        return (this.state.rows || []).slice(start, start + PAGE_SIZE);
    }

    get displayRows() {
        if (this.hasDocument && this.pageRows.length) {
            return this.pageRows;
        }
        if (!this.hasDocument) {
            return this.previewRows;
        }
        return [0, 1, 2, 3].map((index) => ({
            id: `empty-${index}`,
            empty: true,
            first: index === 0,
        }));
    }

    get pageCount() {
        if (!this.hasDocument) {
            return 3;
        }
        return Math.max(1, Math.ceil((this.state.rows || []).length / PAGE_SIZE) || 1);
    }

    get pageNumbers() {
        return [1, 2, 3];
    }

    get showingLabel() {
        if (!this.hasDocument) {
            return "Showing 1 to 4 of 12 entries";
        }
        const total = (this.state.rows || []).length;
        if (!total) {
            return "Showing 0 to 0 of 0 entries";
        }
        const start = (this.state.page - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.page * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    rowMark(row) {
        return (row && row.mark) || "";
    }

    label(value) {
        const raw = formatLabel(value);
        if (!raw || raw === "—") {
            return raw;
        }
        return raw.replace(/\b\w/g, (char) => char.toUpperCase());
    }

    typeLabel(row) {
        if (row.type === "group") {
            return "Group";
        }
        if (row.type === "link") {
            return "Link";
        }
        if (row.type === "user") {
            return "User";
        }
        return formatLabel(row.type);
    }

    rowIcon(row) {
        if (row.type === "group") {
            return "fa fa-users";
        }
        if (row.type === "link") {
            return "fa fa-link";
        }
        return "fa fa-user";
    }

    rowKey(row) {
        if (row.empty) {
            return row.id;
        }
        return `${row.type || "row"}-${row.id}`;
    }

    permClass(on) {
        return on ? "fa fa-check-circle dm-check" : "fa fa-circle-o dm-uncheck";
    }

    expiryDays(row) {
        if (!row || !row.expiry) {
            return null;
        }
        const date = new Date(row.expiry);
        if (Number.isNaN(date.getTime())) {
            return null;
        }
        return Math.ceil((date.getTime() - Date.now()) / 86400000);
    }

    statusLabel(row) {
        if (row.type === "link") {
            const days = this.expiryDays(row);
            if (days !== null && days >= 0) {
                return `EXP ${days} DAY${days === 1 ? "" : "S"}`;
            }
            if (days !== null && days < 0) {
                return "EXPIRED";
            }
        }
        if (row.origin === "inherited") {
            return "INHERITED";
        }
        if (row.origin === "direct") {
            return "DIRECT";
        }
        return formatLabel(row.status || row.origin).toUpperCase();
    }

    statusClass(row) {
        const label = this.statusLabel(row);
        if (label === "EXPIRED") {
            return "dm-access-status is-expired";
        }
        if (label.startsWith("EXP ")) {
            return "dm-access-status is-exp";
        }
        return "dm-access-status";
    }

    canRevoke(row) {
        return row.origin !== "inherited";
    }

    setPage(ev) {
        const page = Number(ev.currentTarget.dataset.page) || 1;
        if (page > this.pageCount) {
            return;
        }
        this.state.page = page;
    }

    shiftPage(ev) {
        const next = this.state.page + Number(ev.currentTarget.dataset.dir || 0);
        this.state.page = Math.min(this.pageCount, Math.max(1, next));
    }

    openUser() {
        if (!this.hasDocument) {
            return;
        }
        this.state.dialog = "user";
    }

    openGroup() {
        if (!this.hasDocument) {
            return;
        }
        this.state.dialog = "group";
    }

    openLink() {
        if (!this.hasDocument) {
            return;
        }
        this.state.dialog = "link";
    }

    closeDialog() {
        this.state.dialog = false;
    }

    async addUser() {
        if (!this.hasDocument) {
            return;
        }
        await this.orm.call("document.management.ui.api", "add_access", [
            this.props.documentId,
            { partner_type: "user", user_id: Number(this.state.userId), role: this.state.role },
        ]);
        this.closeDialog();
        await this.refresh();
        if (this.props.refreshSession) {
            await this.props.refreshSession();
        }
    }

    async addGroup() {
        if (!this.hasDocument) {
            return;
        }
        await this.orm.call("document.management.ui.api", "add_access", [
            this.props.documentId,
            { partner_type: "group", group_id: Number(this.state.groupId), role: this.state.role },
        ]);
        this.closeDialog();
        await this.refresh();
    }

    async addLink() {
        if (!this.hasDocument) {
            return;
        }
        const data = await this.orm.call("document.management.ui.api", "create_share_link", [
            this.props.documentId,
            { expiry: this.state.expiry, perm_download: true },
        ]);
        this.state.lastLink = data;
        this.closeDialog();
        await this.refresh();
    }

    copyLink(ev) {
        const url = ev.currentTarget.dataset.url;
        if (!url || !navigator.clipboard) {
            return;
        }
        navigator.clipboard.writeText(url);
    }

    async revoke(ev) {
        if (!this.hasDocument) {
            return;
        }
        const id = Number(ev.currentTarget.dataset.id);
        const type = ev.currentTarget.dataset.type;
        if (type === "link") {
            await this.orm.call("document.management.ui.api", "revoke_share_link", [this.props.documentId, id]);
        } else {
            await this.orm.call("document.management.ui.api", "revoke_access", [this.props.documentId, id]);
        }
        await this.refresh();
    }
}
