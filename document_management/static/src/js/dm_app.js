/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { extractError, SHELL_PROPS } from "./dm_utils";
import { DashboardScreen } from "./screens/dashboard";
import { RepositoryScreen } from "./screens/repository";
import { UploadScreen } from "./screens/upload";
import { DetailsScreen } from "./screens/details";
import { AccessScreen } from "./screens/access";
import { ApprovalScreen } from "./screens/approval";
import { SearchScreen } from "./screens/search";
import { AuditScreen } from "./screens/audit";
// ./screens/workflow is bundled through this app file so the action still registers.

const SCREENS = [
    {
        id: "dashboard",
        label: "DM Dashboard",
        icon: "fa-th-large",
        title: "Document Management Dashboard",
        crumb: "Dashboard",
        subtitle: "Repository activity, storage, approvals and expiry.",
    },
    {
        id: "repository",
        label: "DM Repository",
        icon: "fa-folder-open",
        title: "Document Repository",
        crumb: "Repository",
        subtitle: "Browse and organize authorized documents.",
    },
    {
        id: "upload",
        label: "DM Upload",
        icon: "fa-upload",
        title: "Document Upload",
        crumb: "Upload",
        subtitle: "Add files with required metadata.",
    },
    {
        id: "details",
        label: "DM Details",
        icon: "fa-file-text-o",
        title: "Document Details",
        crumb: "Details",
        subtitle: "Metadata, versions, approval and activity.",
    },
    {
        id: "access",
        label: "DM Access Control",
        icon: "fa-lock",
        title: "Access Control & Sharing",
        crumb: "Access Control",
        subtitle: "Manage document permissions and share links.",
    },
    {
        id: "approval",
        label: "DM Approval & Expiry",
        icon: "fa-check-square-o",
        title: "Approval & Expiry",
        crumb: "Approval & Expiry",
        subtitle: "Review approvals and expiry follow-up.",
    },
    {
        id: "workflow",
        label: "DM Workflow",
        icon: "fa-sitemap",
        title: "Document Workflow",
        crumb: "Document Workflow",
        subtitle: "Document workflow stages and assigned roles.",
    },
    {
        id: "search",
        label: "DM AI Search",
        icon: "fa-search",
        title: "Document Search",
        crumb: "Search",
        subtitle: "Keyword search and AI retrieval.",
    },
    {
        id: "audit",
        label: "DM Audit",
        icon: "fa-list-alt",
        title: "Document Activity & Audit",
        crumb: "Activity & Audit",
        subtitle: "Document lifecycle and security events.",
    },
];

const WORKFLOW_STEPS = [
    { id: 1, name: "Intake" },
    { id: 2, name: "Categorize" },
    { id: 3, name: "Upload" },
    { id: 4, name: "Version" },
    { id: 5, name: "Review" },
    { id: 6, name: "Approve/Share" },
];

const PREVIEW_WORKFLOWS = [
    {
        id: 'invoice',
        name: "Invoice Approval",
        description: "Standard workflow for all incoming invoices",
        current: 3,
        version: 1,
        steps: WORKFLOW_STEPS,
        roles: ["Accounts Payable", "Finance Manager"],
        sla: "48 Hours",
        triggers: ["On document creation", "After 24h delay"],
    },
    {
        id: 'review',
        name: "Document Review",
        description: "Internal review path for policy and procedure files",
        current: 2,
        version: 1,
        steps: WORKFLOW_STEPS,
        roles: ["Document Owner", "Compliance"],
        sla: "72 Hours",
        triggers: ["On new version", "After 48h delay"],
    },
    {
        id: 'contract',
        name: "Contract Approval",
        description: "Legal and finance sign-off for vendor contracts",
        current: 1,
        version: 1,
        steps: WORKFLOW_STEPS,
        roles: ["Legal", "Procurement"],
        sla: "5 Days",
        triggers: ["On upload", "On expiry warning"],
    },
];

export class WorkflowScreen extends Component {
    static template = "document_management.Workflow";
    static props = SHELL_PROPS;

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            query: "",
            selectedId: "invoice",
            workflows: PREVIEW_WORKFLOWS.map((item) => Object.assign({}, item, { steps: WORKFLOW_STEPS })),
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        this.state.loading = false;
    }

    get filteredWorkflows() {
        const query = (this.state.query || "").trim().toLowerCase();
        const rows = this.state.workflows || [];
        if (!query) {
            return rows;
        }
        return rows.filter((item) => (item.name || "").toLowerCase().includes(query));
    }

    get selected() {
        const rows = this.state.workflows || [];
        return rows.find((item) => item.id === this.state.selectedId) || rows[0] || false;
    }

    get isEmpty() {
        return !this.filteredWorkflows.length;
    }

    selectWorkflow(ev) {
        this.state.selectedId = ev.currentTarget.dataset.id;
    }

    createWorkflow() {
        const id = "wf-" + (this.state.workflows.length + 1);
        this.state.workflows.push({
            id,
            name: "Untitled Workflow",
            description: "New document workflow",
            current: 1,
            version: 1,
            steps: WORKFLOW_STEPS,
            roles: [],
            sla: "—",
            triggers: [],
        });
        this.state.selectedId = id;
        this.state.query = "";
    }

    editWorkflow() {
        const selected = this.selected;
        if (!selected) {
            return;
        }
        selected.description = selected.description || "Standard document workflow";
    }

    newVersion() {
        const selected = this.selected;
        if (!selected) {
            return;
        }
        selected.version = (selected.version || 1) + 1;
    }

    stepClass(step) {
        const selected = this.selected;
        const current = selected ? selected.current : 0;
        if (step.id < current) {
            return "dm-wf-step is-done";
        }
        if (step.id === current) {
            return "dm-wf-step is-now";
        }
        return "dm-wf-step is-wait";
    }

    isSelected(item) {
        return item && item.id === (this.selected && this.selected.id);
    }

    isDone(step) {
        const selected = this.selected;
        return Boolean(selected && step && step.id < selected.current);
    }

    get hasRoles() {
        return Boolean(this.selected && (this.selected.roles || []).length);
    }

    get hasTriggers() {
        return Boolean(this.selected && (this.selected.triggers || []).length);
    }
}

export class DocumentManagementApp extends Component {
    static template = "document_management.App";
    static props = ["*"];
    static components = {
        DashboardScreen,
        RepositoryScreen,
        UploadScreen,
        DetailsScreen,
        AccessScreen,
        ApprovalScreen,
        WorkflowScreen,
        SearchScreen,
        AuditScreen,
    };

    setup() {
        this.orm = useService("orm");
        const initialScreen =
            this.props.action?.context?.dm_screen ||
            this.props.action?.params?.screen ||
            "dashboard";
        this.screens = SCREENS;
        this.state = useState({
            screen: SCREENS.some((item) => item.id === initialScreen)
                ? initialScreen
                : "dashboard",
            session: {
                uid: 0,
                name: "",
                is_user: false,
                is_manager: false,
                is_admin: false,
                unread_notification_count: 0,
                catalogs: { types: [], categories: [], folders: [], tags: [], groups: [] },
                users: [],
            },
            sessionError: null,
            menuOpen: false,
            topSearch: "",
            documentId: false,
            notesOpen: false,
            notes: [],
        });
        onWillStart(async () => {
            await this.refreshSession();
        });
    }

    async refreshSession() {
        try {
            const session = await this.orm.call("document.management.ui.api", "get_session_context", []);
            this.state.session = session || this.state.session;
        } catch (err) {
            this.state.sessionError = extractError(err);
        }
    }

    get current() {
        return this.screens.find((item) => item.id === this.state.screen) || this.screens[0];
    }

    get searchPlaceholder() {
        return "Search documents...";
    }

    get initials() {
        const name = this.state.session.name || "U";
        return name.trim().slice(0, 1).toUpperCase();
    }

    get roleLabel() {
        if (this.state.session.is_admin) {
            return "Administrator";
        }
        if (this.state.session.is_manager) {
            return "Manager";
        }
        return "User";
    }

    onNavClick(ev) {
        const screen = ev.currentTarget.dataset.screen;
        this.navigate(screen);
        this.closeMenu();
    }

    toggleMenu() {
        this.state.menuOpen = !this.state.menuOpen;
    }

    closeMenu() {
        this.state.menuOpen = false;
    }

    navigate(screen, options) {
        if (screen && this.screens.some((item) => item.id === screen)) {
            this.state.screen = screen;
            this.state.menuOpen = false;
        }
        if (options && Object.prototype.hasOwnProperty.call(options, "documentId")) {
            this.state.documentId = options.documentId || false;
        }
    }

    onShellSearch() {
        this.state.topSearch = (this.state.topSearch || "").trim();
        this.navigate("search");
    }

    async toggleNotes() {
        this.state.notesOpen = !this.state.notesOpen;
        if (this.state.notesOpen) {
            try {
                const data = await this.orm.call("document.management.ui.api", "list_notifications", []);
                this.state.notes = data.items || [];
            } catch (err) {
                this.state.sessionError = extractError(err);
            }
        }
    }

    async markNoteRead(ev) {
        const noteId = Number(ev.currentTarget.dataset.id);
        await this.orm.call("document.management.ui.api", "mark_notification_read", [noteId]);
        const data = await this.orm.call("document.management.ui.api", "list_notifications", []);
        this.state.notes = data.items || [];
        await this.refreshSession();
    }
}

registry.category("actions").add("document_management_app", DocumentManagementApp);
