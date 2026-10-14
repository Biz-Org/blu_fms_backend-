from odoo import fields, models


class WfEmployee(models.Model):
    _name = "wf.employee"
    _description = "Workforce Employee"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    department = fields.Char()
    designation = fields.Char()
    site = fields.Char()
    status = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")],
        default="active",
        required=True,
    )
    join_date = fields.Date()
    is_technician = fields.Boolean()
    trade = fields.Char()
    skills = fields.Char()
    experience = fields.Char()
    shift_name = fields.Char()
    cert_level = fields.Char()
    workload = fields.Integer()
    availability = fields.Selection(
        [("available", "Available"), ("busy", "Busy"), ("leave", "On Leave"), ("rest", "Rest")],
        default="available",
    )
    hr_employee_id = fields.Many2one("hr.employee", string="HR Employee", ondelete="set null")


class WfShift(models.Model):
    _name = "wf.shift"
    _description = "Workforce Shift"
    _order = "time_label"

    name = fields.Char(required=True)
    site = fields.Char()
    department = fields.Char()
    time_label = fields.Char(required=True)
    capacity = fields.Integer(default=1)
    kind = fields.Selection(
        [("morning", "Morning"), ("afternoon", "Afternoon"), ("night", "Night")],
        default="morning",
    )
    active_now = fields.Boolean()


class WfRoster(models.Model):
    _name = "wf.roster"
    _description = "Roster Cell"
    _order = "date, employee_id"

    employee_id = fields.Many2one("wf.employee", required=True, ondelete="cascade")
    date = fields.Date(required=True)
    label = fields.Char(required=True)
    kind = fields.Selection(
        [("shift", "Shift"), ("off", "Off"), ("leave", "Leave"), ("open", "Unassigned")],
        default="shift",
        required=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        default="draft",
        required=True,
    )


class WfAttendance(models.Model):
    _name = "wf.attendance"
    _description = "Workforce Attendance"
    _order = "date desc, employee_id"

    employee_id = fields.Many2one("wf.employee", required=True, ondelete="cascade")
    date = fields.Date(required=True)
    shift_label = fields.Char()
    check_in = fields.Char()
    check_out = fields.Char()
    worked = fields.Char()
    overtime = fields.Char(default="00:00")
    status = fields.Selection(
        [("present", "Present"), ("late", "Late"), ("absent", "Absent"), ("completed", "Completed")],
        default="present",
        required=True,
    )
    hr_attendance_id = fields.Many2one("hr.attendance", ondelete="set null")


class WfLeave(models.Model):
    _name = "wf.leave"
    _description = "Workforce Leave"
    _order = "date_from desc"

    employee_id = fields.Many2one("wf.employee", required=True, ondelete="cascade")
    leave_type = fields.Char(required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    days = fields.Float()
    reason = fields.Char()
    status = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="pending",
        required=True,
    )


class WfSkill(models.Model):
    _name = "wf.skill"
    _description = "Workforce Skill"
    _order = "name"

    name = fields.Char(required=True)
    category = fields.Char()
    staff_count = fields.Integer()
    technician_count = fields.Integer()
    proficiency = fields.Integer()
    certification = fields.Char()
    expiry = fields.Date()
    status = fields.Selection(
        [("active", "Active"), ("expiring", "Expiring"), ("gap", "Gap")],
        default="active",
        required=True,
    )


class WfTask(models.Model):
    _name = "wf.task"
    _description = "Workforce Task"
    _order = "code"

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    location = fields.Char()
    site = fields.Char()
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        default="medium",
        required=True,
    )
    required_skill = fields.Char()
    status = fields.Selection(
        [("unassigned", "Unassigned"), ("assigned", "Assigned"), ("progress", "In Progress"), ("done", "Completed")],
        default="unassigned",
        required=True,
    )
    employee_id = fields.Many2one("wf.employee", ondelete="set null")
    due_label = fields.Char()
    hours = fields.Float()


class WfAlert(models.Model):
    _name = "wf.alert"
    _description = "Workforce Alert"
    _order = "id desc"

    name = fields.Char(required=True)
    detail = fields.Char()
    age_label = fields.Char()
    kind = fields.Selection(
        [("attendance", "Attendance"), ("skill", "Skill"), ("shift", "Shift"), ("task", "Task")],
        default="task",
    )
    resolved = fields.Boolean()
