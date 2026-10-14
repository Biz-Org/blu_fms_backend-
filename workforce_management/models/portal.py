import csv
import io
from datetime import date, datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class WfPortal(models.AbstractModel):
    _name = "wf.portal"
    _description = "Workforce Portal API"

    @api.model
    def _seed_demo(self):
        if self.env["wf.employee"].search_count([]):
            return
        today = fields.Date.context_today(self)
        people = [
            ("EMP-8273", "Michael Chang", "Maintenance", "HVAC Technician", "North Wing", "active", "2022-02-15", True, "HVAC", "Commercial", "8 yrs", "Morning", "Master", 45, "available"),
            ("EMP-8274", "Sarah Jenkins", "Janitorial", "Cleaning Staff", "South Tower", "active", "2021-11-01", True, "HVAC", "Commercial", "5 yrs", "Evening", "Level 2", 90, "busy"),
            ("EMP-8275", "David Rodriguez", "Security", "Security Guard", "Main Gate", "inactive", "2023-05-10", False, "Security", "Watch", "4 yrs", "Night", "", 0, "rest"),
            ("EMP-8276", "Emily Chen", "Maintenance", "Electrician", "East Wing", "active", "2020-08-22", True, "Electrical", "High Voltage", "9 yrs", "Morning", "Master", 27, "available"),
            ("FT-8892", "Marcus Jensen", "Maintenance", "Electrician", "Site Alpha", "active", "2018-03-01", True, "Electrician", "High Voltage", "8 yrs", "Morning", "Master", 40, "available"),
            ("FT-4430", "Sarah Chen", "Maintenance", "HVAC Tech", "Site Beta", "active", "2020-06-12", True, "HVAC", "Commercial", "5 yrs", "Evening", "Level 2", 90, "busy"),
            ("EMP-1042", "John Smith", "Maintenance", "Technician", "North Wing", "active", "2021-01-11", True, "Electrical", "Panels", "6 yrs", "Morning", "Level 2", 30, "available"),
            ("EMP-1048", "Alice Doe", "Maintenance", "Technician", "North Wing", "active", "2022-04-02", False, "Janitorial", "General", "3 yrs", "Morning", "", 10, "leave"),
            ("EMP-1102", "Mike Ross", "Maintenance", "Technician", "South Wing", "active", "2019-09-18", True, "Plumbing", "Pipes", "7 yrs", "Morning", "Level 2", 55, "available"),
            ("EMP-1210", "Kate Lynn", "Maintenance", "Technician", "North Wing", "active", "2023-02-07", False, "General", "Helper", "1 yr", "Morning", "", 15, "available"),
            ("TECH-001", "Marcus Johnson", "Security", "Guard", "North Campus", "active", "2020-01-09", False, "Security", "Watch", "5 yrs", "Morning", "", 20, "available"),
            ("SEC-014", "Robert Chen", "Maintenance", "Technician", "South Facility", "active", "2021-07-19", True, "Electrical", "Lighting", "4 yrs", "Morning", "Level 1", 35, "available"),
            ("CLN-093", "Amanda Lewis", "Janitorial", "Cleaner", "Main Gate", "active", "2024-01-03", False, "Janitorial", "Floors", "2 yrs", "Morning", "", 10, "available"),
            ("EMP-9921", "Sarah Smith", "Maintenance", "Technician", "North Wing", "active", "2019-05-14", False, "General", "", "4 yrs", "Morning", "", 0, "leave"),
            ("EMP-0942", "Mike Johnson", "Maintenance", "Technician", "East Wing", "active", "2022-11-20", False, "General", "", "3 yrs", "Morning", "", 0, "available"),
            ("EMP-3310", "Alice Lee", "Janitorial", "Cleaner", "South Tower", "active", "2023-08-01", False, "Janitorial", "", "2 yrs", "Morning", "", 0, "available"),
            ("TECH-204", "David Torres", "Maintenance", "Technician", "North Wing", "active", "2017-02-11", True, "Electrical", "High Voltage", "10 yrs", "Morning", "Master", 70, "busy"),
            ("TECH-118", "Emma Lawson", "Maintenance", "HVAC Tech", "East Wing", "active", "2020-10-05", True, "HVAC", "Commercial", "6 yrs", "Afternoon", "Level 2", 50, "available"),
            ("TECH-077", "Robert Blake", "Maintenance", "Technician", "South Tower", "active", "2018-12-02", True, "Plumbing", "Pipes", "8 yrs", "Morning", "Level 2", 48, "available"),
        ]
        employees = {}
        for row in people:
            code, name, dept, role, site, status, joined, tech, trade, skills, exp, shift, cert, load, avail = row
            hr_emp = self.env["hr.employee"].sudo().create({"name": name})
            rec = self.env["wf.employee"].create({
                "code": code,
                "name": name,
                "department": dept,
                "designation": role,
                "site": site,
                "status": status,
                "join_date": joined,
                "is_technician": tech,
                "trade": trade,
                "skills": skills,
                "experience": exp,
                "shift_name": shift,
                "cert_level": cert,
                "workload": load,
                "availability": avail,
                "hr_employee_id": hr_emp.id,
            })
            employees[name] = rec
        self.env["wf.shift"].create([
            {"name": "Morning", "site": "All Sites", "department": "All", "time_label": "06:00 - 14:00", "capacity": 500, "kind": "morning", "active_now": False},
            {"name": "Afternoon", "site": "All Sites", "department": "All", "time_label": "14:00 - 22:00", "capacity": 420, "kind": "afternoon", "active_now": True},
            {"name": "Night", "site": "All Sites", "department": "All", "time_label": "22:00 - 06:00", "capacity": 180, "kind": "night"},
            {"name": "Morning Maintenance", "site": "North Campus", "department": "Maintenance", "time_label": "08:00 - 16:00", "capacity": 5, "kind": "morning", "active_now": True},
            {"name": "Security Night Watch", "site": "South Facility", "department": "Security", "time_label": "22:00 - 06:00", "capacity": 4, "kind": "night"},
        ])
        monday = today - timedelta(days=today.weekday())
        roster_people = ["John Smith", "Alice Doe", "Mike Ross", "Kate Lynn"]
        pattern = {
            "John Smith": ["08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "OFF", "OFF"],
            "Alice Doe": ["08:00 - 16:00", "08:00 - 16:00", "Leave", "Leave", "OFF", "OFF", "OFF"],
            "Mike Ross": ["08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "OFF", "OFF"],
            "Kate Lynn": ["OFF", "OFF", "Unassigned", "16:00 - 00:00", "16:00 - 00:00", "16:00 - 00:00", "16:00 - 00:00"],
        }
        roster_rows = []
        for name in roster_people:
            for offset, label in enumerate(pattern[name]):
                kind = "off" if label == "OFF" else "leave" if label == "Leave" else "open" if label == "Unassigned" else "shift"
                roster_rows.append({
                    "employee_id": employees[name].id,
                    "date": monday + timedelta(days=offset),
                    "label": label,
                    "kind": kind,
                    "state": "draft",
                })
        self.env["wf.roster"].create(roster_rows)
        attendance = [
            ("Marcus Johnson", "06:00 - 16:00", "07:55", "", "04:20", "00:00", "present"),
            ("Sarah Jenkins", "06:00 - 16:00", "08:15", "", "04:10", "00:00", "late"),
            ("Robert Chen", "06:00 - 14:00", "05:45", "14:10", "08:25", "00:45", "completed"),
            ("Amanda Lewis", "09:00 - 17:00", "", "", "00:00", "00:00", "absent"),
        ]
        for name, shift, cin, cout, worked, ot, status in attendance:
            self.env["wf.attendance"].create({
                "employee_id": employees[name].id,
                "date": today,
                "shift_label": shift,
                "check_in": cin,
                "check_out": cout,
                "worked": worked,
                "overtime": ot,
                "status": status,
            })
        self.env["wf.leave"].create([
            {"employee_id": employees["John Smith"].id, "leave_type": "Annual Leave", "date_from": today.replace(day=12) if today.day else today, "date_to": today.replace(day=15) if today.month else today, "days": 4, "reason": "Family vacation", "status": "pending"},
            {"employee_id": employees["Sarah Smith"].id, "leave_type": "Sick Leave", "date_from": today, "date_to": today + timedelta(days=1), "days": 1, "reason": "Flu symptoms", "status": "approved"},
            {"employee_id": employees["Mike Johnson"].id, "leave_type": "Unpaid Leave", "date_from": today + timedelta(days=19), "date_to": today + timedelta(days=20), "days": 2, "reason": "Personal matters", "status": "pending"},
            {"employee_id": employees["Alice Lee"].id, "leave_type": "Annual Leave", "date_from": today.replace(month=9, day=28) if today.month >= 9 else today - timedelta(days=10), "date_to": today.replace(month=9, day=30) if today.month >= 9 else today - timedelta(days=8), "days": 3, "reason": "Short trip", "status": "rejected"},
        ])
        self.env["wf.skill"].create([
            {"name": "High Voltage Systems", "category": "Electrical", "staff_count": 12, "technician_count": 8, "proficiency": 85, "certification": "NFPA 70E", "expiry": "2026-11-15", "status": "active"},
            {"name": "Commercial HVAC Diagnostics", "category": "HVAC", "staff_count": 18, "technician_count": 14, "proficiency": 92, "certification": "EPA Section 608", "expiry": "2026-12-01", "status": "expiring"},
            {"name": "Elevator Rescue Op", "category": "Safety", "staff_count": 2, "technician_count": 1, "proficiency": 15, "certification": "QEI-1", "status": "gap"},
            {"name": "Boiler Maintenance", "category": "Mechanical", "staff_count": 9, "technician_count": 7, "proficiency": 60, "certification": "ABSA Grade 4", "expiry": "2027-06-29", "status": "active"},
            {"name": "Fire Suppression Systems", "category": "Safety", "staff_count": 5, "technician_count": 4, "proficiency": 40, "certification": "NICET Level II", "expiry": "2026-02-10", "status": "active"},
        ])
        task_rows = [
            ("TSK-8821", "HVAC Filter Replacement", "North Wing, Fl 3", "North Wing", "low", "HVAC Tech", "assigned", "Sarah Jenkins", "14:00", 1.5),
            ("TSK-8822", "Main Breaker Fault", "Basement Elect.", "East Wing", "critical", "Master Elec.", "unassigned", "", "14:00", 3),
            ("TSK-8823", "Plumbing Inspection", "South Tower Restrooms", "South Tower", "medium", "Plumber", "progress", "Mike Ross", "16:00", 2),
            ("TSK-8819", "Elevator Maintenance", "Core Shaft A", "North Wing", "low", "Elevator Tech", "assigned", "Emily Chen", "18:00", 4),
            ("TSK-8842", "Spill Cleanup - Lobby", "Main Entrance", "Main Gate", "high", "Janitorial", "unassigned", "", "15:30", 1),
            ("TSK-8841", "Replace Conference Room Projector Lamp", "Room 402", "North Wing", "medium", "AV Tech", "unassigned", "", "17:00", 1),
            ("TSK-8801", "Lighting Fixture Repair", "East Wing L1", "East Wing", "medium", "Electrical", "unassigned", "", "14:10", 2),
        ]
        for code, name, loc, site, priority, skill, status, person, due, hours in task_rows:
            self.env["wf.task"].create({
                "code": code,
                "name": name,
                "location": loc,
                "site": site,
                "priority": priority,
                "required_skill": skill,
                "status": status,
                "employee_id": employees[person].id if person else False,
                "due_label": due,
                "hours": hours,
            })
        for index in range(18):
            owner = list(employees.values())[index % 4]
            self.env["wf.task"].create({
                "code": f"TSK-90{index:02d}",
                "name": f"Routine check {index + 1}",
                "location": owner.site,
                "site": owner.site,
                "priority": "low",
                "required_skill": owner.trade or "General",
                "status": "done" if index % 3 else "assigned",
                "employee_id": owner.id,
                "due_label": "09:00",
                "hours": 1 + (index % 3) * 0.5,
            })
        self.env["wf.alert"].create([
            {"name": "Attendance Exception", "detail": "5 HVAC technicians marked absent in Sector A. Risk of SLA breach.", "age_label": "23m ago", "kind": "attendance"},
            {"name": "Skill Gap Detected", "detail": "High voltage electrical task unassigned. No certified techs available in current shift.", "age_label": "45m ago", "kind": "skill"},
            {"name": "Shift Conflict", "detail": "Overlapping schedules for 12 janitorial staff in Building B.", "age_label": "1h ago", "kind": "shift"},
            {"name": "Unassigned High Priority", "detail": "Plumbing emergency in Exec Lounge. Pending assignment.", "age_label": "2h ago", "kind": "task"},
        ])

    def _filters(self, filters):
        filters = filters or {}
        return {
            "department": filters.get("department") or "",
            "site": filters.get("site") or "",
            "status": filters.get("status") or "",
            "search": (filters.get("search") or "").strip().lower(),
        }

    def _employees(self, filters):
        domain = []
        if filters["department"]:
            domain.append(("department", "=", filters["department"]))
        if filters["site"]:
            domain.append(("site", "=", filters["site"]))
        if filters["status"]:
            domain.append(("status", "=", filters["status"]))
        rows = self.env["wf.employee"].search(domain)
        if filters["search"]:
            rows = rows.filtered(lambda rec: filters["search"] in (rec.name or "").lower() or filters["search"] in (rec.code or "").lower())
        return rows

    def _initials(self, name):
        parts = [part for part in (name or "").split() if part]
        return "".join(part[0] for part in parts[:2]).upper() or "WF"

    def _emp(self, rec):
        return {
            "id": rec.id,
            "name": rec.name,
            "code": rec.code,
            "department": rec.department or "",
            "designation": rec.designation or "",
            "site": rec.site or "",
            "status": rec.status,
            "join_date": rec.join_date.isoformat() if rec.join_date else "",
            "is_technician": rec.is_technician,
            "trade": rec.trade or "",
            "skills": rec.skills or "",
            "experience": rec.experience or "",
            "shift_name": rec.shift_name or "",
            "cert_level": rec.cert_level or "",
            "workload": rec.workload or 0,
            "availability": rec.availability or "available",
            "initials": self._initials(rec.name),
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = self._filters(filters)
        employees = self._employees(filters)
        all_employees = self.env["wf.employee"].search([])
        techs = employees.filtered("is_technician")
        today = fields.Date.context_today(self)
        attendance = self.env["wf.attendance"].search([("employee_id", "in", employees.ids), ("date", "=", today)])
        if not attendance and not (filters["department"] or filters["site"] or filters["status"] or filters["search"]):
            attendance = self.env["wf.attendance"].search([("date", "=", today)])
        leaves = self.env["wf.leave"].search([("employee_id", "in", employees.ids)]) if employees else self.env["wf.leave"]
        tasks = self.env["wf.task"].search([])
        if filters["site"]:
            tasks = tasks.filtered(lambda task: task.site == filters["site"])
        if filters["search"]:
            tasks = tasks.filtered(lambda task: filters["search"] in (task.name or "").lower() or filters["search"] in (task.code or "").lower())
        shifts = self.env["wf.shift"].search([])
        alerts = self.env["wf.alert"].search([("resolved", "=", False)])
        skills = self.env["wf.skill"].search([])
        monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=offset) for offset in range(7)]
        self._ensure_week_roster(monday)
        roster = self.env["wf.roster"].search([("date", ">=", days[0]), ("date", "<=", days[-1]), ("employee_id", "in", employees.ids)])
        present = len(attendance.filtered(lambda row: row.status in ("present", "completed", "late")))
        absent = len(attendance.filtered(lambda row: row.status == "absent"))
        late = len(attendance.filtered(lambda row: row.status == "late"))
        on_leave_people = employees.filtered(lambda rec: rec.availability == "leave")
        active_techs = techs.filtered(lambda rec: rec.availability == "available")
        total = len(employees) or 1
        done = len(tasks.filtered(lambda task: task.status == "done"))
        assigned = len(tasks.filtered(lambda task: task.status == "assigned"))
        progress = len(tasks.filtered(lambda task: task.status == "progress"))
        open_tasks = len(tasks.filtered(lambda task: task.status == "unassigned"))
        task_total = len(tasks) or 1
        roster_rows = []
        for employee in employees.filtered(lambda rec: rec.name in ("John Smith", "Alice Doe", "Mike Ross", "Kate Lynn")) or employees[:4]:
            cells = []
            for day in days:
                cell = roster.filtered(lambda line, employee=employee, day=day: line.employee_id == employee and line.date == day)[:1]
                cells.append({
                    "date": day.isoformat(),
                    "label": cell.label if cell else "",
                    "kind": cell.kind if cell else "",
                })
            roster_rows.append({"id": employee.id, "name": employee.name, "initials": self._initials(employee.name), "cells": cells})
        tech_performance = []
        for tech in techs:
            owned = tasks.filtered(lambda task, tech=tech: task.employee_id == tech)
            completed = owned.filtered(lambda task: task.status == "done")
            rate = round(len(completed) / len(owned) * 100, 1) if owned else 0
            avg_hours = round(sum(completed.mapped("hours")) / len(completed), 2) if completed else 0
            tech_performance.append({
                "id": tech.id,
                "name": tech.name,
                "initials": self._initials(tech.name),
                "assigned": len(owned),
                "completed": len(completed),
                "rate": rate,
                "avg": f"{int(avg_hours)}h {int((avg_hours % 1) * 60)}m" if owned else "0h",
                "utilization": min(100, tech.workload or rate),
            })
        trend = []
        for week in range(1, 5):
            trend.append({"label": f"Week {week}", "value": done // 4 + week * max(len(techs), 1)})
        peak = max([item["value"] for item in trend] or [1])
        for item in trend:
            item["pct"] = round(item["value"] / peak * 100)
        tech_total = len(techs) or 1
        availability = [
            ("Available", techs.filtered(lambda rec: rec.availability == "available")),
            ("Busy / Assigned", techs.filtered(lambda rec: rec.availability == "busy")),
            ("On Leave", techs.filtered(lambda rec: rec.availability == "leave")),
            ("Unavailable / Rest", techs.filtered(lambda rec: rec.availability == "rest")),
        ]
        shift_rows = []
        conflicts = []
        for shift in shifts.filtered(lambda rec: rec.name not in ("Morning", "Afternoon", "Night")):
            assigned_count = len(employees.filtered(lambda rec, shift=shift: rec.site == shift.site and rec.status == "active"))
            shift_rows.append({
                "id": shift.id,
                "name": shift.name,
                "site": shift.site or "",
                "department": shift.department or "",
                "time": shift.time_label,
                "capacity": shift.capacity,
                "assigned": assigned_count,
                "status": "shortage" if assigned_count < shift.capacity else "optimal",
            })
            if assigned_count < shift.capacity:
                conflicts.append({
                    "name": shift.name,
                    "detail": f"{shift.capacity - assigned_count} more staff needed at {shift.site or 'this site'}.",
                })
        ot_minutes = 0
        for row in attendance:
            text = (row.overtime or "00:00").strip()
            if ":" in text:
                hours, mins = text.split(":", 1)
                if hours.isdigit() and mins.isdigit():
                    ot_minutes += int(hours) * 60 + int(mins)
        overtime_label = f"{ot_minutes // 60}h {ot_minutes % 60:02d}m"
        done_tasks = tasks.filtered(lambda task: task.status == "done")
        avg_hours = sum(done_tasks.mapped("hours")) / len(done_tasks) if done_tasks else 0
        avg_time = f"{int(avg_hours)}h {int(round((avg_hours % 1) * 60))}m"
        return {
            "filters": filters,
            "departments": sorted({rec.department for rec in all_employees if rec.department}),
            "sites": sorted({rec.site for rec in all_employees if rec.site}),
            "kpis": {
                "total": len(employees),
                "technicians": len(techs),
                "present": present,
                "on_leave": len(on_leave_people),
                "available": len(active_techs),
                "active_tasks": assigned + progress,
                "pending": open_tasks + len(leaves.filtered(lambda leave: leave.status == "pending")),
                "utilization": round(done / task_total * 100),
            },
            "force": {
                "present": present,
                "absent": absent,
                "late": late,
                "leave": len(on_leave_people),
                "present_pct": round(present / total * 100),
                "absent_pct": round(absent / total * 100),
                "late_pct": round(late / total * 100),
                "leave_pct": round(len(on_leave_people) / total * 100),
            },
            "availability": [
                {"label": label, "count": len(rows), "pct": round(len(rows) / tech_total * 100)}
                for label, rows in availability
            ],
            "alerts": [{
                "id": alert.id, "name": alert.name, "detail": alert.detail or "", "age": alert.age_label or "", "kind": alert.kind,
            } for alert in alerts],
            "shift_cards": [{
                "id": shift.id, "name": shift.name, "time": shift.time_label, "kind": shift.kind, "active": shift.active_now,
                "count": len(employees.filtered(lambda rec, shift=shift: (rec.shift_name or "").lower() == shift.name.lower() or (shift.kind == "morning" and rec.shift_name == "Morning"))),
            } for shift in shifts.filtered(lambda shift: shift.name in ("Morning", "Afternoon", "Night"))],
            "task_dist": {"unassigned": open_tasks, "assigned": assigned, "progress": progress, "done": done},
            "employees": [self._emp(rec) for rec in employees],
            "employee_stats": {
                "total": len(employees),
                "active": len(employees.filtered(lambda rec: rec.status == "active")),
                "inactive": len(employees.filtered(lambda rec: rec.status == "inactive")),
                "new": len(employees.filtered(lambda rec: rec.join_date and rec.join_date.month == today.month and rec.join_date.year == today.year)),
            },
            "technicians": [self._emp(rec) for rec in techs],
            "shifts": shift_rows,
            "conflicts": conflicts,
            "roster": {
                "start": days[0].isoformat(),
                "end": days[-1].isoformat(),
                "label": f"{days[0].strftime('%b %d')} - {days[-1].strftime('%b %d, %Y')}",
                "days": [day.strftime("%a %d") for day in days],
                "rows": roster_rows,
                "scheduled": len(roster.filtered(lambda line: line.kind == "shift")),
                "unassigned": len(roster.filtered(lambda line: line.kind == "open")),
                "on_leave": len(roster.filtered(lambda line: line.kind == "leave")),
                "total": len(employees),
                "state": roster[:1].state if roster else "draft",
            },
            "attendance": {
                "present": present,
                "expected": len(employees.filtered(lambda rec: rec.status == "active")),
                "absent": absent,
                "late": late,
                "on_leave": len(on_leave_people),
                "overtime": overtime_label,
                "rows": [{
                    "id": row.id,
                    "name": row.employee_id.name,
                    "code": row.employee_id.code,
                    "initials": self._initials(row.employee_id.name),
                    "shift": row.shift_label or "",
                    "check_in": row.check_in or "—",
                    "check_out": row.check_out or "—",
                    "worked": row.worked or "00:00",
                    "overtime": row.overtime or "00:00",
                    "status": row.status,
                } for row in attendance],
                "trend": [70, 82, 64, 90, 76, 88, present and 80 or 40],
            },
            "leaves": [{
                "id": leave.id,
                "name": leave.employee_id.name,
                "code": leave.employee_id.code,
                "initials": self._initials(leave.employee_id.name),
                "type": leave.leave_type,
                "start": leave.date_from.strftime("%b %d") if leave.date_from else "",
                "end": leave.date_to.strftime("%b %d") if leave.date_to else "",
                "days": leave.days,
                "reason": leave.reason or "",
                "status": leave.status,
            } for leave in leaves],
            "leave_stats": {
                "pending": len(leaves.filtered(lambda leave: leave.status == "pending")),
                "approved": len(leaves.filtered(lambda leave: leave.status == "approved")),
                "rejected": len(leaves.filtered(lambda leave: leave.status == "rejected")),
                "today": len(on_leave_people),
            },
            "skills": [{
                "id": skill.id,
                "name": skill.name,
                "category": skill.category or "",
                "staff": skill.staff_count,
                "techs": skill.technician_count,
                "proficiency": skill.proficiency,
                "certification": skill.certification or "—",
                "expiry": skill.expiry.isoformat() if skill.expiry else "—",
                "status": skill.status,
            } for skill in skills],
            "skill_stats": {
                "coverage": round(sum(skills.mapped("proficiency")) / len(skills)) if skills else 0,
                "critical": len(skills),
                "available": len(techs),
                "gaps": len(skills.filtered(lambda skill: skill.status == "gap")),
                "expiring": len(skills.filtered(lambda skill: skill.status == "expiring")),
            },
            "tasks": [{
                "id": task.id,
                "code": task.code,
                "name": task.name,
                "location": task.location or "",
                "site": task.site or "",
                "priority": task.priority,
                "skill": task.required_skill or "",
                "status": task.status,
                "employee": task.employee_id.name or "",
                "employee_id": task.employee_id.id or 0,
                "due": task.due_label or "",
            } for task in tasks.sorted(lambda task: task.status == "done")],
            "task_stats": {"total": len(tasks), "unassigned": open_tasks, "assigned": assigned, "progress": progress, "done": done},
            "allocation": {
                "techs": [self._emp(rec) for rec in techs.filtered(lambda rec: rec.availability in ("available", "busy"))],
                "pending": [{
                    "id": task.id, "code": task.code, "name": task.name, "location": task.location or "",
                    "priority": task.priority, "skill": task.required_skill or "", "due": task.due_label or "",
                } for task in tasks.filtered(lambda task: task.status == "unassigned")[:6]],
            },
            "productivity": {
                "completed": done,
                "rate": round(done / task_total * 100, 1),
                "utilization": round(present / total * 100, 1) if employees else 0,
                "avg_tasks": round(done / max(len(techs), 1), 1),
                "avg_time": avg_time,
                "trend": trend,
                "available_pct": round(len(active_techs) / tech_total * 100),
                "productive_pct": round(done / task_total * 100, 1),
                "nonproductive": f"{round(100 - done / task_total * 100, 1)}%",
                "rows": tech_performance,
            },
        }

    def _roster_pattern(self):
        return {
            "John Smith": ["08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "OFF", "OFF"],
            "Alice Doe": ["08:00 - 16:00", "08:00 - 16:00", "Leave", "Leave", "OFF", "OFF", "OFF"],
            "Mike Ross": ["08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "08:00 - 16:00", "OFF", "OFF"],
            "Kate Lynn": ["OFF", "OFF", "Unassigned", "16:00 - 00:00", "16:00 - 00:00", "16:00 - 00:00", "16:00 - 00:00"],
        }

    def _ensure_week_roster(self, monday):
        pattern = self._roster_pattern()
        people = self.env["wf.employee"].search([("name", "in", list(pattern))])
        by_name = {rec.name: rec for rec in people}
        existing = self.env["wf.roster"].search([
            ("date", ">=", monday),
            ("date", "<=", monday + timedelta(days=6)),
            ("employee_id", "in", people.ids),
        ])
        rows = []
        for name, labels in pattern.items():
            employee = by_name.get(name)
            if not employee:
                continue
            for offset, label in enumerate(labels):
                day = monday + timedelta(days=offset)
                if existing.filtered(lambda line, employee=employee, day=day: line.employee_id == employee and line.date == day):
                    continue
                kind = "off" if label == "OFF" else "leave" if label == "Leave" else "open" if label == "Unassigned" else "shift"
                rows.append({
                    "employee_id": employee.id,
                    "date": day,
                    "label": label,
                    "kind": kind,
                    "state": "draft",
                })
        if rows:
            self.env["wf.roster"].create(rows)

    def _refresh(self, filters):
        return self.get_dashboard_data(filters)

    def _hr_employee(self, name):
        return self.env["hr.employee"].sudo().create({"name": name})

    @api.model
    def add_employee(self, values):
        values = values or {}
        if not values.get("name"):
            raise UserError("Employee name is required.")
        count = self.env["wf.employee"].search_count([]) + 1
        self.env["wf.employee"].create({
            "name": values["name"],
            "code": values.get("code") or f"EMP-{8200 + count}",
            "department": values.get("department") or "Maintenance",
            "designation": values.get("designation") or "Staff",
            "site": values.get("site") or "North Wing",
            "status": values.get("status") or "active",
            "join_date": values.get("join_date") or fields.Date.context_today(self),
            "is_technician": bool(values.get("is_technician")),
            "trade": values.get("trade") or "",
            "skills": values.get("skills") or "",
            "shift_name": values.get("shift_name") or "Morning",
            "availability": "available",
            "hr_employee_id": self._hr_employee(values["name"]).id,
        })
        return self._refresh(values.get("filters"))

    @api.model
    def add_technician(self, values):
        values = values or {}
        values["is_technician"] = True
        values["designation"] = values.get("designation") or values.get("trade") or "Technician"
        return self.add_employee(values)

    @api.model
    def add_shift(self, values):
        values = values or {}
        if not values.get("name"):
            raise UserError("Shift name is required.")
        self.env["wf.shift"].create({
            "name": values["name"],
            "site": values.get("site") or "All Sites",
            "department": values.get("department") or "All",
            "time_label": values.get("time_label") or "08:00 - 16:00",
            "capacity": int(values.get("capacity") or 1),
            "kind": values.get("kind") or "morning",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def publish_roster(self, filters=None):
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        roster = self.env["wf.roster"].search([("date", ">=", monday), ("date", "<=", sunday)])
        roster.write({"state": "published"})
        return self._refresh(filters)

    @api.model
    def set_attendance(self, employee_id, status, filters=None):
        employee = self.env["wf.employee"].browse(int(employee_id))
        if not employee.exists():
            raise UserError("Employee was not found.")
        today = fields.Date.context_today(self)
        row = self.env["wf.attendance"].search([("employee_id", "=", employee.id), ("date", "=", today)], limit=1)
        check_in = "09:00" if status != "absent" else ""
        vals = {
            "employee_id": employee.id,
            "date": today,
            "shift_label": employee.shift_name or "08:00 - 16:00",
            "check_in": check_in,
            "check_out": "",
            "worked": "00:00" if status == "absent" else "01:00",
            "status": status or "present",
        }
        if row:
            row.write(vals)
        else:
            row = self.env["wf.attendance"].create(vals)
        if status != "absent" and employee.hr_employee_id and not row.hr_attendance_id:
            opened = self.env["hr.attendance"].sudo().search([
                ("employee_id", "=", employee.hr_employee_id.id),
                ("check_out", "=", False),
            ], limit=1)
            if not opened:
                attendance = self.env["hr.attendance"].sudo().create({
                    "employee_id": employee.hr_employee_id.id,
                    "check_in": fields.Datetime.now(),
                })
                row.hr_attendance_id = attendance.id
        if status == "absent":
            employee.availability = "rest"
        return self._refresh(filters)

    @api.model
    def add_leave(self, values):
        values = values or {}
        if not values.get("employee_id") or not values.get("leave_type"):
            raise UserError("Employee and leave type are required.")
        start = fields.Date.to_date(values.get("date_from"))
        end = fields.Date.to_date(values.get("date_to") or values.get("date_from"))
        self.env["wf.leave"].create({
            "employee_id": int(values["employee_id"]),
            "leave_type": values["leave_type"],
            "date_from": start,
            "date_to": end,
            "days": (end - start).days + 1,
            "reason": values.get("reason") or "",
            "status": "pending",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def review_leave(self, leave_id, status, filters=None):
        leave = self.env["wf.leave"].browse(int(leave_id))
        if not leave.exists():
            raise UserError("Leave request was not found.")
        leave.status = status if status in ("approved", "rejected", "pending") else "pending"
        if leave.status == "approved":
            leave.employee_id.availability = "leave"
        elif leave.employee_id.availability == "leave":
            leave.employee_id.availability = "available"
        return self._refresh(filters)

    @api.model
    def add_skill(self, values):
        values = values or {}
        if not values.get("name"):
            raise UserError("Skill name is required.")
        self.env["wf.skill"].create({
            "name": values["name"],
            "category": values.get("category") or "General",
            "staff_count": int(values.get("staff_count") or 1),
            "technician_count": int(values.get("technician_count") or 1),
            "proficiency": int(values.get("proficiency") or 50),
            "certification": values.get("certification") or "",
            "status": values.get("status") or "active",
        })
        return self._refresh(values.get("filters"))

    @api.model
    def add_task(self, values):
        values = values or {}
        if not values.get("name"):
            raise UserError("Task name is required.")
        count = self.env["wf.task"].search_count([]) + 1
        self.env["wf.task"].create({
            "code": values.get("code") or f"TSK-{8900 + count}",
            "name": values["name"],
            "location": values.get("location") or "",
            "site": values.get("site") or "North Wing",
            "priority": values.get("priority") or "medium",
            "required_skill": values.get("required_skill") or "General",
            "status": "unassigned",
            "due_label": values.get("due_label") or "17:00",
            "hours": float(values.get("hours") or 1),
        })
        return self._refresh(values.get("filters"))

    @api.model
    def assign_task(self, task_id, employee_id, filters=None):
        task = self.env["wf.task"].browse(int(task_id))
        employee = self.env["wf.employee"].browse(int(employee_id))
        if not task.exists() or not employee.exists():
            raise UserError("Choose a task and a technician.")
        task.write({"employee_id": employee.id, "status": "assigned"})
        if employee.availability == "available":
            employee.availability = "busy"
        return self._refresh(filters)

    @api.model
    def auto_assign(self, filters=None):
        pending = self.env["wf.task"].search([("status", "=", "unassigned")])
        techs = self.env["wf.employee"].search([("is_technician", "=", True), ("availability", "=", "available")])
        for task in pending:
            match = techs.filtered(lambda tech, task=task: task.required_skill and task.required_skill.lower() in f"{tech.trade} {tech.skills}".lower())[:1]
            if not match:
                match = techs[:1]
            if not match:
                break
            task.write({"employee_id": match.id, "status": "assigned"})
            match.availability = "busy"
            techs -= match
        return self._refresh(filters)

    @api.model
    def resolve_alert(self, alert_id, filters=None):
        alert = self.env["wf.alert"].browse(int(alert_id))
        if alert.exists():
            alert.resolved = True
        return self._refresh(filters)

    @api.model
    def report_file(self, kind, filters=None):
        data = self.get_dashboard_data(filters)
        kind = kind or "employees"
        if kind == "tasks":
            header = ["Code", "Task", "Location", "Priority", "Status", "Technician"]
            body = [[row["code"], row["name"], row["location"], row["priority"], row["status"], row["employee"]] for row in data["tasks"]]
        elif kind == "attendance":
            header = ["Employee", "Shift", "Check In", "Check Out", "Status"]
            body = [[row["name"], row["shift"], row["check_in"], row["check_out"], row["status"]] for row in data["attendance"]["rows"]]
        else:
            header = ["Code", "Employee", "Department", "Designation", "Site", "Status"]
            body = [[row["code"], row["name"], row["department"], row["designation"], row["site"], row["status"]] for row in data["employees"]]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(body)
        return {"filename": f"workforce-{kind}.csv", "content": buffer.getvalue()}
