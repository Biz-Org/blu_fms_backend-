/** @odoo-module **/

/**
 * Preventive Maintenance — consolidated OWL client (single JS file).
 * Sections: setup & services · state · data loaders · screens · actions · registry
 */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const SCREENS = {
    dashboard: "PM Dashboard",
    plans: "PM Plans",
    schedule: "PM Schedule & Calendar",
    tasks: "PM Tasks",
    workorders: "PM Work Orders",
    execution: "Work Order Execution",
    inspection: "Inspection",
    maint_requests: "Maintenance Requests",
    maint_request: "Maintenance Request",
    history: "PM History & Cost",
    completed: "My Completed Work",
    reports: "PM Reports & Analytics",
    config: "PM Configuration & Audit",
    users: "User Management",
};

const CONFIG_TABS = ["general", "notifications", "escalation", "sequences", "defaults", "templates"];

const REPORT_STATUS_KEYS = [
    "scheduled",
    "assigned",
    "in_progress",
    "on_hold",
    "pending_inspection",
    "rework",
    "completed",
    "skipped",
    "cancelled",
    "overdue",
];

export class PmApp extends Component {
    static template = "preventive_maintenance.PmApp";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            screen: "dashboard",
            title: SCREENS.dashboard,
            breadcrumbs: ["Home", "Dashboard"],
            loading: false,
            error: "",
            dashFull: null,
            dashAlerts: [],
            dashActivity: [],
            dashChartBars: [],
            planKpis: null,
            planFilterPriority: "",
            isManager: false,
            isAdmin: false,
            isTechnicianOnly: false,
            passwordResetRequired: false,
            // Dashboard
            kpiCards: [],
            dashSchedules: [],
            filters: { property_location: "" },
            // Plans
            plans: [],
            planSearch: "",
            selectedPlanId: null,
            planForm: null,
            // Schedule
            schedules: [],
            calMode: "month",
            calView: "calendar",
            calYear: new Date().getFullYear(),
            calMonth: new Date().getMonth(),
            calCells: [],
            calLabel: "",
            scheduleForm: null,
            taskKpis: null,
            tasks: [],
            taskForm: null,
            issueForm: null,
            maintRequests: [],
            maintRequestId: null,
            maintRequestDetail: null,
            historyKpis: null,
            reportsExt: {},
            configTabs: CONFIG_TABS,
            configTab: "general",
            configTabsData: null,
            // Work orders
            workOrders: [],
            woFilterState: "",
            // Execution
            execWoId: null,
            execDetail: null,
            canEditExecution: false,
            // History
            historyRows: [],
            // Reports
            reports: { by_status: {}, by_asset: {} },
            reportTotal: 0,
            reportMax: 0,
            repDateFrom: "",
            repDateTo: "",
            reportStatusKeys: REPORT_STATUS_KEYS,
            // Config
            configForm: null,
            auditRows: [],
            // User management (admin)
            pmUsers: [],
            userRoleFilter: "",
            userActiveOnly: true,
            userForm: null,
            inspectionQueue: [],
            // Options
            optionEquipment: [],
            optionTeams: [],
            optionUsers: [],
            optionTemplates: [],
            optionCategories: [],
            // Dialog
            dialog: null,
            dialogReason: "",
            dialogCallback: null,
        });

        onWillStart(async () => {
            await this._initAccess();
            await this._loadOptions();
            const p = this.props.action?.params || {};
            if (p.screen && SCREENS[p.screen]) {
                this.setScreen(p.screen);
            }
            if (p.workOrderId) {
                this.state.execWoId = p.workOrderId;
                this.setScreen("execution");
            }
            if (p.planId) {
                this.state.selectedPlanId = p.planId;
                this.setScreen("plans");
            }
            await this._refreshCurrent();
        });
    }

    // -------------------------------------------------------------------------
    // Access & options
    // -------------------------------------------------------------------------

    async _initAccess() {
        let manager = false;
        let technician = false;
        let admin = false;
        try {
            admin = Boolean(await user.hasGroup("preventive_maintenance.group_pm_admin"));
            manager =
                Boolean(await user.hasGroup("preventive_maintenance.group_pm_maintenance_manager")) ||
                Boolean(await user.hasGroup("preventive_maintenance.group_pm_manager"));
            technician = Boolean(await user.hasGroup("preventive_maintenance.group_pm_technician"));
            const session = await this.orm.call("pm.service", "get_session_access", []);
            this.state.isAdmin = Boolean(session.is_admin);
            this.state.isManager = Boolean(session.is_manager);
            this.state.isTechnicianOnly = Boolean(session.is_technician_only);
            this.state.passwordResetRequired = Boolean(session.password_reset_required);
        } catch (e) {
            console.error(e);
            this.state.error =
                e?.message || String(e) || "Could not verify your PM role. Try again or contact support.";
            this.notification.add(this.state.error, { type: "danger" });
            manager = false;
            technician = false;
            admin = false;
        }
        if (!this.state.isManager && !technician && !admin) {
            this.state.isManager = manager;
            this.state.isAdmin = admin;
            this.state.isTechnicianOnly = technician && !manager;
        }
        if (!this.state.isManager && !technician && !this.state.isAdmin) {
            this.state.error =
                this.state.error ||
                "Assign PM Administrator, Maintenance Manager, or Technician to use this app.";
        }
        if (this.state.isTechnicianOnly) {
            this.state.screen = "dashboard";
            this.state.title = SCREENS.dashboard;
        }
        if (this.state.passwordResetRequired) {
            this.notification.add(
                "Please change your password from your Odoo user preferences.",
                { type: "warning", sticky: true }
            );
        }
    }

    async _loadOptions() {
        if (!this.state.isManager) {
            return;
        }
        const opt = await this.orm.call("pm.service", "get_form_options", []);
        this.state.optionEquipment = opt.equipment;
        this.state.optionTeams = opt.teams;
        this.state.optionUsers = opt.users;
        this.state.optionTemplates = opt.templates;
        this.state.optionCategories = opt.categories;
    }

    // -------------------------------------------------------------------------
    // Navigation
    // -------------------------------------------------------------------------

    setScreen(name) {
        if (!SCREENS[name]) {
            return;
        }
        const managerScreens = [
            "plans",
            "schedule",
            "reports",
            "config",
            "inspection",
            "history",
            "tasks",
            "maint_requests",
            "maint_request",
        ];
        const techScreens = ["dashboard", "workorders", "execution", "completed", "tasks"];
        const adminScreens = ["users"];
        if (managerScreens.includes(name) && !this.state.isManager) {
            this.notification.add("Screen restricted to Maintenance Manager or Admin.", { type: "warning" });
            return;
        }
        if (this.state.isTechnicianOnly && !techScreens.includes(name)) {
            this.notification.add("This screen is not available for your role.", { type: "warning" });
            return;
        }
        if (adminScreens.includes(name) && !this.state.isAdmin) {
            this.notification.add("User Management is restricted to PM Administrators.", { type: "warning" });
            return;
        }
        this.state.screen = name;
        this.state.title = SCREENS[name];
        this.state.breadcrumbs = ["Home", SCREENS[name]];
        if (name === "maint_request" && this.state.maintRequestDetail?.name) {
            this.state.breadcrumbs.push(this.state.maintRequestDetail.name);
        }
        if (name === "users" && this.state.isTechnicianOnly) {
            this.state.title = "My Work Orders";
        } else if (name === "workorders" && this.state.isTechnicianOnly) {
            this.state.title = "My Work Orders";
        }
        this._refreshCurrent();
    }

    async _refreshCurrent() {
        const s = this.state.screen;
        this.state.loading = true;
        this.state.error = "";
        try {
            if (s === "dashboard") {
                await this.loadDashboard();
            } else if (s === "plans") {
                await this.loadPlans();
            } else if (s === "schedule") {
                await this.loadSchedules();
            } else if (s === "tasks") {
                await this.loadTasks();
            } else if (s === "maint_requests") {
                await this.loadMaintRequests();
            } else if (s === "maint_request") {
                await this.loadMaintRequestDetail();
            } else if (s === "workorders") {
                await this.loadWorkOrders();
            } else if (s === "execution") {
                await this.loadWorkOrders();
                await this.loadExecution();
            } else if (s === "history") {
                await this.loadHistory();
            } else if (s === "reports") {
                await this.loadReports();
            } else if (s === "config") {
                await this.loadConfig();
            } else if (s === "inspection") {
                await this.loadInspectionQueue();
            } else if (s === "completed") {
                await this.loadCompletedWork();
            } else if (s === "users") {
                await this.loadPmUsers();
            }
        } catch (e) {
            console.error(e);
            this.state.error = e.message || String(e);
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // -------------------------------------------------------------------------
    // Dashboard
    // -------------------------------------------------------------------------

    async loadDashboard() {
        const filters = {};
        if (this.state.filters.property_location) {
            filters.property_location = this.state.filters.property_location;
        }
        let k;
        try {
            const full = await this.orm.call("pm.service", "get_dashboard_full", [filters]);
            this.state.dashFull = full;
            this.state.dashAlerts = full.alerts || [];
            this.state.dashActivity = full.activity || [];
            const bars = full.charts?.wo_by_status || {};
            this.state.dashChartBars = Object.keys(bars).map((key) => ({
                key,
                label: key.replace(/_/g, " "),
                value: bars[key],
            }));
            k = full;
        } catch {
            k = await this.orm.call("pm.service", "get_dashboard_kpis", [filters]);
        }
        if (k.role === "technician" || this.state.isTechnicianOnly) {
            this.state.kpiCards = [
                { key: "ao", label: "Open assignments", value: k.assigned_open },
                { key: "ip", label: "In progress", value: k.in_progress },
                { key: "pi", label: "Awaiting inspection", value: k.pending_inspection },
                { key: "dn", label: "Completed today", value: k.completed_today },
            ];
            this.state.dashSchedules = [];
            return;
        }
        const costVal =
            k.total_cost_period !== undefined && k.total_cost_period !== null
                ? Number(k.total_cost_period).toFixed(2)
                : "";
        this.state.kpiCards = [
            { key: "ap", label: "Active PM plans", value: k.active_plans },
            { key: "dt", label: "Due today", value: k.due_today },
            { key: "dw", label: "Due this week", value: k.due_week },
            { key: "up", label: "Upcoming", value: k.upcoming },
            { key: "ov", label: "Overdue (sched)", value: k.overdue_schedules },
            { key: "ip", label: "In progress WO", value: k.wo_in_progress },
            { key: "dn", label: "Completed today", value: k.wo_completed_today },
            { key: "cp", label: "Compliance %", value: k.compliance_pct },
            { key: "cs", label: `Cost (${k.currency})`, value: costVal },
        ];
        this.state.dashSchedules = await this.orm.call("pm.service", "search_read_schedules", [
            [],
            ["id", "date_planned", "state", "plan_id"],
            12,
            0,
            "date_planned asc",
        ]);
    }

    // -------------------------------------------------------------------------
    // Plans
    // -------------------------------------------------------------------------

    async loadPlans() {
        if (this.state.isManager) {
            try {
                this.state.planKpis = await this.orm.call("pm.service", "get_plan_kpis", []);
            } catch {
                this.state.planKpis = null;
            }
        }
        let domain = this.state.planSearch
            ? ["|", ["name", "ilike", this.state.planSearch], ["reference", "ilike", this.state.planSearch]]
            : [];
        if (this.state.planFilterPriority) {
            domain = domain.length
                ? ["&", ...domain, ["priority", "=", this.state.planFilterPriority]]
                : [["priority", "=", this.state.planFilterPriority]];
        }
        this.state.plans = await this.orm.call("pm.service", "search_read_plans", [
            domain,
            [
                "id",
                "name",
                "reference",
                "equipment_id",
                "asset_category_id",
                "category_id",
                "state",
                "frequency_time",
                "start_date",
                "user_id",
                "team_id",
            ],
            80,
            0,
            "id desc",
        ]);
        if (this.state.selectedPlanId) {
            const found = this.state.plans.find((p) => p.id === this.state.selectedPlanId);
            if (!found) {
                this.state.selectedPlanId = null;
                this.state.planForm = null;
            }
        }
    }

    onPlanSearchKey(ev) {
        if (ev.key === "Enter") {
            this.loadPlans();
        }
    }

    async selectPlan(planId) {
        this.state.selectedPlanId = planId;
        const rows = await this.orm.read(
            "pm.plan",
            [planId],
            [
                "name",
                "equipment_id",
                "asset_category_id",
                "property_location",
                "team_id",
                "user_id",
                "maintenance_type",
                "frequency_basis",
                "frequency_time",
                "custom_interval_days",
                "meter_type",
                "meter_interval",
                "start_date",
                "end_date",
                "reminder_before_days",
                "duration_hours",
                "checklist_template_id",
                "auto_generate_work_orders",
                "auto_next_schedule",
                "mandatory_checklist",
                "instruction",
                "state",
                "priority",
                "supervisor_id",
            ]
        );
        const r = rows[0];
        this.state.planForm = {
            name: r.name,
            equipment_id: r.equipment_id ? r.equipment_id[0] : "",
            asset_category_id: r.asset_category_id ? r.asset_category_id[0] : "",
            property_location: r.property_location || "",
            team_id: r.team_id ? r.team_id[0] : "",
            user_id: r.user_id ? r.user_id[0] : "",
            maintenance_type: r.maintenance_type,
            frequency_basis: r.frequency_basis,
            frequency_time: r.frequency_time,
            custom_interval_days: r.custom_interval_days,
            meter_type: r.meter_type || "hours",
            meter_interval: r.meter_interval || 0,
            start_date: r.start_date || "",
            end_date: r.end_date || "",
            reminder_before_days: r.reminder_before_days,
            duration_hours: r.duration_hours,
            checklist_template_id: r.checklist_template_id ? r.checklist_template_id[0] : "",
            auto_generate_work_orders: r.auto_generate_work_orders,
            auto_next_schedule: r.auto_next_schedule,
            mandatory_checklist: r.mandatory_checklist,
            instruction: r.instruction,
            state: r.state,
            priority: r.priority || "1",
            supervisor_id: r.supervisor_id ? r.supervisor_id[0] : "",
        };
    }

    newPlan() {
        this.state.selectedPlanId = null;
        this.state.planForm = {
            name: "New PM Plan",
            equipment_id: "",
            asset_category_id: "",
            property_location: "",
            team_id: "",
            user_id: "",
            maintenance_type: "inspection",
            frequency_basis: "time",
            frequency_time: "monthly",
            custom_interval_days: 30,
            meter_type: "hours",
            meter_interval: 0,
            start_date: new Date().toISOString().slice(0, 10),
            end_date: "",
            reminder_before_days: 1,
            duration_hours: 2,
            checklist_template_id: "",
            auto_generate_work_orders: true,
            auto_next_schedule: true,
            mandatory_checklist: true,
            instruction: "",
            state: "draft",
            priority: "1",
            supervisor_id: "",
        };
    }

    async savePlan() {
        const f = this.state.planForm;
        if (!f) {
            return;
        }
        const vals = {
            name: f.name,
            equipment_id: f.equipment_id || false,
            asset_category_id: f.asset_category_id || false,
            property_location: f.property_location || false,
            team_id: f.team_id || false,
            user_id: f.user_id || false,
            maintenance_type: f.maintenance_type,
            frequency_basis: f.frequency_basis,
            frequency_time: f.frequency_time,
            custom_interval_days: f.custom_interval_days,
            meter_type: f.frequency_basis === "meter" ? f.meter_type : false,
            meter_interval: f.frequency_basis === "meter" ? f.meter_interval : false,
            start_date: f.start_date || false,
            end_date: f.end_date || false,
            reminder_before_days: f.reminder_before_days,
            duration_hours: f.duration_hours,
            checklist_template_id: f.checklist_template_id || false,
            auto_generate_work_orders: f.auto_generate_work_orders,
            auto_next_schedule: f.auto_next_schedule,
            mandatory_checklist: f.mandatory_checklist,
            instruction: f.instruction,
            priority: f.priority || "1",
            supervisor_id: f.supervisor_id || false,
        };
        if (this.state.selectedPlanId) {
            await this.orm.write("pm.plan", [this.state.selectedPlanId], vals);
            this.notification.add("Plan saved.", { type: "success" });
        } else {
            const newId = await this.orm.create("pm.plan", [vals]);
            this.state.selectedPlanId = newId;
            this.notification.add("Plan created.", { type: "success" });
        }
        await this.loadPlans();
    }

    async activatePlan() {
        if (!this.state.selectedPlanId) {
            return;
        }
        await this.orm.call("pm.plan", "action_activate", [[this.state.selectedPlanId]]);
        this.notification.add("Plan activated; schedules generated.", { type: "success" });
        await this.loadPlans();
        await this.selectPlan(this.state.selectedPlanId);
    }

    async deactivatePlan() {
        if (!this.state.selectedPlanId) {
            return;
        }
        await this.orm.call("pm.plan", "action_deactivate", [[this.state.selectedPlanId]]);
        this.notification.add("Plan deactivated.", { type: "info" });
        await this.loadPlans();
    }

    async duplicatePlan(planId) {
        const newId = await this.orm.call("pm.plan", "action_duplicate_plan", [[planId]]);
        this.notification.add("Plan duplicated.", { type: "success" });
        this.state.selectedPlanId = newId;
        await this.loadPlans();
        await this.selectPlan(newId);
    }

    // -------------------------------------------------------------------------
    // Schedule
    // -------------------------------------------------------------------------

    async loadSchedules() {
        if (this.state.isManager && !this.state.plans.length) {
            await this.loadPlans();
        }
        this.state.schedules = await this.orm.call("pm.service", "search_read_schedules", [
            [],
            [
                "id",
                "date_planned",
                "date_due",
                "equipment_id",
                "state",
                "work_order_id",
                "plan_id",
            ],
            500,
            0,
            "date_planned asc",
        ]);
        this._buildCalendar();
    }

    setCalMode(mode) {
        this.state.calMode = mode;
        this._buildCalendar();
    }

    calPrevMonth() {
        if (this.state.calMonth === 0) {
            this.state.calMonth = 11;
            this.state.calYear -= 1;
        } else {
            this.state.calMonth -= 1;
        }
        this._buildCalendar();
    }

    calNextMonth() {
        if (this.state.calMonth === 11) {
            this.state.calMonth = 0;
            this.state.calYear += 1;
        } else {
            this.state.calMonth += 1;
        }
        this._buildCalendar();
    }

    calToday() {
        const now = new Date();
        this.state.calYear = now.getFullYear();
        this.state.calMonth = now.getMonth();
        this._buildCalendar();
    }

    toggleScheduleView() {
        this.state.calView = this.state.calView === "calendar" ? "list" : "calendar";
    }

    openScheduleForm() {
        this.state.scheduleForm = {
            plan_id: "",
            equipment_id: "",
            date_planned: new Date().toISOString().slice(0, 10),
            create_work_order: true,
        };
    }

    async saveScheduleForm() {
        const f = this.state.scheduleForm;
        if (!f?.plan_id || !f.date_planned) {
            this.notification.add("Plan and date are required.", { type: "warning" });
            return;
        }
        let equipId = f.equipment_id ? parseInt(f.equipment_id, 10) : false;
        if (!equipId) {
            const prows = await this.orm.read("pm.plan", [parseInt(f.plan_id, 10)], ["equipment_id"]);
            equipId = prows[0]?.equipment_id ? prows[0].equipment_id[0] : false;
        }
        const conflict = await this.orm.call("pm.service", "check_schedule_conflict", [
            parseInt(f.plan_id, 10),
            equipId,
            f.date_planned,
        ]);
        if (conflict.has_conflict) {
            this.notification.add(conflict.message, { type: "danger" });
            return;
        }
        await this.orm.call("pm.service", "create_schedule", [
            {
                plan_id: parseInt(f.plan_id, 10),
                equipment_id: f.equipment_id ? parseInt(f.equipment_id, 10) : false,
                date_planned: f.date_planned,
                create_work_order: f.create_work_order,
            },
        ]);
        this.state.scheduleForm = null;
        this.notification.add("Schedule created.", { type: "success" });
        await this.loadSchedules();
    }

    _buildCalendar() {
        const y = this.state.calYear;
        const m = this.state.calMonth;
        const first = new Date(y, m, 1);
        const last = new Date(y, m + 1, 0);
        const startWeekday = first.getDay();
        const daysInMonth = last.getDate();
        this.state.calLabel = first.toLocaleString(undefined, { month: "long", year: "numeric" });
        const cells = [];
        const pad = (startWeekday + 6) % 7;
        for (let i = 0; i < pad; i++) {
            cells.push({ key: `p-${i}`, day: "", items: [] });
        }
        const byDay = {};
        for (const s of this.state.schedules) {
            if (!s.date_planned) {
                continue;
            }
            const d = s.date_planned;
            if (typeof d === "string" && d.startsWith(`${y}-${String(m + 1).padStart(2, "0")}`)) {
                const dayNum = parseInt(d.split("-")[2], 10);
                if (!byDay[dayNum]) {
                    byDay[dayNum] = [];
                }
                byDay[dayNum].push(s);
            }
        }
        for (let d = 1; d <= daysInMonth; d++) {
            cells.push({
                key: `d-${d}`,
                day: String(d),
                items: byDay[d] || [],
            });
        }
        this.state.calCells = cells;
    }

    async generateFromPlans() {
        await this.orm.call("pm.plan", "action_refresh_schedules", []);
        this.notification.add("Schedules refreshed from active plans.", { type: "success" });
        await this.loadSchedules();
    }

    promptReschedule(scheduleId) {
        this.state.dialog = {
            title: "Reschedule",
            body: "Enter new date (YYYY-MM-DD) in reason field below, or set dialog reason only.",
            askReason: true,
        };
        this.state.dialogReason = "";
        this.state.dialogCallback = async () => {
            const reason = this.state.dialogReason || "Rescheduled";
            const m = reason.match(/\d{4}-\d{2}-\d{2}/);
            const newDate = m ? m[0] : new Date().toISOString().slice(0, 10);
            await this.orm.call("pm.schedule", "action_reschedule", [[scheduleId], newDate, reason]);
            this.notification.add("Rescheduled.", { type: "success" });
            await this.loadSchedules();
        };
    }

    openExecution(woId) {
        this.state.execWoId = woId;
        this.setScreen("execution");
    }

    // -------------------------------------------------------------------------
    // Work orders
    // -------------------------------------------------------------------------

    async loadWorkOrders() {
        let domain = [];
        if (this.state.woFilterState) {
            domain = [["state", "=", this.state.woFilterState]];
        }
        this.state.workOrders = await this.orm.call("pm.service", "search_read_work_orders", [
            domain,
            [
                "id",
                "name",
                "equipment_id",
                "date_scheduled",
                "date_due",
                "user_id",
                "state",
                "duration_planned",
                "duration_actual",
                "total_cost",
                "corrective_request_id",
            ],
            120,
            0,
            "id desc",
        ]);
    }

    assignWoPrompt(woId) {
        this.state.dialog = { title: "Assign technician", body: "Enter user ID number in the reason field.", askReason: true };
        this.state.dialogReason = "";
        this.state.dialogCallback = async () => {
            const uid = parseInt(this.state.dialogReason, 10);
            if (!uid) {
                this.notification.add("Invalid user id.", { type: "danger" });
                return;
            }
            await this.orm.write("pm.work.order", [woId], { user_id: uid, state: "assigned" });
            this.notification.add("Assigned.", { type: "success" });
            await this.loadWorkOrders();
        };
    }

    async ormStartWo(woId) {
        await this.orm.call("pm.work.order", "action_start", [[woId]]);
        this.notification.add("Work started.", { type: "info" });
        await this.loadWorkOrders();
        if (this.state.execWoId === woId) {
            await this.loadExecution();
        }
    }

    promptSkipWo(woId) {
        this.state.dialog = { title: "Skip work order", body: "Provide a reason.", askReason: true };
        this.state.dialogReason = "";
        this.state.dialogCallback = async () => {
            await this.orm.call("pm.work.order", "action_skip", [[woId], this.state.dialogReason || "Skipped"]);
            this.notification.add("Skipped.", { type: "warning" });
            await this.loadWorkOrders();
        };
    }

    // -------------------------------------------------------------------------
    // Execution
    // -------------------------------------------------------------------------

    async loadExecution() {
        if (!this.state.execWoId) {
            this.state.execDetail = null;
            return;
        }
        this.state.execDetail = await this.orm.call("pm.service", "get_work_order_detail", [
            this.state.execWoId,
        ]);
        const wo = this.state.execDetail.work_order;
        const tech = wo.user_id && wo.user_id[0] === user.userId;
        const open = ["scheduled", "assigned", "in_progress", "on_hold", "rework"].includes(wo.state);
        this.state.canEditExecution =
            (this.state.isManager || (tech && open)) && wo.state !== "pending_inspection";
        this.state.canInspectWo =
            this.state.isManager && wo.state === "pending_inspection" && (!tech || !this.state.isTechnicianOnly);

        // Ensure checklist lines show current values in DOM
        for (const cl of this.state.execDetail.checklist) {
            cl.observation = cl.observation || "";
        }
    }

    async saveExecWo() {
        if (!this.state.execDetail) {
            return;
        }
        const wo = this.state.execDetail.work_order;
        await this.orm.write("pm.work.order", [wo.id], {
            work_performed: wo.work_performed,
            technician_remarks: wo.technician_remarks,
            meter_reading: wo.meter_reading,
        });
    }

    async updateChecklistResult(lineId, ev) {
        const val = ev.target.value || false;
        await this.orm.write("pm.checklist.result", [lineId], { result: val || false });
        await this.loadExecution();
    }

    setChecklistObs(lineId, ev) {
        const line = this.state.execDetail.checklist.find((c) => c.id === lineId);
        if (line) {
            line.observation = ev.target.value;
        }
    }

    async saveChecklistLine(cl) {
        await this.orm.write("pm.checklist.result", [cl.id], { observation: cl.observation || "" });
    }

    async submitInspection() {
        if (!this.state.execWoId) {
            return;
        }
        await this.orm.call("pm.work.order", "action_submit_inspection", [[this.state.execWoId]]);
        this.notification.add("Submitted for inspection.", { type: "success" });
        await this.loadExecution();
        await this.loadWorkOrders();
    }

    async approveInspection() {
        if (!this.state.execWoId) {
            return;
        }
        await this.orm.call("pm.work.order", "action_inspection_approve", [[this.state.execWoId]]);
        this.notification.add("Approved and next PM scheduled.", { type: "success" });
        await this.loadExecution();
        await this.loadWorkOrders();
    }

    rejectInspectionPrompt() {
        this.state.dialog = { title: "Reject inspection", body: "Remarks for technician:", askReason: true };
        this.state.dialogReason = "";
        this.state.dialogCallback = async () => {
            await this.orm.call("pm.work.order", "action_inspection_reject", [
                [this.state.execWoId],
                this.state.dialogReason || "Rejected",
            ]);
            this.notification.add("Sent for rework.", { type: "warning" });
            await this.loadExecution();
            await this.loadWorkOrders();
        };
    }

    clearDialog() {
        this.state.dialog = null;
        this.state.dialogReason = "";
        this.state.dialogCallback = null;
    }

    async confirmDialog() {
        const cb = this.state.dialogCallback;
        this.clearDialog();
        if (cb) {
            await cb();
        }
    }

    // -------------------------------------------------------------------------
    // History
    // -------------------------------------------------------------------------

    async loadTasks() {
        if (this.state.isManager && !this.state.plans.length) {
            await this.loadPlans();
        }
        this.state.taskKpis = await this.orm.call("pm.service", "get_task_kpis", []);
        let domain = [["state", "in", ["scheduled", "assigned", "in_progress", "on_hold", "rework", "overdue"]]];
        this.state.tasks = await this.orm.call("pm.service", "search_read_work_orders", [
            domain,
            ["id", "name", "equipment_id", "date_due", "user_id", "state", "priority"],
            120,
            0,
            "date_due asc",
        ]);
    }

    newTaskForm() {
        this.state.taskForm = {
            name: "",
            equipment_id: "",
            plan_id: "",
            user_id: "",
            date_scheduled: new Date().toISOString().slice(0, 10),
            date_due: new Date().toISOString().slice(0, 10),
        };
    }

    async saveTaskForm() {
        const f = this.state.taskForm;
        if (!f?.plan_id) {
            this.notification.add("Select a PM plan.", { type: "warning" });
            return;
        }
        const planRows = await this.orm.read("pm.plan", [parseInt(f.plan_id, 10)], ["equipment_id"]);
        const eq = f.equipment_id || (planRows[0].equipment_id ? planRows[0].equipment_id[0] : false);
        if (!eq) {
            this.notification.add("Equipment required.", { type: "warning" });
            return;
        }
        const plan = await this.orm.read("pm.plan", [parseInt(f.plan_id, 10)], ["id"]);
        await this.orm.call("pm.service", "create_schedule", [
            {
                plan_id: plan[0].id,
                equipment_id: eq,
                date_planned: f.date_scheduled,
                create_work_order: true,
            },
        ]);
        if (f.user_id) {
            const wos = await this.orm.call("pm.service", "search_read_work_orders", [
                [],
                ["id"],
                1,
                0,
                "id desc",
            ]);
            if (wos[0]) {
                await this.orm.write("pm.work.order", [wos[0].id], {
                    user_id: parseInt(f.user_id, 10),
                    state: "assigned",
                });
            }
        }
        this.state.taskForm = null;
        this.notification.add("Task created.", { type: "success" });
        await this.loadTasks();
    }

    openIssueForm(woId) {
        this.state.issueForm = {
            work_order_id: woId,
            name: "",
            issue_category: "other",
            severity: "medium",
            description: "",
        };
    }

    async submitIssueForm() {
        const f = this.state.issueForm;
        if (!f) {
            return;
        }
        await this.orm.call("pm.service", "report_issue", [f]);
        this.state.issueForm = null;
        this.notification.add("Issue reported.", { type: "success" });
    }

    async loadMaintRequests() {
        this.state.maintRequests = await this.orm.call("pm.service", "get_maintenance_requests", [[], 100]);
    }

    async openMaintRequest(reqId) {
        this.state.maintRequestId = reqId;
        this.setScreen("maint_request");
    }

    async loadMaintRequestDetail() {
        if (!this.state.maintRequestId) {
            this.state.maintRequestDetail = null;
            return;
        }
        this.state.maintRequestDetail = await this.orm.call("pm.service", "get_request_detail", [
            this.state.maintRequestId,
        ]);
        this.state.breadcrumbs = ["Home", SCREENS.maint_requests, this.state.maintRequestDetail.name];
    }

    async saveMaintRequestDetail() {
        const d = this.state.maintRequestDetail;
        if (!d) {
            return;
        }
        await this.orm.call("pm.service", "update_maintenance_request", [
            d.id,
            {
                description: d.description,
                severity: d.severity,
                issue_category: d.issue_category,
            },
        ]);
        this.notification.add("Request updated.", { type: "success" });
    }

    async saveReadingLine(lineId, ev) {
        await this.orm.write("pm.asset.reading.result", [lineId], { value: parseFloat(ev.target.value) || 0 });
        await this.loadExecution();
    }

    async loadHistory() {
        if (this.state.isManager) {
            this.state.historyKpis = await this.orm.call("pm.service", "get_history_kpis", [{}]);
        }
        this.state.historyRows = await this.orm.call("pm.service", "search_read_work_orders", [
            [
                "|",
                "|",
                "|",
                ["state", "=", "completed"],
                ["state", "=", "skipped"],
                ["state", "=", "cancelled"],
                ["state", "=", "overdue"],
            ],
            [
                "id",
                "name",
                "equipment_id",
                "date_scheduled",
                "state",
                "duration_planned",
                "duration_actual",
                "total_cost",
            ],
            200,
            0,
            "date_scheduled desc",
        ]);
    }

    async exportHistory() {
        const res = await this.orm.call("pm.service", "export_csv", [
            "pm.work.order",
            [],
            ["name", "equipment_id", "date_scheduled", "state", "total_cost", "duration_planned", "duration_actual"],
        ]);
        this._downloadCsv(res.filename, res.data);
        this.notification.add("Export ready.", { type: "success" });
    }

    _downloadCsv(filename, text) {
        const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    // -------------------------------------------------------------------------
    // Reports
    // -------------------------------------------------------------------------

    async loadReports() {
        const filters = {};
        if (this.state.repDateFrom) {
            filters.date_from = this.state.repDateFrom;
        }
        if (this.state.repDateTo) {
            filters.date_to = this.state.repDateTo;
        }
        let rep;
        try {
            rep = await this.orm.call("pm.service", "get_reports_extended", [filters]);
            this.state.reportsExt = {
                by_maintenance_type: rep.by_maintenance_type || {},
                by_month: rep.by_month || {},
                cost_total_completed: rep.cost_total_completed,
            };
        } catch {
            rep = await this.orm.call("pm.service", "get_reports", [filters]);
            this.state.reportsExt = {};
        }
        this.state.reports = rep;
        this.state.reportTotal = rep.total || 0;
        const bs = rep.by_status || {};
        let m = 0;
        for (const k of REPORT_STATUS_KEYS) {
            m = Math.max(m, bs[k] || 0);
        }
        this.state.reportMax = m;
    }

    // -------------------------------------------------------------------------
    // Config & audit
    // -------------------------------------------------------------------------

    async loadConfig() {
        try {
            this.state.configTabsData = await this.orm.call("pm.service", "get_config_tabs", []);
            this.state.configForm = { id: this.state.configTabsData.config_id, ...this.state.configTabsData.general };
        } catch {
            const cfg = await this.orm.call("pm.service", "get_configuration", []);
            this.state.configForm = cfg;
            this.state.configTabsData = null;
        }
        this.state.auditRows = await this.orm.call("pm.service", "search_read_audit_log", [[], 150]);
    }

    setConfigTab(tab) {
        this.state.configTab = tab;
    }

    async saveConfig() {
        if (this.state.configTabsData) {
            await this.orm.call("pm.service", "save_config_full", [
                {
                    general: this.state.configTabsData.general,
                    notifications: this.state.configTabsData.notifications,
                    escalation: this.state.configTabsData.escalation,
                    sequences: this.state.configTabsData.sequences,
                    defaults: this.state.configTabsData.defaults,
                },
            ]);
            this.notification.add("Configuration saved.", { type: "success" });
            await this.loadConfig();
            return;
        }
        if (!this.state.configForm?.id) {
            return;
        }
        await this.orm.write("pm.configuration", [this.state.configForm.id], {
            default_lead_days: this.state.configForm.default_lead_days,
            default_task_duration: this.state.configForm.default_task_duration,
            reminder_days: this.state.configForm.reminder_days,
            escalation_overdue_days: this.state.configForm.escalation_overdue_days,
        });
        this.notification.add("Configuration saved.", { type: "success" });
    }

    // -------------------------------------------------------------------------
    // Inspection queue (manager / admin)
    // -------------------------------------------------------------------------

    async loadInspectionQueue() {
        this.state.inspectionQueue = await this.orm.call("pm.service", "search_read_inspection_queue", [80]);
    }

    openInspectionWo(woId) {
        this.state.execWoId = woId;
        this.setScreen("execution");
    }

    async approveInspectionWo(woId) {
        await this.orm.call("pm.work.order", "action_inspection_approve", [[woId]]);
        this.notification.add("Work order approved and closed.", { type: "success" });
        await this.loadInspectionQueue();
        if (this.state.execWoId === woId) {
            await this.loadExecution();
        }
    }

    rejectInspectionWoPrompt(woId) {
        this.state.dialog = { title: "Reject inspection", body: "Remarks for technician:", askReason: true };
        this.state.dialogReason = "";
        this.state.dialogCallback = async () => {
            await this.orm.call("pm.work.order", "action_inspection_reject", [
                [woId],
                this.state.dialogReason || "Rejected",
            ]);
            this.notification.add("Sent for rework.", { type: "warning" });
            await this.loadInspectionQueue();
        };
    }

    // -------------------------------------------------------------------------
    // Technician completed work
    // -------------------------------------------------------------------------

    async loadCompletedWork() {
        this.state.historyRows = await this.orm.call("pm.service", "search_read_work_orders", [
            [["state", "=", "completed"]],
            ["id", "name", "equipment_id", "date_scheduled", "state", "duration_actual", "total_cost"],
            200,
            0,
            "date_scheduled desc",
        ]);
    }

    // -------------------------------------------------------------------------
    // User management (admin)
    // -------------------------------------------------------------------------

    async loadPmUsers() {
        this.state.pmUsers = await this.orm.call("pm.service", "search_read_pm_users", [
            this.state.userRoleFilter || null,
            this.state.userActiveOnly,
        ]);
    }

    newPmUser() {
        this.state.userForm = {
            id: null,
            name: "",
            login: "",
            email: "",
            password: "",
            role: "technician",
            active: true,
        };
    }

    editPmUser(row) {
        this.state.userForm = {
            id: row.id,
            name: row.name,
            login: row.login,
            email: row.email || "",
            password: "",
            role: row.role === "admin" ? "manager" : row.role || "technician",
            active: row.active,
            readOnlyRole: row.role === "admin",
        };
    }

    clearUserForm() {
        this.state.userForm = null;
    }

    async savePmUser() {
        const f = this.state.userForm;
        if (!f) {
            return;
        }
        try {
            if (f.id) {
                await this.orm.call("pm.service", "update_pm_user", [
                    f.id,
                    {
                        name: f.name,
                        email: f.email,
                        active: f.active,
                        role: f.readOnlyRole ? null : f.role,
                        password: f.password || null,
                    },
                ]);
                this.notification.add("User updated.", { type: "success" });
            } else {
                await this.orm.call("pm.service", "create_pm_user", [
                    {
                        name: f.name,
                        login: f.login,
                        email: f.email,
                        password: f.password,
                        role: f.role,
                        active: f.active,
                    },
                ]);
                this.notification.add("User created.", { type: "success" });
            }
            this.state.userForm = null;
            await this.loadPmUsers();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }
}

PmApp.props = {
    action: { type: Object, optional: true },
};

registry.category("actions").add("preventive_maintenance_pm_app", PmApp);
