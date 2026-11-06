/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { MOCK_APPROVALS } from "../we_mockup";
import {
    CRITERIA, OPERATORS, RULE_TYPES, extractError, formatDate, statusClass, userLabel,
} from "../we_utils";

function emptyHierarchy() {
    return {
        id: null,
        name: "",
        description: "",
        priority: 10,
        source_module: "",
        active: true,
        date_from: "",
        date_to: "",
        levels: [{
            name: "Level 1",
            sequence: 10,
            mode: "sequential",
            threshold: 1,
            approver_user_ids: [],
            approver_group_ids: [],
            fallback_user_id: null,
        }],
    };
}

function emptyRule() {
    return {
        id: null,
        name: "",
        rule_type: "branch",
        criterion: "value",
        operator: "=",
        value: "",
        priority: 10,
        active: true,
    };
}

function toDateInput(value) {
    if (!value) {
        return "";
    }
    return String(value).slice(0, 10);
}

export class WeApprovals extends Component {
    static template = "workflow_engine.Approvals";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.RULE_TYPES = RULE_TYPES;
        this.CRITERIA = CRITERIA;
        this.OPERATORS = OPERATORS;
        this.state = useState({
            tab: "hierarchies",
            selectedHierarchyId: null,
            selectedRuleId: null,
            selectedLevels: [],
            loading: true,
            error: null,
            hierarchies: [],
            rules: [],
            users: [],
            groups: [],
            drawerOpen: false,
            drawerKind: "hierarchy",
            hierarchyForm: emptyHierarchy(),
            ruleForm: emptyRule(),
            saving: false,
        });
        onWillStart(() => this.load());
    }

    get canManage() {
        return !!(this.props.session?.is_manager || this.props.session?.is_admin);
    }

    get useMockup() {
        return !(this.state.hierarchies || []).length;
    }

    get selectedHierarchy() {
        if (this.useMockup) {
            return { id: "mock", name: MOCK_APPROVALS.hierarchyName };
        }
        return this.state.hierarchies.find((h) => h.id === this.state.selectedHierarchyId) || null;
    }

    get displayLevels() {
        if (this.useMockup) {
            return MOCK_APPROVALS.levels;
        }
        return this.state.selectedLevels || [];
    }

    get activeRuleCount() {
        if (this.useMockup) {
            return MOCK_APPROVALS.activeRules;
        }
        return (this.state.rules || []).filter((r) => r.active).length;
    }

    get conflictCount() {
        if (this.useMockup) {
            return MOCK_APPROVALS.conflicts;
        }
        const keys = {};
        let n = 0;
        for (const r of this.state.rules || []) {
            const k = `${r.criterion}|${r.operator}|${r.value}|${r.rule_type}`;
            keys[k] = (keys[k] || 0) + 1;
        }
        for (const v of Object.values(keys)) {
            if (v > 1) {
                n += v - 1;
            }
        }
        return n;
    }

    get expiringCount() {
        if (this.useMockup) {
            return MOCK_APPROVALS.expiring;
        }
        const now = Date.now();
        const soon = now + 30 * 24 * 3600 * 1000;
        return (this.state.hierarchies || []).filter((h) => {
            if (!h.date_to) {
                return false;
            }
            const t = new Date(String(h.date_to).replace(" ", "T")).getTime();
            return t >= now && t <= soon;
        }).length;
    }

    userName(id) {
        const rec = (this.state.users || []).find((u) => u.id === id);
        return rec ? rec.name : "User";
    }

    groupName(id) {
        const rec = (this.state.groups || []).find((g) => g.id === id);
        return rec ? (rec.full_name || rec.name) : "Group";
    }

    levelTitle(level, index) {
        return level.name || `Level ${index + 1}`;
    }

    levelRole(level) {
        if (level.role) {
            return level.role;
        }
        if ((level.approver_group_ids || []).length) {
            return "GROUP";
        }
        if ((level.approver_user_ids || []).length) {
            return "SPECIFIC USER";
        }
        return (level.mode || "ROLE").toUpperCase();
    }

    selectRule(rec) {
        this.state.selectedRuleId = rec?.id || null;
        this.state.ruleForm = rec ? {
            id: rec.id,
            name: rec.name || "",
            rule_type: rec.rule_type || "branch",
            criterion: rec.criterion || "value",
            operator: rec.operator || "=",
            value: rec.value || "",
            priority: rec.priority || 10,
            active: rec.active !== false,
        } : emptyRule();
    }

    resetRuleForm() {
        const current = (this.state.rules || []).find((r) => r.id === this.state.selectedRuleId);
        this.selectRule(current || null);
    }

    openHistory() {
        this.state.tab = "rules";
    }

    runDiagnostic() {
        this.notification.add(
            `Rule health: ${this.activeRuleCount} active, ${this.conflictCount} conflict(s).`,
            { type: "info" }
        );
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    async selectHierarchy(rec) {
        this.state.selectedHierarchyId = rec.id;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "get_hierarchy_detail",
                [rec.id]
            );
            this.state.selectedLevels = data.levels || [];
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("workflow.engine.ui.api", "get_approval_setup", []);
            this.state.hierarchies = data.hierarchies || [];
            this.state.rules = data.rules || [];
            this.state.users = data.users || [];
            this.state.groups = data.groups || [];
            if (this.state.rules.length) {
                const current = this.state.rules.find((r) => r.id === this.state.selectedRuleId) || this.state.rules[0];
                this.selectRule(current);
            } else {
                this.state.ruleForm = { ...MOCK_APPROVALS.ruleForm };
            }
            if (!this.state.selectedHierarchyId && this.state.hierarchies.length) {
                await this.selectHierarchy(this.state.hierarchies[0]);
            } else if (this.state.selectedHierarchyId) {
                const current = this.state.hierarchies.find((h) => h.id === this.state.selectedHierarchyId);
                if (current) {
                    await this.selectHierarchy(current);
                }
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    openHierarchyCreate() {
        if (!this.canManage) {
            return;
        }
        this.state.drawerKind = "hierarchy";
        this.state.hierarchyForm = emptyHierarchy();
        this.state.drawerOpen = true;
    }

    async openHierarchyEdit(rec) {
        if (!this.canManage) {
            return;
        }
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "get_hierarchy_detail",
                [rec.id]
            );
            const h = data.record;
            const levels = (data.levels || []).map((level) => ({
                id: level.id,
                name: level.name || "",
                sequence: level.sequence,
                mode: level.mode || "sequential",
                threshold: level.threshold || 1,
                approver_user_ids: level.approver_user_ids || [],
                approver_group_ids: level.approver_group_ids || [],
                fallback_user_id: level.fallback_user_id || null,
            }));
            this.state.hierarchyForm = {
                id: h.id,
                name: h.name || "",
                description: h.description || "",
                priority: h.priority || 10,
                source_module: h.source_module || "",
                active: h.active,
                date_from: toDateInput(h.date_from),
                date_to: toDateInput(h.date_to),
                levels: levels.length ? levels : emptyHierarchy().levels,
            };
            this.state.drawerKind = "hierarchy";
            this.state.drawerOpen = true;
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    openRuleCreate() {
        if (!this.canManage) {
            return;
        }
        this.state.tab = "rules";
        this.selectRule(null);
    }

    openRuleEdit(rec) {
        if (!this.canManage) {
            return;
        }
        this.state.ruleForm = {
            id: rec.id,
            name: rec.name || "",
            rule_type: rec.rule_type,
            criterion: rec.criterion,
            operator: rec.operator,
            value: rec.value || "",
            priority: rec.priority || 10,
            active: rec.active,
        };
        this.state.drawerKind = "rule";
        this.state.drawerOpen = true;
    }

    closeDrawer() {
        this.state.drawerOpen = false;
    }

    addLevel() {
        const levels = this.state.hierarchyForm.levels;
        const seq = (levels[levels.length - 1]?.sequence || 0) + 10;
        levels.push({
            name: `Level ${levels.length + 1}`,
            sequence: seq,
            mode: "sequential",
            threshold: 1,
            approver_user_ids: [],
            approver_group_ids: [],
            fallback_user_id: null,
        });
    }

    removeLevel(index) {
        if (this.state.hierarchyForm.levels.length <= 1) {
            return;
        }
        this.state.hierarchyForm.levels.splice(index, 1);
    }

    toggleApprover(level, userId) {
        const ids = level.approver_user_ids;
        const idx = ids.indexOf(userId);
        if (idx >= 0) {
            ids.splice(idx, 1);
        } else {
            ids.push(userId);
        }
    }

    toggleGroup(level, groupId) {
        const ids = level.approver_group_ids;
        const idx = ids.indexOf(groupId);
        if (idx >= 0) {
            ids.splice(idx, 1);
        } else {
            ids.push(groupId);
        }
    }

    setFallback(level, ev) {
        const value = ev.target.value;
        level.fallback_user_id = value ? Number(value) : null;
    }

    async saveHierarchy() {
        if (!this.canManage || this.state.saving) {
            return;
        }
        const f = this.state.hierarchyForm;
        if (!f.name.trim()) {
            this.notification.add("Hierarchy name is required.", { type: "danger" });
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("workflow.engine.ui.api", "save_hierarchy", [{
                id: f.id || false,
                name: f.name.trim(),
                description: f.description || false,
                priority: Number(f.priority) || 10,
                source_module: f.source_module || false,
                active: !!f.active,
                date_from: f.date_from || false,
                date_to: f.date_to || false,
                levels: (f.levels || []).map((level) => ({
                    name: level.name || false,
                    sequence: Number(level.sequence) || 10,
                    mode: level.mode || "sequential",
                    threshold: Number(level.threshold) || 1,
                    approver_user_ids: level.approver_user_ids || [],
                    approver_group_ids: level.approver_group_ids || [],
                    fallback_user_id: level.fallback_user_id || false,
                })),
            }]);
            this.state.drawerOpen = false;
            await this.load();
            this.notification.add("Hierarchy saved.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async saveRule() {
        if (!this.canManage || this.state.saving) {
            return;
        }
        const f = this.state.ruleForm;
        if (!f.name.trim() || !f.value.trim()) {
            this.notification.add("Name and value are required.", { type: "danger" });
            return;
        }
        this.state.saving = true;
        try {
            const vals = {
                name: f.name.trim(),
                rule_type: f.rule_type,
                criterion: f.criterion,
                operator: f.operator,
                value: f.value.trim(),
                priority: Number(f.priority) || 10,
                active: !!f.active,
            };
            await this.orm.call("workflow.engine.ui.api", "save_rule", [f.id || false, vals]);
            this.state.drawerOpen = false;
            await this.load();
            this.notification.add("Rule saved.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async toggleHierarchyActive(rec) {
        if (!this.canManage) {
            return;
        }
        try {
            await this.orm.call("workflow.engine.ui.api", "toggle_hierarchy_active", [rec.id]);
            await this.load();
            this.notification.add(rec.active ? "Hierarchy deactivated." : "Hierarchy activated.", {
                type: "success",
            });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    groupLabel(group) {
        return group.full_name || group.name || `Group #${group.id}`;
    }

    formatDate = formatDate;
    statusClass = statusClass;
    userLabel = userLabel;
}
