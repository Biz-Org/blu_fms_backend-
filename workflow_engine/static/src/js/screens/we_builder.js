/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { NODE_TYPES, extractError, statusClass, userLabel } from "../we_utils";

function uidKey() {
    return `tmp_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
}

function defaultNode(type, x, y, name) {
    const meta = NODE_TYPES.find((n) => n.id === type) || NODE_TYPES[2];
    const key = `${type}_${Math.floor(Math.random() * 100000)}`;
    return {
        client_key: uidKey(),
        id: false,
        name: name || meta.label,
        technical_key: key,
        node_type: type,
        sequence: 10,
        pos_x: x,
        pos_y: y,
        config_json: type === "action" ? { action: "noop" } : false,
        input_mapping: false,
        output_mapping: false,
        hierarchy_id: false,
        rule_id: false,
        mail_template_id: false,
    };
}

export class WeBuilder extends Component {
    static template = "workflow_engine.Builder";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");
        this.NODE_TYPES = NODE_TYPES;
        this.PALETTE = [
            { id: "start", label: "Trigger", icon: "fa-play-circle" },
            { id: "action", label: "Action", icon: "fa-bolt" },
            { id: "approval", label: "Approval", icon: "fa-check-square-o" },
            { id: "task", label: "Task", icon: "fa-tasks" },
            { id: "conditional", label: "Condition", icon: "fa-code-fork" },
            { id: "notification", label: "Notification", icon: "fa-bell-o" },
            { id: "action", label: "Delay", icon: "fa-clock-o", name: "Delay" },
            { id: "end", label: "End", icon: "fa-stop-circle" },
        ];
        this.state = useState({
            loading: true,
            busy: false,
            error: null,
            workflows: [],
            definitionId: null,
            versionId: null,
            definition: null,
            version: null,
            versions: [],
            nodes: [],
            edges: [],
            triggers: [],
            readonly: true,
            hierarchies: [],
            rules: [],
            selectedNodeKey: null,
            selectedEdgeKey: null,
            panel: "node", // node | trigger | validation
            validation: null,
            connectFrom: null,
            drag: null,
            defName: "",
            defDescription: "",
        });
        onWillStart(() => this.bootstrap());
    }

    get canManage() {
        return !!(this.props.session?.is_manager || this.props.session?.is_admin);
    }

    get canAdmin() {
        return !!this.props.session?.is_admin;
    }

    get selectedNode() {
        return this.state.nodes.find((n) => this.nodeKey(n) === this.state.selectedNodeKey) || null;
    }

    nodeKey(node) {
        return String(node.client_key || node.id);
    }

    nodeByRef(ref) {
        const key = String(Array.isArray(ref) ? ref[0] : ref);
        return this.state.nodes.find((n) => this.nodeKey(n) === key || String(n.id) === key);
    }

    statusClass = statusClass;
    userLabel = userLabel;

    async bootstrap() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const workflows = await this.orm.call("workflow.engine.ui.api", "list_workflows", []);
            this.state.workflows = workflows || [];
            if (workflows.length) {
                await this.loadWorkflow(workflows[0].id);
            } else {
                this.state.loading = false;
            }
        } catch (err) {
            this.state.error = extractError(err);
            this.state.loading = false;
        }
    }

    async loadWorkflow(definitionId, versionId = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "load_builder_graph",
                [definitionId, versionId]
            );
            this.applyGraph(data);
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    applyGraph(data) {
        this.state.definition = data.definition || null;
        this.state.version = data.version || null;
        this.state.versions = data.versions || [];
        this.state.definitionId = data.definition?.id || null;
        this.state.versionId = data.version?.id || null;
        this.state.readonly = !!data.readonly;
        this.state.hierarchies = data.hierarchies || [];
        this.state.rules = data.rules || [];
        this.state.defName = data.definition?.name || "";
        this.state.defDescription = data.definition?.description || "";
        this.state.nodes = (data.nodes || []).map((n) => ({
            ...n,
            client_key: String(n.id),
            hierarchy_id: Array.isArray(n.hierarchy_id) ? n.hierarchy_id[0] : n.hierarchy_id || false,
            rule_id: Array.isArray(n.rule_id) ? n.rule_id[0] : n.rule_id || false,
            mail_template_id: Array.isArray(n.mail_template_id)
                ? n.mail_template_id[0]
                : n.mail_template_id || false,
        }));
        this.state.edges = (data.edges || []).map((e) => ({
            ...e,
            client_key: String(e.id),
            source_ref: Array.isArray(e.source_node_id) ? e.source_node_id[0] : e.source_node_id,
            target_ref: Array.isArray(e.target_node_id) ? e.target_node_id[0] : e.target_node_id,
            rule_id: Array.isArray(e.rule_id) ? e.rule_id[0] : e.rule_id || false,
        }));
        this.state.triggers = (data.triggers || []).map((t) => ({ ...t, client_key: String(t.id) }));
        this.state.selectedNodeKey = null;
        this.state.selectedEdgeKey = null;
        this.state.validation = null;
        this.state.connectFrom = null;
    }

    async onSelectWorkflow(ev) {
        const id = Number(ev.target.value);
        if (id) {
            await this.loadWorkflow(id);
        }
    }

    async onSelectVersion(ev) {
        const id = Number(ev.target.value);
        if (id && this.state.definitionId) {
            await this.loadWorkflow(this.state.definitionId, id);
        }
    }

    async createWorkflow() {
        if (!this.canManage) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call("workflow.engine.ui.api", "create_workflow", [{
                name: "New Workflow",
            }]);
            const workflows = await this.orm.call("workflow.engine.ui.api", "list_workflows", []);
            this.state.workflows = workflows || [];
            this.applyGraph(data);
            this.notification.add("Draft workflow created.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
            this.state.loading = false;
        }
    }

    buildPayload() {
        return {
            definition: {
                name: this.state.defName,
                description: this.state.defDescription,
            },
            nodes: this.state.nodes.map((n, idx) => ({
                client_key: this.nodeKey(n),
                id: n.id || false,
                name: n.name,
                technical_key: n.technical_key,
                node_type: n.node_type,
                sequence: n.sequence || (idx + 1) * 10,
                pos_x: n.pos_x,
                pos_y: n.pos_y,
                config_json: n.config_json || false,
                input_mapping: n.input_mapping || false,
                output_mapping: n.output_mapping || false,
                hierarchy_id: n.hierarchy_id || false,
                rule_id: n.rule_id || false,
                mail_template_id: n.mail_template_id || false,
            })),
            edges: this.state.edges.map((e, idx) => ({
                name: e.name || false,
                source_ref: e.source_ref,
                target_ref: e.target_ref,
                sequence: e.sequence || (idx + 1) * 10,
                is_default: !!e.is_default,
                condition_json: e.condition_json || false,
                rule_id: e.rule_id || false,
            })),
            triggers: this.state.triggers.map((t) => ({
                name: t.name,
                source_module: t.source_module,
                source_model: t.source_model,
                event_code: t.event_code,
                domain_json: t.domain_json || false,
                active: t.active !== false,
                description: t.description || false,
            })),
        };
    }

    async save() {
        if (!this.canManage || this.state.readonly || !this.state.versionId) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "save_builder_graph",
                [this.state.definitionId, this.state.versionId, this.buildPayload()]
            );
            this.applyGraph(data);
            this.notification.add("Workflow saved.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async validate() {
        if (!this.state.versionId) {
            return;
        }
        this.state.busy = true;
        this.state.panel = "validation";
        try {
            const result = await this.orm.call(
                "workflow.engine.ui.api",
                "validate_version",
                [this.state.versionId]
            );
            this.state.validation = result;
            this.notification.add(result.ok ? "Validation passed." : "Validation found issues.", {
                type: result.ok ? "success" : "warning",
            });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async publish() {
        if (!this.canAdmin || !this.state.versionId) {
            return;
        }
        if (!confirm("Publish this draft version? It will become immutable.")) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "publish_version",
                [this.state.versionId]
            );
            const workflows = await this.orm.call("workflow.engine.ui.api", "list_workflows", []);
            this.state.workflows = workflows || [];
            this.applyGraph(data);
            this.notification.add("Workflow published.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async activate() {
        if (!this.canAdmin || !this.state.versionId) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "activate_version",
                [this.state.versionId]
            );
            this.applyGraph(data);
            this.notification.add("Workflow activated.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async deactivate() {
        if (!this.canAdmin || !this.state.versionId) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "deactivate_version",
                [this.state.versionId]
            );
            this.applyGraph(data);
            this.notification.add("Workflow deactivated.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async newDraft() {
        if (!this.canManage || !this.state.versionId) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "create_draft_from_version",
                [this.state.versionId]
            );
            this.applyGraph(data);
            this.notification.add("New draft version created.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async testRun() {
        if (!this.canManage || !this.state.versionId) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                "workflow.engine.ui.api",
                "test_run_version",
                [this.state.versionId, { we_test: true }]
            );
            this.notification.add(result.message || "Test run started.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    onPaletteDragStart(ev, type, name) {
        if (this.state.readonly || !this.canManage) {
            ev.preventDefault();
            return;
        }
        ev.dataTransfer.setData("text/we-node-type", type);
        ev.dataTransfer.setData("text/we-node-name", name || "");
        ev.dataTransfer.effectAllowed = "copy";
    }

    onCanvasDragOver(ev) {
        if (this.state.readonly) {
            return;
        }
        ev.preventDefault();
    }

    onCanvasDrop(ev) {
        if (this.state.readonly || !this.canManage) {
            return;
        }
        ev.preventDefault();
        const type = ev.dataTransfer.getData("text/we-node-type");
        if (!type) {
            return;
        }
        const name = ev.dataTransfer.getData("text/we-node-name");
        const rect = this.canvasRef.el.getBoundingClientRect();
        const x = ev.clientX - rect.left - 70;
        const y = ev.clientY - rect.top - 28;
        const node = defaultNode(type, Math.max(20, x), Math.max(20, y), name || undefined);
        this.state.nodes.push(node);
        this.state.selectedNodeKey = this.nodeKey(node);
        this.state.panel = "node";
    }

    selectNode(node, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        if (this.state.connectFrom) {
            const fromKey = this.state.connectFrom;
            const toKey = this.nodeKey(node);
            if (fromKey !== toKey && !this.state.readonly) {
                this.state.edges.push({
                    client_key: uidKey(),
                    name: "",
                    source_ref: fromKey,
                    target_ref: toKey,
                    sequence: (this.state.edges.length + 1) * 10,
                    is_default: false,
                    condition_json: false,
                    rule_id: false,
                });
            }
            this.state.connectFrom = null;
            return;
        }
        this.state.selectedNodeKey = this.nodeKey(node);
        this.state.selectedEdgeKey = null;
        this.state.panel = "node";
    }

    clearSelection() {
        this.state.selectedNodeKey = null;
        this.state.selectedEdgeKey = null;
        this.state.connectFrom = null;
    }

    startConnect(node, ev) {
        ev.stopPropagation();
        if (this.state.readonly || !this.canManage) {
            return;
        }
        this.state.connectFrom = this.nodeKey(node);
    }

    onNodeMouseDown(node, ev) {
        if (this.state.readonly || !this.canManage || ev.button !== 0) {
            return;
        }
        ev.stopPropagation();
        const startX = ev.clientX;
        const startY = ev.clientY;
        const origX = node.pos_x;
        const origY = node.pos_y;
        this.state.drag = { key: this.nodeKey(node), startX, startY, origX, origY };
        const onMove = (moveEv) => {
            if (!this.state.drag) {
                return;
            }
            const dx = moveEv.clientX - this.state.drag.startX;
            const dy = moveEv.clientY - this.state.drag.startY;
            const target = this.state.nodes.find((n) => this.nodeKey(n) === this.state.drag.key);
            if (target) {
                target.pos_x = Math.max(10, this.state.drag.origX + dx);
                target.pos_y = Math.max(10, this.state.drag.origY + dy);
            }
        };
        const onUp = () => {
            this.state.drag = null;
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseup", onUp);
        };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        this.selectNode(node);
    }

    deleteSelected() {
        if (this.state.readonly || !this.canManage) {
            return;
        }
        if (this.state.selectedNodeKey) {
            const key = this.state.selectedNodeKey;
            this.state.nodes = this.state.nodes.filter((n) => this.nodeKey(n) !== key);
            this.state.edges = this.state.edges.filter(
                (e) => String(e.source_ref) !== key && String(e.target_ref) !== key
            );
            this.state.selectedNodeKey = null;
        } else if (this.state.selectedEdgeKey) {
            this.state.edges = this.state.edges.filter((e) => e.client_key !== this.state.selectedEdgeKey);
            this.state.selectedEdgeKey = null;
        }
    }

    selectEdge(edge, ev) {
        ev.stopPropagation();
        this.state.selectedEdgeKey = edge.client_key;
        this.state.selectedNodeKey = null;
    }

    edgePath(edge) {
        const src = this.nodeByRef(edge.source_ref);
        const tgt = this.nodeByRef(edge.target_ref);
        if (!src || !tgt) {
            return "";
        }
        const width = 188;
        const midY = 29;
        const x1 = (src.pos_x || 0) + width;
        const y1 = (src.pos_y || 0) + midY;
        const x2 = (tgt.pos_x || 0) - 8;
        const y2 = (tgt.pos_y || 0) + midY;
        const mx = (x1 + x2) / 2;
        return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
    }

    nodeIcon(type) {
        return (NODE_TYPES.find((n) => n.id === type) || {}).icon || "fa-circle";
    }

    nodeTypeLabel(type) {
        const map = {
            start: "START",
            action: "ACTION",
            approval: "APPROVAL",
            task: "TASK",
            conditional: "CONDITION",
            notification: "NOTIFICATION",
            end: "END",
        };
        return map[type] || type;
    }

    updateSelectedField(field, ev) {
        const node = this.selectedNode;
        if (!node || this.state.readonly) {
            return;
        }
        let value = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        if (["hierarchy_id", "rule_id"].includes(field)) {
            value = value ? Number(value) : false;
        }
        if (field === "config_action") {
            node.config_json = { ...(node.config_json || {}), action: value };
            return;
        }
        node[field] = value;
    }

    addTrigger() {
        if (this.state.readonly || !this.canManage) {
            return;
        }
        this.state.triggers.push({
            client_key: uidKey(),
            name: "Manual Trigger",
            source_module: "workflow_engine",
            source_model: "workflow.engine.definition",
            event_code: "manual",
            active: true,
            description: "",
            domain_json: false,
        });
        this.state.panel = "trigger";
    }

    updateTrigger(trigger, field, ev) {
        if (this.state.readonly) {
            return;
        }
        const value = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        trigger[field] = value;
    }

    removeTrigger(trigger) {
        if (this.state.readonly || !this.canManage) {
            return;
        }
        this.state.triggers = this.state.triggers.filter((t) => t.client_key !== trigger.client_key);
    }

    setPanel(panel) {
        this.state.panel = panel;
    }
}
