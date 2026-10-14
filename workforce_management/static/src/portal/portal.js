/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NAV = [
    { id: "overview", label: "Workforce Overview", icon: "fa-th-large" },
    { id: "employees", label: "Employee Master", icon: "fa-id-badge" },
    { id: "technicians", label: "Technician Profiles", icon: "fa-wrench" },
    { id: "shifts", label: "Shift Scheduling", icon: "fa-clock-o" },
    { id: "roster", label: "Roster Management", icon: "fa-calendar" },
    { id: "attendance", label: "Attendance", icon: "fa-check-square-o" },
    { id: "leave", label: "Leave Management", icon: "fa-plane" },
    { id: "skills", label: "Skill Management", icon: "fa-graduation-cap" },
    { id: "tasks", label: "Task Distribution", icon: "fa-tasks" },
    { id: "allocation", label: "Technician Allocation", icon: "fa-users" },
    { id: "reports", label: "Productivity Reports", icon: "fa-line-chart" },
];

export class WorkforcePortal extends Component {
    static template = "workforce_management.Portal";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.navItems = NAV;
        this.state = useState({
            page: "overview",
            loading: true,
            saving: false,
            data: {},
            search: "",
            filters: { department: "", site: "", status: "", search: "" },
            show: "",
            selectedTech: 0,
            selectedTask: 0,
            employee: { name: "", department: "Maintenance", designation: "", site: "North Wing", status: "active" },
            technician: { name: "", trade: "HVAC", skills: "", site: "North Wing", shift_name: "Morning", experience: "1 yr" },
            shift: { name: "", site: "North Campus", department: "Maintenance", time_label: "08:00 - 16:00", capacity: 4 },
            leave: { employee_id: "", leave_type: "Annual Leave", date_from: "", date_to: "", reason: "" },
            skill: { name: "", category: "Electrical", staff_count: 1, technician_count: 1, proficiency: 60, certification: "" },
            task: { name: "", location: "", site: "North Wing", priority: "medium", required_skill: "HVAC" },
        });
        onWillStart(() => this.load());
    }

    async load() {
        const first = !this.state.data.employees;
        if (first) this.state.loading = true;
        try {
            const data = await this.orm.call("wf.portal", "get_dashboard_data", [this.state.filters]);
            this.state.data = data;
            const pending = (data.allocation && data.allocation.pending) || [];
            const techs = (data.allocation && data.allocation.techs) || [];
            if (!this.state.selectedTask && pending.length) this.state.selectedTask = pending[0].id;
            if (!this.state.selectedTech && techs.length) this.state.selectedTech = techs[0].id;
        } catch (error) {
            this.notification.add(error?.data?.message || "Could not load workforce data.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async call(method, args) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("wf.portal", method, args);
            this.state.show = "";
            this.notification.add("Saved.", { type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onNav(id) {
        this.state.page = id;
        this.state.search = "";
        this.state.show = "";
    }

    pageTitle() {
        return (NAV.find((item) => item.id === this.state.page) || NAV[0]).label;
    }

    kpis() { return this.state.data.kpis || {}; }
    force() { return this.state.data.force || {}; }
    employees() { return this.visible(this.state.data.employees || []); }
    technicians() { return this.visible(this.state.data.technicians || []); }
    matches(row) {
        const query = (this.state.search || "").trim().toLowerCase();
        if (!query) return true;
        return JSON.stringify(row).toLowerCase().includes(query);
    }
    visible(rows) { return (rows || []).filter((row) => this.matches(row)); }

    async applyFilters() {
        this.state.filters.search = this.state.search;
        await this.load();
    }

    async saveEmployee() {
        await this.call("add_employee", [{ ...this.state.employee, filters: this.state.filters }]);
    }
    async saveTechnician() {
        await this.call("add_technician", [{ ...this.state.technician, filters: this.state.filters }]);
    }
    async saveShift() {
        await this.call("add_shift", [{ ...this.state.shift, filters: this.state.filters }]);
    }
    async publishRoster() {
        await this.call("publish_roster", [this.state.filters]);
    }
    async markAttendance(id, status) {
        await this.call("set_attendance", [id, status, this.state.filters]);
    }
    async saveLeave() {
        await this.call("add_leave", [{ ...this.state.leave, filters: this.state.filters }]);
    }
    async reviewLeave(id, status) {
        await this.call("review_leave", [id, status, this.state.filters]);
    }
    async saveSkill() {
        await this.call("add_skill", [{ ...this.state.skill, filters: this.state.filters }]);
    }
    async saveTask() {
        await this.call("add_task", [{ ...this.state.task, filters: this.state.filters }]);
    }
    async assignSelected() {
        if (!this.state.selectedTask || !this.state.selectedTech) {
            this.notification.add("Select a technician and a pending task.", { type: "warning" });
            return;
        }
        await this.call("assign_task", [this.state.selectedTask, this.state.selectedTech, this.state.filters]);
    }
    async autoAssign() {
        await this.call("auto_assign", [this.state.filters]);
    }
    async resolveAlert(id) {
        await this.call("resolve_alert", [id, this.state.filters]);
    }
    async download(kind) {
        const file = await this.orm.call("wf.portal", "report_file", [kind, this.state.filters]);
        const blob = new Blob([file.content], { type: "text/csv;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = file.filename;
        link.click();
        URL.revokeObjectURL(link.href);
    }
    linePoints(series) {
        const rows = series || [];
        if (!rows.length) return "";
        const max = Math.max(...rows.map((row) => row.value || row.pct || 0), 1);
        return rows.map((row, index) => {
            const x = rows.length === 1 ? 160 : (index / (rows.length - 1)) * 320;
            const y = 90 - ((row.value || 0) / max) * 70;
            return `${x},${y}`;
        }).join(" ");
    }
}

registry.category("actions").add("workforce_management.portal", WorkforcePortal);
