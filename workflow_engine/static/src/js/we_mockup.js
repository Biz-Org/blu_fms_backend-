/** @odoo-module **/

/** Visual content copied from the PrecastMPS mockup screenshots. */

export const MOCK_APPROVALS = {
    activeRules: 28,
    expiring: 3,
    conflicts: 0,
    avgRouting: "1.2s",
    hierarchyName: "STANDARD CAPEX FLOW",
    levels: [
        { id: "l1", name: "Department Manager", hint: "Auto-assign based on requestor's department.", role: "ROLE" },
        { id: "l2", name: "Finance Manager", hint: "Requires 1 approval from Finance team.", role: "GROUP" },
        { id: "l3", name: "Operations Director", hint: "Final sign-off required for amounts > $50k.", role: "SPECIFIC USER" },
    ],
    ruleForm: {
        id: "CR-492",
        name: "Require Additional Level",
        rule_type: "approval_routing",
        criterion: "value",
        operator: ">",
        value: "50,000",
        priority: 10,
        active: true,
    },
};

export const MOCK_NOTIFICATIONS = {
    pending: [
        {
            id: "2023-0891",
            code: "REQ-2023-0891",
            name: "Mould Setup Variation Request - Line A",
            requester: "Sarah Jenkins",
            role: "Production Manager",
            department: "Production",
            priority: "High",
            date: "Oct 24, 09:15 AM",
            sla: "2h Remaining",
            slaTone: "we-sla-danger",
            comment: "Requesting variance for setup parameters on Line A to accommodate structural changes in batch #882. Current parameters will result in suboptimal curing times.",
            timeline: [
                { kind: "current", step: "Step 2", title: "Plant Manager Review", meta: "Assigned to: You", tag: "Current" },
                { kind: "done", step: "Step 1", title: "Line Supervisor Check", meta: "Oct 24, 10:05 AM", extra: "Approved by: David Kim" },
                { kind: "start", title: "Request Submitted", meta: "Oct 24, 09:15 AM" },
            ],
        },
        {
            id: "2023-0892",
            code: "REQ-2023-0892",
            name: "Quality Hold Release",
            requester: "Marcus Chen",
            role: "Quality Lead",
            department: "Quality",
            priority: "Medium",
            date: "Oct 24, 11:30 AM",
            sla: "1d Remaining",
            slaTone: "we-sla-warn",
            comment: "Quality hold release for inspected lot.",
        },
        {
            id: "2023-0895",
            code: "REQ-2023-0895",
            name: "Logistics Exception",
            requester: "Elena Rodriguez",
            role: "Logistics Coord",
            department: "Logistics",
            priority: "Medium",
            date: "Oct 23, 14:45 PM",
            sla: "3d Remaining",
            slaTone: "we-sla-ok",
            comment: "Delayed inbound shipment exception.",
        },
    ],
};

export const MOCK_TASKS = {
    slaBreaches: 3,
    pending: 24,
    tasks: [
        { id: "t1", name: "Approve Panel #402 Design", workflow: "Design Approval V2", assignee: "J. Smith", priority: "High", due: "Today, 14:00", dueDanger: true, state: "escalated", status: "Overdue" },
        { id: "t2", name: "Material Check: Steel Rebar", workflow: "Procurement Flow", assignee: "M. Johnson", priority: "Medium", due: "Oct 24, 09:00", dueDanger: false, state: "in_progress", status: "In Progress" },
        { id: "t3", name: "Quality Audit – Batch A", workflow: "QA Standard", assignee: "Team Alpha", priority: "Medium", due: "Oct 25, 12:00", dueDanger: false, state: "in_progress", status: "In Progress" },
        { id: "t4", name: "Final Sign-off Order #992", workflow: "Release Workflow", assignee: "S. Connor", priority: "High", due: "Oct 26, 17:00", dueDanger: false, state: "open", status: "Pending" },
    ],
    escalations: [
        { id: "e1", level: 2, name: "Design Approval V2 Overdue > 24h", time: "15m ago", note: "SLA Threshold exceeded for step Manager Review." },
        { id: "e2", level: 1, name: "Material Check Stalled", time: "2h ago", note: "Trigger: Task idle for 4 hours." },
    ],
    executions: [
        { id: "x1", name: "EXE-8832", module: "Production Order", started: "08:00 AM", step: "Mould Preparation", progress: 45, status: "Running", state: "running" },
        { id: "x2", name: "EXE-8831", module: "QA Sign-off", started: "Yesterday", step: "Final Report Gen", progress: 100, status: "Completed", state: "completed" },
    ],
};

export const MOCK_TEMPLATES = {
    stats: { total: 42, active: 31, draft: 7, mostUsed: "Purchase Approval" },
    records: [
        { id: "p1", name: "Purchase Approval", description: "Standard workflow for capex and opex", state: "active", steps: 5, icon: "fa-file-text-o" },
        { id: "p2", name: "Production Approval", description: "Multi-stage sign-off for new precast mold", state: "active", steps: 8, icon: "fa-share-alt" },
        { id: "p3", name: "Document Approval", description: "Review and approval routing for", state: "draft", steps: 3, icon: "fa-file-o" },
        { id: "p4", name: "Invoice Approval", description: "Automated routing for supplier invoices,", state: "active", steps: 4, icon: "fa-file-text-o" },
        { id: "p5", name: "Delivery Exception", description: "Escalation protocol for delayed logistical", state: "active", steps: 6, icon: "fa-exclamation-triangle", alert: true },
    ],
};

export const MOCK_ANALYTICS = {
    summary: {
        total_executions: 2842,
        completion_rate: 94.8,
        avg_duration_hours: 5.4,
        sla_compliance: 91,
    },
    bottlenecks: [
        { node_id: 1, node_name: "QC Inspection Approval", wait: "4h 12m", count: 80 },
        { node_id: 2, node_name: "Mould Release Sign-off", wait: "1h 45m", count: 40 },
        { node_id: 3, node_name: "Material Req Processing", wait: "0h 55m", count: 20 },
    ],
    by_module: [
        { module: "Production Floor", count: 1240 },
        { module: "Quality Control", count: 850 },
        { module: "Logistics", count: 450 },
    ],
};

export const MOCK_BUILDER = {
    title: "Purchase Approval Workflow",
    state: "draft",
    nodes: [
        { type: "start", typeLabel: "START", name: "PO Created", x: 80, y: 180 },
        { type: "conditional", typeLabel: "CONDITION", name: "Amount > 100k", x: 320, y: 168 },
    ],
};
