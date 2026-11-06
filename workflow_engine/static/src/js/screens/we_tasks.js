/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, formatDate, formatRelative, priorityLabel, statusClass, userLabel } from "../we_utils";
import { MOCK_TASKS } from "../we_mockup";

export class WeTasks extends Component {
    static template = "workflow_engine.Tasks";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
        search: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            tab: "executions",
            taskFilter: "active",
            search: "",
            loading: true,
            error: null,
            executions: [],
            tasks: [],
            escalationEvents: [],
            users: [],
            drawerOpen: false,
            detail: null,
            steps: [],
            escalations: [],
            assignUserId: null,
            busy: false,
        });
        onWillStart(() => this.load());
    }

    get canManage() {
        return !!(this.props.session?.is_manager || this.props.session?.is_admin);
    }

    get uid() {
        return this.props.session?.uid;
    }

    setTaskFilter(filter) {
        this.state.taskFilter = filter;
        this.closeDrawer();
    }

    createTaskHint() {
        this.notification.add("Tasks are created when a workflow execution reaches a task node.", { type: "info" });
    }

    isOverdue(task) {
        if (!task?.date_deadline || ["done"].includes(task.state)) {
            return false;
        }
        const raw = String(task.date_deadline).replace(" ", "T");
        const date = new Date(raw.endsWith("Z") || raw.includes("+") ? raw : `${raw}Z`);
        return date.getTime() < Date.now() && ["open", "in_progress", "escalated"].includes(task.state);
    }

    get useMockup() {
        return !(this.state.tasks || []).length && !(this.state.executions || []).length;
    }

    get filteredTasks() {
        const q = (this.props.search || this.state.search || "").trim().toLowerCase();
        if (this.useMockup) {
            return MOCK_TASKS.tasks.filter((task) => {
                if (this.state.taskFilter === "completed") {
                    return false;
                }
                if (this.state.taskFilter === "overdue") {
                    return task.dueDanger;
                }
                if (!q) {
                    return true;
                }
                return (task.name || "").toLowerCase().includes(q);
            });
        }
        return (this.state.tasks || []).filter((task) => {
            if (this.state.taskFilter === "completed" && task.state !== "done") {
                return false;
            }
            if (this.state.taskFilter === "overdue" && !this.isOverdue(task)) {
                return false;
            }
            if (this.state.taskFilter === "active" && !["open", "in_progress", "escalated"].includes(task.state)) {
                return false;
            }
            if (!q) {
                return true;
            }
            return (task.name || "").toLowerCase().includes(q) || userLabel(task.user_id).toLowerCase().includes(q);
        });
    }

    get slaBreaches() {
        if (this.useMockup) {
            return MOCK_TASKS.slaBreaches;
        }
        return (this.state.tasks || []).filter((t) => this.isOverdue(t)).length;
    }

    get pendingCount() {
        if (this.useMockup) {
            return MOCK_TASKS.pending;
        }
        return (this.state.tasks || []).filter((t) => ["open", "in_progress"].includes(t.state)).length;
    }

    escalationLevel(ev) {
        return parseInt(ev?.level, 10) || 0;
    }

    isLevelOne(ev) {
        return this.escalationLevel(ev) === 1;
    }

    isLevelTwoPlus(ev) {
        return this.escalationLevel(ev) >= 2;
    }

    get openEscalations() {
        if (this.useMockup) {
            return MOCK_TASKS.escalations;
        }
        return (this.state.escalationEvents || []).filter((e) => ["triggered", "notified"].includes(e.state)).slice(0, 4);
    }

    get displayExecutions() {
        return this.useMockup ? MOCK_TASKS.executions : this.state.executions;
    }

    progressWidth(rec) {
        if (rec.progress != null) {
            return `${rec.progress}%`;
        }
        if (rec.state === "completed") {
            return "100%";
        }
        if (rec.state === "failed") {
            return "100%";
        }
        if (rec.state === "escalated") {
            return "70%";
        }
        if (["waiting_approval", "waiting_task"].includes(rec.state)) {
            return "45%";
        }
        return "25%";
    }

    priorityClass(priority) {
        const key = String(priority);
        if (key === "High" || key === "2" || key === "3" || key === "escalated") {
            return "we-badge-danger";
        }
        if (key === "Medium" || key === "1") {
            return "we-badge-warning";
        }
        return "we-badge-muted";
    }

    async openTaskFromEscalation(ev) {
        const taskId = Array.isArray(ev.task_id) ? ev.task_id[0] : ev.task_id;
        const rec = (this.state.tasks || []).find((t) => t.id === taskId) || this.filteredTasks[0];
        if (rec) {
            await this.openTask(rec);
        }
    }

    setTab(tab) {
        this.state.tab = tab;
        this.closeDrawer();
    }

    canComplete(task) {
        if (this.canManage) {
            return ["open", "in_progress", "escalated"].includes(task.state);
        }
        const assigneeId = Array.isArray(task.user_id) ? task.user_id[0] : task.user_id;
        return assigneeId === this.uid && ["open", "in_progress", "escalated"].includes(task.state);
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [executions, tasks, escalationEvents, users] = await Promise.all([
                this.orm.call("workflow.engine.ui.api", "search_executions", [[], 0, 100]),
                this.orm.call("workflow.engine.ui.api", "search_tasks", [[], 0, 100]),
                this.orm.call("workflow.engine.ui.api", "search_escalations", [[], 0, 100]),
                this.orm.searchRead(
                    "res.users",
                    [["active", "=", true], ["share", "=", false]],
                    ["id", "name"],
                    { order: "name", limit: 300 }
                ),
            ]);
            this.state.executions = executions.records || [];
            this.state.tasks = tasks.records || [];
            this.state.escalationEvents = escalationEvents.records || [];
            this.state.users = users;
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    async openExecution(rec) {
        if (typeof rec.id === "string") {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "workflow.engine.ui.api",
                "get_execution_detail",
                [rec.id]
            );
            this.state.detail = { kind: "execution", record: data.record };
            this.state.steps = data.steps || [];
            this.state.escalations = data.escalations || [];
            this.state.drawerOpen = true;
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async openTask(rec) {
        if (typeof rec.id === "string") {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call("workflow.engine.ui.api", "get_task_detail", [rec.id]);
            const full = data.record;
            this.state.detail = { kind: "task", record: full };
            this.state.steps = [];
            this.state.escalations = data.escalations || [];
            this.state.assignUserId = Array.isArray(full.user_id)
                ? String(full.user_id[0])
                : full.user_id
                    ? String(full.user_id)
                    : "";
            this.state.drawerOpen = true;
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeDrawer() {
        this.state.drawerOpen = false;
        this.state.detail = null;
    }

    async retryExecution() {
        if (!this.canManage || !this.state.detail?.record || this.state.detail.kind !== "execution" || this.state.busy) {
            return;
        }
        const rec = this.state.detail.record;
        if (rec.state !== "failed") {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("workflow.engine.ui.api", "retry_execution", [rec.id]);
            this.notification.add("Execution retried.", { type: "success" });
            await this.load();
            await this.openExecution(rec);
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async assignTask() {
        if (!this.canManage || !this.state.detail?.record || this.state.detail.kind !== "task" || this.state.busy) {
            return;
        }
        const rec = this.state.detail.record;
        const raw = this.state.assignUserId;
        const userId = raw ? Number(raw) : false;
        if (userId === false) {
            this.notification.add("Select a user to assign.", { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("workflow.engine.ui.api", "assign_task", [rec.id, userId]);
            this.notification.add("Task assigned.", { type: "success" });
            await this.load();
            await this.openTask(rec);
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async completeTask(rec) {
        if (!this.canComplete(rec) || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("workflow.engine.ui.api", "complete_task", [rec.id]);
            this.notification.add("Task completed.", { type: "success" });
            await this.load();
            if (this.state.detail?.kind === "task" && this.state.detail.record.id === rec.id) {
                await this.openTask(rec);
            }
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async escalateTask(rec) {
        if (!this.canManage || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("workflow.engine.ui.api", "escalate_task", [rec.id]);
            this.notification.add("Execution escalated.", { type: "success" });
            await this.load();
            if (this.state.detail?.kind === "task") {
                await this.openTask(rec);
            }
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    formatDate = formatDate;
    formatRelative = formatRelative;
    priorityLabel = priorityLabel;
    statusClass = statusClass;
    userLabel = userLabel;
}
