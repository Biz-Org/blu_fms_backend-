import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { FsAppShell, FS_NAV } from "@fire_safety_management/owl/ui/fs_shell";
import { FS_COMPONENTS } from "@fire_safety_management/owl/ui/fs_ui";

export class FireSafetyDashboard extends Component {
    static template = "fire_safety_management.Dashboard";
    static components = { FsAppShell, ...FS_COMPONENTS };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            isSafetyManager: false,
            isSecurity: false,
            isGuard: false,
            isReadOnly: false,
        });
        onWillStart(async () => {
            const [isSafetyManager, isSecurity, isGuard, isFacility, isAuditor, isExecutive] = await Promise.all([
                user.hasGroup("fire_safety_management.group_fire_safety_manager"),
                user.hasGroup("fire_safety_management.group_fire_safety_security"),
                user.hasGroup("fire_safety_management.group_fire_safety_guard"),
                user.hasGroup("fire_safety_management.group_fire_safety_facility"),
                user.hasGroup("fire_safety_management.group_fire_safety_auditor"),
                user.hasGroup("fire_safety_management.group_fire_safety_executive"),
            ]);
            this.state.isSafetyManager = isSafetyManager;
            this.state.isSecurity = isSecurity;
            this.state.isGuard = isGuard && !isSafetyManager && !isSecurity;
            this.state.isReadOnly = !isSafetyManager && !isSecurity && !this.state.isGuard
                && (isFacility || isAuditor || isExecutive);
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("fire.safety.dashboard", "get_dashboard_data", []);
        } catch (error) {
            this.state.data = null;
            this.state.error = error?.data?.message || error?.message || "Could not load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || {
            compliance: false,
            inspection_counts: {},
            incident_counts: {},
            drill_counts: {},
            equipment_counts: {},
            emergency_counts: {},
            open_actions: 0,
            overdue_inspections: 0,
            recent_inspections: [],
            recent_incidents: [],
            upcoming_drills: [],
        };
    }

    sumCounts(counts) {
        return Object.values(counts || {}).reduce((total, value) => total + (value || 0), 0);
    }

    countOf(counts, keys) {
        return keys.reduce((total, key) => total + (counts?.[key] || 0), 0);
    }

    get inspectionTotal() {
        return this.sumCounts(this.data.inspection_counts);
    }

    get openInspections() {
        return this.countOf(this.data.inspection_counts, ["scheduled", "in_progress", "pending"]);
    }

    get openIncidents() {
        return this.countOf(this.data.incident_counts, ["open", "investigating"]);
    }

    get equipmentDue() {
        return this.countOf(this.data.equipment_counts, ["inspection_due", "service_due", "expired"]);
    }

    get scheduledDrills() {
        return this.countOf(this.data.drill_counts, ["scheduled", "rescheduled"]);
    }

    get activeEmergencies() {
        return this.data.emergency_counts?.active || 0;
    }

    get complianceValue() {
        const compliance = this.data.compliance;
        if (!compliance) {
            return "—";
        }
        return `${compliance.compliance}%`;
    }

    get complianceHint() {
        const compliance = this.data.compliance;
        if (!compliance) {
            return "Not available for this role";
        }
        return `Target ${compliance.target}%`;
    }

    get canCreateInspection() {
        return this.state.isSafetyManager;
    }

    get canReportIncident() {
        return this.state.isSafetyManager || this.state.isSecurity || this.state.isGuard;
    }

    get canActivateEmergency() {
        return this.state.isSafetyManager || this.state.isSecurity;
    }

    get canCreateDrill() {
        return this.state.isSafetyManager;
    }

    get canCreateEquipment() {
        return this.state.isSafetyManager;
    }

    get showInspectionKpis() {
        return !this.state.isGuard;
    }

    get showEquipmentKpis() {
        return !this.state.isGuard;
    }

    get showDrillKpis() {
        return !this.state.isGuard;
    }

    openNav(tag, name) {
        const item = FS_NAV.find((entry) => entry.tag === tag);
        this.action.doAction(item?.xmlid || tag, { clearBreadcrumbs: true, forceLeave: true });
    }

    openNative(xmlid) {
        this.action.doAction(xmlid);
    }

    openCreateInspection() {
        this.action.doAction("fire_safety_management.action_fs_inspection_create_ui", {
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    openReportIncident() {
        this.action.doAction("fire_safety_management.action_fs_incident_report_ui", {
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    openScheduleDrill() {
        this.action.doAction("fire_safety_management.action_fs_drill_create_ui", {
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    openCreateEquipment() {
        this.action.doAction("fire_safety_management.action_fs_equipment_create_ui", {
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    openActivateEmergency() {
        this.action.doAction("fire_safety_management.action_fs_emergency_activate_ui", {
            clearBreadcrumbs: true,
            forceLeave: true,
        });
    }

    get recentIncidents() {
        return this.data.recent_incidents || [];
    }

    get upcomingDrills() {
        return this.data.upcoming_drills || [];
    }

    get inspectionRows() {
        return Object.entries(this.data.inspection_counts || {}).map(([state, count]) => ({ state, count }));
    }

    get equipmentRows() {
        return Object.entries(this.data.equipment_counts || {}).map(([state, count]) => ({ state, count }));
    }

    formatWhen(value) {
        if (!value) {
            return "";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleString();
    }
}

registry.category("actions").add("fire_safety_management.action_dashboard", FireSafetyDashboard);
