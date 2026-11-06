/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
// asset:document_management_workflow
import { SHELL_PROPS } from "../dm_utils";

const STEPS = [
    { id: 1, name: "Intake" },
    { id: 2, name: "Categorize" },
    { id: 3, name: "Upload" },
    { id: 4, name: "Version" },
    { id: 5, name: "Review" },
    { id: 6, name: "Approve/Share" },
];

const PREVIEW_WORKFLOWS = [
    {
        id: "invoice",
        name: "Invoice Approval",
        description: "Standard workflow for all incoming invoices",
        current: 3,
        version: 1,
        steps: STEPS,
        roles: ["Accounts Payable", "Finance Manager"],
        sla: "48 Hours",
        triggers: ["On document creation", "After 24h delay"],
    },
    {
        id: "review",
        name: "Document Review",
        description: "Internal review path for policy and procedure files",
        current: 2,
        version: 1,
        steps: STEPS,
        roles: ["Document Owner", "Compliance"],
        sla: "72 Hours",
        triggers: ["On new version", "After 48h delay"],
    },
    {
        id: "contract",
        name: "Contract Approval",
        description: "Legal and finance sign-off for vendor contracts",
        current: 1,
        version: 1,
        steps: STEPS,
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
            workflows: PREVIEW_WORKFLOWS.map((item) => Object.assign({}, item, { steps: STEPS })),
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
        const id = `wf-${this.state.workflows.length + 1}`;
        this.state.workflows.push({
            id,
            name: "Untitled Workflow",
            description: "New document workflow",
            current: 1,
            version: 1,
            steps: STEPS,
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
