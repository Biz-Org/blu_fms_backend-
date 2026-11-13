# Part of Preventive Maintenance Management.

import csv
import io
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression

from .pm_access import (
    GROUP_PM_ADMIN,
    GROUP_PM_MANAGER,
    GROUP_PM_TECHNICIAN,
    pm_is_admin,
    pm_is_any_pm_user,
    pm_is_manager,
    pm_is_technician_only,
)


class PmService(models.AbstractModel):
    """RPC helpers for the Preventive Maintenance OWL client (no SQL table)."""

    _name = "pm.service"
    _description = "Preventive Maintenance Service"

    def _json_date(self, d):
        return fields.Date.to_string(d) if d else False

    def _domain_company(self):
        return [("company_id", "in", self.env.companies.ids)]

    def _check_manager(self):
        if not pm_is_manager(self.env):
            raise AccessError("This action requires Maintenance Manager access.")

    def _check_pm_admin(self):
        if not pm_is_admin(self.env):
            raise AccessError("This action requires PM Administrator access.")

    def _check_pm_user(self):
        if not pm_is_any_pm_user(self.env):
            raise AccessError("Preventive Maintenance access required.")

    @api.model
    def get_session_access(self):
        """Role flags for the OWL client."""
        self._check_pm_user()
        u = self.env.user
        return {
            "is_admin": pm_is_admin(self.env),
            "is_manager": pm_is_manager(self.env),
            "is_technician_only": pm_is_technician_only(self.env),
            "user_id": u.id,
            "user_name": u.name,
            "password_reset_required": bool(u.pm_password_reset_required),
        }

    @api.model
    def get_dashboard_kpis(self, filters=None):
        self._check_pm_user()
        if pm_is_technician_only(self.env):
            return self.get_technician_dashboard_kpis(filters)
        if not pm_is_manager(self.env):
            raise AccessError("Dashboard is not available for your PM role.")
        """filters: { date_from, date_to, property_location, equipment_id }"""
        filters = filters or {}
        Plan = self.env["pm.plan"].sudo()
        Wo = self.env["pm.work.order"].sudo()
        Schedule = self.env["pm.schedule"].sudo()
        today = fields.Date.today()
        week_end = today + timedelta(days=7)

        plan_domain = expression.AND(
            [[("state", "=", "active")], self._domain_company()]
        )
        wo_domain = self._domain_company()
        sched_domain = self._domain_company()

        if filters.get("property_location"):
            loc_txt = filters["property_location"].strip()
            if loc_txt:
                wo_domain = expression.AND([wo_domain, [("property_location", "ilike", loc_txt)]])
                sched_domain = expression.AND([sched_domain, [("property_location", "ilike", loc_txt)]])
        if filters.get("equipment_id"):
            eq = int(filters["equipment_id"])
            wo_domain = expression.AND([wo_domain, [("equipment_id", "=", eq)]])
            sched_domain = expression.AND([sched_domain, [("equipment_id", "=", eq)]])

        active_plans = Plan.search_count(plan_domain)

        due_today = Schedule.search_count(
            expression.AND(
                [
                    sched_domain,
                    [("date_planned", "=", today)],
                    [("state", "in", ("scheduled", "due", "overdue", "rescheduled"))],
                ]
            )
        )
        due_week = Schedule.search_count(
            expression.AND(
                [
                    sched_domain,
                    [("date_planned", ">=", today), ("date_planned", "<=", week_end)],
                    [("state", "in", ("scheduled", "due", "overdue", "rescheduled"))],
                ]
            )
        )
        upcoming = Schedule.search_count(
            expression.AND(
                [
                    sched_domain,
                    [("date_planned", ">", today)],
                    [("state", "in", ("scheduled", "rescheduled"))],
                ]
            )
        )
        overdue_sched = Schedule.search_count(
            expression.AND([sched_domain, [("state", "=", "overdue")]])
        )
        wo_prog = Wo.search_count(expression.AND([wo_domain, [("state", "=", "in_progress")]]))
        wo_done = Wo.search_count(
            expression.AND(
                [
                    wo_domain,
                    [
                        ("state", "=", "completed"),
                        ("date_scheduled", "=", today),
                    ],
                ]
            )
        )
        # Compliance: completed / (completed + overdue + skipped + cancelled) in period — simplified
        month_start = date(today.year, today.month, 1)
        date_from = filters.get("date_from") or fields.Date.to_string(month_start)
        date_to = filters.get("date_to") or fields.Date.to_string(today)
        comp_domain = expression.AND(
            [
                wo_domain,
                [
                    ("date_scheduled", ">=", date_from),
                    ("date_scheduled", "<=", date_to),
                    ("state", "in", ("completed", "overdue", "skipped", "cancelled")),
                ],
            ]
        )
        w_all = Wo.search(comp_domain)
        denom = len(w_all)
        numer = len(w_all.filtered(lambda w: w.state == "completed"))
        compliance = round((numer / denom) * 100, 1) if denom else 0.0

        cost_wos = Wo.search(
            expression.AND(
                [
                    wo_domain,
                    [
                        ("state", "=", "completed"),
                        ("date_scheduled", ">=", date_from),
                        ("date_scheduled", "<=", date_to),
                    ],
                ]
            )
        )
        total_cost = sum(cost_wos.mapped("total_cost"))

        return {
            "role": "manager",
            "active_plans": active_plans,
            "due_today": due_today,
            "due_week": due_week,
            "upcoming": upcoming,
            "overdue_schedules": overdue_sched,
            "wo_in_progress": wo_prog,
            "wo_completed_today": wo_done,
            "compliance_pct": compliance,
            "total_cost_period": total_cost,
            "currency": self.env.company.currency_id.name,
        }

    @api.model
    def get_technician_dashboard_kpis(self, filters=None):
        self._check_pm_user()
        if not pm_is_technician_only(self.env) and not pm_is_manager(self.env):
            raise AccessError("Technician dashboard not available.")
        Wo = self.env["pm.work.order"]
        uid = self.env.user.id
        base = expression.AND([self._domain_company(), [("user_id", "=", uid)]])
        today = fields.Date.today()
        assigned = Wo.search_count(
            expression.AND([base, [("state", "in", ("scheduled", "assigned", "rework", "overdue"))]])
        )
        in_progress = Wo.search_count(expression.AND([base, [("state", "=", "in_progress")]]))
        pending = Wo.search_count(expression.AND([base, [("state", "=", "pending_inspection")]]))
        completed_today = Wo.search_count(
            expression.AND(
                [
                    base,
                    [("state", "=", "completed"), ("date_scheduled", "=", today)],
                ]
            )
        )
        return {
            "role": "technician",
            "assigned_open": assigned,
            "in_progress": in_progress,
            "pending_inspection": pending,
            "completed_today": completed_today,
        }

    @api.model
    def search_read_plans(self, domain, fields_list, limit=80, offset=0, order="id desc"):
        self._check_pm_user()
        if not pm_is_manager(self.env):
            raise AccessError("PM Plans are only available to Maintenance Managers.")
        Plan = self.env["pm.plan"]
        dom = expression.AND([domain or [], self._domain_company()])
        return Plan.search_read(dom, fields_list, limit=limit, offset=offset, order=order)

    @api.model
    def search_read_schedules(self, domain, fields_list, limit=200, offset=0, order="date_planned asc"):
        self._check_pm_user()
        if not pm_is_manager(self.env):
            raise AccessError("PM schedules are only available to Maintenance Managers.")
        Schedule = self.env["pm.schedule"]
        dom = expression.AND([domain or [], self._domain_company()])
        return Schedule.search_read(dom, fields_list, limit=limit, offset=offset, order=order)

    @api.model
    def search_read_work_orders(self, domain, fields_list, limit=80, offset=0, order="id desc"):
        self._check_pm_user()
        Wo = self.env["pm.work.order"]
        dom = expression.AND([domain or [], self._domain_company()])
        if pm_is_technician_only(self.env):
            dom = expression.AND([dom, [("user_id", "=", self.env.user.id)]])
        return Wo.search_read(dom, fields_list, limit=limit, offset=offset, order=order)

    @api.model
    def get_work_order_detail(self, work_order_id):
        self._check_pm_user()
        wo = self.env["pm.work.order"].browse(int(work_order_id))
        if pm_is_technician_only(self.env):
            if wo.user_id and wo.user_id != self.env.user:
                raise AccessError("You cannot open this work order.")
        checklist = self.env["pm.checklist.result"].search_read(
            [("work_order_id", "=", wo.id)],
            ["id", "item_id", "result", "observation"],
        )
        item_ids = [c["item_id"][0] for c in checklist if c.get("item_id")]
        mandatory_map = {}
        if item_ids:
            for it in self.env["pm.checklist.item"].browse(item_ids).read(["mandatory"]):
                mandatory_map[it["id"]] = it["mandatory"]
        for c in checklist:
            if c.get("item_id"):
                c["item_mandatory"] = mandatory_map.get(c["item_id"][0], False)
        materials = self.env["pm.material.line"].search_read(
            [("work_order_id", "=", wo.id)],
            ["id", "product_id", "quantity", "unit_cost", "subtotal"],
        )
        costs = self.env["pm.cost.line"].search_read(
            [("work_order_id", "=", wo.id)], ["id", "cost_type", "description", "amount"]
        )
        readings = self.env["pm.asset.reading.result"].search_read(
            [("work_order_id", "=", wo.id)],
            ["id", "name", "min_value", "max_value", "value", "unit", "is_out_of_range", "template_id"],
        )
        timeline = self.env["pm.audit.log"].search_read(
            expression.AND(
                [self._domain_company(), [("res_model", "=", "pm.work.order"), ("res_id", "=", wo.id)]]
            ),
            ["create_date", "user_id", "action_type", "details"],
            order="create_date asc",
            limit=80,
        )
        supervisor = False
        sup = wo.supervisor_id or (wo.plan_id.supervisor_id if wo.plan_id else False)
        if sup:
            supervisor = {"id": sup.id, "name": sup.name}
        return {
            "work_order": wo.read()[0],
            "checklist": checklist,
            "materials": materials,
            "costs": costs,
            "readings": readings,
            "timeline": timeline,
            "supervisor": supervisor,
        }

    @api.model
    def get_reports(self, filters=None):
        """Aggregate real data for charts/tables."""
        self._check_manager()
        filters = filters or {}
        Wo = self.env["pm.work.order"].sudo()
        domain = self._domain_company()
        if filters.get("date_from"):
            domain = expression.AND([domain, [("date_scheduled", ">=", filters["date_from"])]])
        if filters.get("date_to"):
            domain = expression.AND([domain, [("date_scheduled", "<=", filters["date_to"])]])
        if filters.get("equipment_id"):
            domain = expression.AND([domain, [("equipment_id", "=", int(filters["equipment_id"]))]])
        if filters.get("user_id"):
            domain = expression.AND([domain, [("user_id", "=", int(filters["user_id"]))]])
        records = Wo.search(domain)
        by_status = {}
        for st in (
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
        ):
            by_status[st] = len(records.filtered(lambda w: w.state == st))
        by_asset = {}
        for wo in records:
            key = wo.equipment_id.display_name
            by_asset[key] = by_asset.get(key, 0) + 1
        return {"by_status": by_status, "by_asset": by_asset, "total": len(records)}

    @api.model
    def get_configuration(self):
        self._check_manager()
        cfg = self.env["pm.configuration"].get_config()
        return cfg.read()[0]

    @api.model
    def get_form_options(self):
        """Dropdown data for PM plan form (manager only)."""
        self._check_manager()
        Equipment = self.env["maintenance.equipment"].sudo()
        Team = self.env["maintenance.team"].sudo()
        User = self.env["res.users"].sudo()
        Template = self.env["pm.checklist.template"].sudo()
        Category = self.env["maintenance.equipment.category"].sudo()
        equipment = Equipment.search_read([], ["id", "name"], limit=500)
        teams = Team.search_read([], ["id", "name"], limit=100)
        users = User.search_read([("active", "=", True)], ["id", "name"], limit=200)
        tpl = Template.search_read([], ["id", "name"], limit=200)
        cats = Category.search_read([], ["id", "name"], limit=200)
        return {
            "equipment": [{"id": r["id"], "display_name": r["name"]} for r in equipment],
            "locations": [],
            "teams": teams,
            "users": users,
            "templates": tpl,
            "categories": cats,
        }

    @api.model
    def search_read_audit_log(self, domain, limit=120):
        self._check_manager()
        Audit = self.env["pm.audit.log"]
        dom = expression.AND([domain or [], self._domain_company()])
        return Audit.search_read(
            dom,
            [
                "create_date",
                "user_id",
                "action_type",
                "details",
                "res_model",
                "res_id",
                "value_before",
                "value_after",
            ],
            limit=limit,
            order="create_date desc",
        )

    @api.model
    def export_csv(self, model, domain, fields_list):
        self._check_manager()
        Model = self.env[model]
        dom = expression.AND([domain or [], self._domain_company()])
        records = Model.search(dom)
        data = records.read(fields_list)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(fields_list)
        for row in data:
            out = []
            for f in fields_list:
                val = row.get(f)
                if isinstance(val, tuple):
                    val = val[1]
                out.append(val if val is not False else "")
            writer.writerow(out)
        return {"filename": f"{model.replace('.', '_')}_export.csv", "data": buf.getvalue()}

    @api.model
    def search_read_inspection_queue(self, limit=80):
        """Work orders awaiting manager inspection."""
        self._check_manager()
        Wo = self.env["pm.work.order"]
        dom = expression.AND(
            [self._domain_company(), [("state", "=", "pending_inspection")]]
        )
        return Wo.search_read(
            dom,
            [
                "id",
                "name",
                "equipment_id",
                "user_id",
                "date_scheduled",
                "date_due",
                "work_performed",
                "technician_remarks",
            ],
            limit=limit,
            order="date_due asc, id asc",
        )

    @api.model
    def search_read_pm_users(self, role_filter=None, active_only=True):
        self._check_pm_admin()
        Users = self.env["res.users"].sudo()
        admin_g = self.env.ref(GROUP_PM_ADMIN)
        manager_g = self.env.ref(GROUP_PM_MANAGER)
        tech_g = self.env.ref(GROUP_PM_TECHNICIAN)
        domain = [
            "|",
            "|",
            ("groups_id", "in", admin_g.ids),
            ("groups_id", "in", manager_g.ids),
            ("groups_id", "in", tech_g.ids),
        ]
        if active_only:
            domain = expression.AND([domain, [("active", "=", True)]])
        if role_filter == "admin":
            domain = expression.AND([domain, [("groups_id", "in", admin_g.ids)]])
        elif role_filter == "manager":
            domain = expression.AND(
                [domain, [("groups_id", "in", manager_g.ids), ("groups_id", "not in", admin_g.ids)]]
            )
        elif role_filter == "technician":
            domain = expression.AND(
                [domain, [("groups_id", "in", tech_g.ids), ("groups_id", "not in", admin_g.ids)]]
            )
        rows = Users.search_read(
            domain,
            ["id", "name", "login", "email", "active", "pm_role", "pm_password_reset_required"],
            order="name",
            limit=200,
        )
        for r in rows:
            r["role"] = r.get("pm_role") or False
        return rows

    @api.model
    def create_pm_user(self, values):
        self._check_pm_admin()
        role = values.get("role")
        if role not in ("manager", "technician"):
            raise ValidationError("Admins can create Maintenance Manager or Technician accounts only.")
        login = (values.get("login") or "").strip()
        name = (values.get("name") or "").strip()
        email = (values.get("email") or "").strip()
        password = values.get("password") or ""
        if not login or not name:
            raise ValidationError("Name and login are required.")
        if len(password) < 6:
            raise ValidationError("Initial password must be at least 6 characters.")
        Users = self.env["res.users"].sudo()
        if Users.search_count([("login", "=", login)]):
            raise ValidationError("A user with this login already exists.")
        partner = self.env["res.partner"].sudo().create({"name": name, "email": email or False})
        user = Users.with_context(no_reset_password=True).create(
            {
                "name": name,
                "login": login,
                "email": email or False,
                "partner_id": partner.id,
                "active": bool(values.get("active", True)),
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.companies.ids)],
            }
        )
        user._pm_assign_role_groups(role)
        user.sudo().write({"password": password})
        user.write({"pm_password_reset_required": True})
        return user.read(["id", "name", "login", "email", "active", "pm_role"])[0]

    @api.model
    def update_pm_user(self, user_id, values):
        self._check_pm_admin()
        user = self.env["res.users"].sudo().browse(int(user_id))
        if not user.exists() or not user._is_pm_application_user():
            raise AccessError("User is not a PM application account.")
        if user.id == self.env.uid and values.get("active") is False:
            raise ValidationError("You cannot deactivate your own account.")
        if user.has_group(GROUP_PM_ADMIN) and values.get("role") in ("manager", "technician"):
            raise ValidationError("Cannot demote a PM Administrator from this screen.")
        writes = {}
        if "name" in values:
            writes["name"] = values["name"]
            user.partner_id.sudo().write({"name": values["name"]})
        if "email" in values:
            writes["email"] = values["email"]
        if "active" in values:
            writes["active"] = bool(values["active"])
        if writes:
            user.write(writes)
        role = values.get("role")
        if role in ("manager", "technician") and not user.has_group(GROUP_PM_ADMIN):
            user._pm_assign_role_groups(role)
        new_password = values.get("password")
        if new_password:
            self.env["res.users"].pm_change_password(user.id, new_password)
        return user.read(["id", "name", "login", "email", "active", "pm_role"])[0]

    @api.model
    def get_dashboard_full(self, filters=None):
        """Enhanced dashboard: KPIs, chart series, alerts, recent activity."""
        base = self.get_dashboard_kpis(filters)
        if base.get("role") == "technician":
            Wo = self.env["pm.work.order"]
            uid = self.env.user.id
            wo_dom = expression.AND([self._domain_company(), [("user_id", "=", uid)]])
            alerts = Wo.search_read(
                expression.AND([wo_dom, [("state", "in", ("overdue", "rework"))]]),
                ["id", "name", "state", "date_due", "equipment_id"],
                limit=15,
                order="date_due asc",
            )
            return {**base, "charts": {}, "alerts": alerts, "activity": []}
        self._check_manager()
        filters = filters or {}
        Wo = self.env["pm.work.order"].sudo()
        Schedule = self.env["pm.schedule"].sudo()
        Audit = self.env["pm.audit.log"].sudo()
        wo_dom = self._domain_company()
        sched_dom = self._domain_company()
        if filters.get("property_location"):
            loc = filters["property_location"].strip()
            if loc:
                wo_dom = expression.AND([wo_dom, [("property_location", "ilike", loc)]])
                sched_dom = expression.AND([sched_dom, [("property_location", "ilike", loc)]])
        by_status = {}
        for st in (
            "scheduled", "assigned", "in_progress", "pending_inspection",
            "completed", "overdue", "rework",
        ):
            by_status[st] = Wo.search_count(expression.AND([wo_dom, [("state", "=", st)]]))
        today = fields.Date.today()
        week_labels = []
        completed_series = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            week_labels.append(fields.Date.to_string(d))
            completed_series.append(
                Wo.search_count(
                    expression.AND(
                        [wo_dom, [("state", "=", "completed"), ("date_scheduled", "=", d)]]
                    )
                )
            )
        alerts = Schedule.search_read(
            expression.AND([sched_dom, [("state", "in", ("overdue", "due"))]]),
            ["id", "date_planned", "state", "equipment_id", "plan_id"],
            limit=20,
            order="date_planned asc",
        )
        activity = Audit.search_read(
            expression.AND([self._domain_company(), []]),
            ["create_date", "user_id", "action_type", "details", "res_model"],
            limit=25,
            order="create_date desc",
        )
        return {
            **base,
            "charts": {
                "wo_by_status": by_status,
                "completed_last_7_days": {"labels": week_labels, "values": completed_series},
            },
            "alerts": alerts,
            "activity": activity,
        }

    @api.model
    def get_plan_kpis(self):
        self._check_manager()
        Plan = self.env["pm.plan"].sudo()
        dom = expression.AND([self._domain_company(), []])
        return {
            "total": Plan.search_count(dom),
            "active": Plan.search_count(expression.AND([dom, [("state", "=", "active")]])),
            "draft": Plan.search_count(expression.AND([dom, [("state", "=", "draft")]])),
            "inactive": Plan.search_count(
                expression.AND([dom, [("state", "in", ("inactive", "expired", "review"))]])
            ),
        }

    @api.model
    def create_schedule(self, values):
        self._check_manager()
        plan_id = int(values.get("plan_id"))
        plan = self.env["pm.plan"].browse(plan_id)
        if not plan.exists():
            raise ValidationError("Plan not found.")
        date_planned = values.get("date_planned")
        if not date_planned:
            raise ValidationError("Planned date is required.")
        equip_id = values.get("equipment_id") or (plan.equipment_id.id if plan.equipment_id else False)
        if not equip_id:
            raise ValidationError("Equipment is required.")
        date_due = values.get("date_due") or plan._due_date_from_planned(fields.Date.from_string(date_planned))
        conflict = self.check_schedule_conflict(plan_id, equip_id, date_planned)
        if conflict.get("has_conflict"):
            raise ValidationError(conflict.get("message", "Schedule conflict detected."))
        Schedule = self.env["pm.schedule"]
        sched = Schedule.create(
            plan._prepare_schedule_vals(
                fields.Date.from_string(date_planned),
                date_due if isinstance(date_due, date) else fields.Date.from_string(date_due),
                equipment=self.env["maintenance.equipment"].browse(equip_id),
            )
        )
        if values.get("create_work_order", True) and plan.auto_generate_work_orders:
            wo = self.env["pm.work.order"].create(
                plan._prepare_work_order_vals(
                    sched.date_planned,
                    sched.date_due,
                    schedule=sched,
                    equipment=sched.equipment_id,
                )
            )
            sched.work_order_id = wo.id
        return sched.read(["id", "date_planned", "state", "work_order_id"])[0]

    @api.model
    def check_schedule_conflict(self, plan_id, equipment_id, date_planned):
        self._check_manager()
        d = fields.Date.from_string(date_planned) if isinstance(date_planned, str) else date_planned
        existing = self.env["pm.schedule"].search_count(
            expression.AND(
                [
                    self._domain_company(),
                    [
                        ("plan_id", "=", int(plan_id)),
                        ("equipment_id", "=", int(equipment_id)),
                        ("date_planned", "=", d),
                    ],
                    [("state", "not in", ("cancelled", "skipped", "completed"))],
                ]
            )
        )
        if existing:
            return {
                "has_conflict": True,
                "message": "A schedule already exists for this plan, asset and date.",
            }
        return {"has_conflict": False, "message": ""}

    @api.model
    def get_task_kpis(self):
        self._check_pm_user()
        Wo = self.env["pm.work.order"].sudo()
        dom = expression.AND([self._domain_company(), []])
        if pm_is_technician_only(self.env):
            dom = expression.AND([dom, [("user_id", "=", self.env.user.id)]])
        open_states = ("scheduled", "assigned", "in_progress", "on_hold", "rework", "overdue")
        return {
            "open": Wo.search_count(expression.AND([dom, [("state", "in", open_states)]])),
            "in_progress": Wo.search_count(expression.AND([dom, [("state", "=", "in_progress")]])),
            "overdue": Wo.search_count(expression.AND([dom, [("state", "=", "overdue")]])),
            "due_today": Wo.search_count(
                expression.AND([dom, [("date_due", "=", fields.Date.today()), ("state", "in", open_states)]])
            ),
        }

    @api.model
    def report_issue(self, values):
        """Create corrective maintenance request linked to a PM work order."""
        self._check_pm_user()
        wo_id = int(values.get("work_order_id"))
        wo = self.env["pm.work.order"].browse(wo_id)
        if pm_is_technician_only(self.env) and wo.user_id != self.env.user:
            raise AccessError("You can only report issues on your assigned work orders.")
        Mr = self.env["maintenance.request"]
        team = wo.team_id or wo.equipment_id.maintenance_team_id
        vals = {
            "name": values.get("name") or f"Issue: {wo.name}",
            "equipment_id": wo.equipment_id.id,
            "maintenance_type": "corrective",
            "priority": {"low": "1", "medium": "2", "high": "3", "critical": "3"}.get(
                values.get("severity", "medium"), "2"
            ),
            "description": values.get("description") or "",
            "pm_work_order_id": wo.id,
            "issue_category": values.get("issue_category") or "other",
            "severity": values.get("severity") or "medium",
            "technician_user_id": self.env.user.id,
        }
        if team:
            vals["maintenance_team_id"] = team.id
        req = Mr.create(vals)
        return req.read(
            ["id", "name", "stage_id", "equipment_id", "severity", "issue_category", "pm_work_order_id"]
        )[0]

    @api.model
    def get_maintenance_requests(self, domain=None, limit=80):
        self._check_manager()
        Mr = self.env["maintenance.request"].sudo()
        dom = domain or []
        dom = expression.AND([dom, [("pm_work_order_id", "!=", False)]])
        return Mr.search_read(
            dom,
            [
                "id",
                "name",
                "equipment_id",
                "stage_id",
                "severity",
                "issue_category",
                "priority",
                "create_date",
                "pm_work_order_id",
            ],
            limit=limit,
            order="create_date desc",
        )

    @api.model
    def get_request_detail(self, request_id):
        self._check_manager()
        req = self.env["maintenance.request"].sudo().browse(int(request_id))
        if not req.exists():
            raise ValidationError("Request not found.")
        data = req.read(
            [
                "id",
                "name",
                "equipment_id",
                "stage_id",
                "severity",
                "issue_category",
                "priority",
                "description",
                "pm_work_order_id",
                "technician_user_id",
                "schedule_date",
                "close_date",
            ]
        )[0]
        wo = req.pm_work_order_id
        if wo:
            data["work_order"] = wo.read(["id", "name", "state", "user_id", "date_scheduled"])[0]
        return data

    @api.model
    def update_maintenance_request(self, request_id, values):
        self._check_manager()
        req = self.env["maintenance.request"].sudo().browse(int(request_id))
        allowed = {
            "name", "description", "severity", "issue_category",
            "priority", "schedule_date", "stage_id",
        }
        writes = {k: v for k, v in (values or {}).items() if k in allowed}
        if writes:
            req.write(writes)
        return self.get_request_detail(request_id)

    @api.model
    def get_history_kpis(self, filters=None):
        self._check_manager()
        filters = filters or {}
        Wo = self.env["pm.work.order"].sudo()
        domain = expression.AND([self._domain_company(), [("state", "=", "completed")]])
        if filters.get("date_from"):
            domain = expression.AND([domain, [("date_scheduled", ">=", filters["date_from"])]])
        if filters.get("date_to"):
            domain = expression.AND([domain, [("date_scheduled", "<=", filters["date_to"])]])
        completed = Wo.search(domain)
        return {
            "completed_count": len(completed),
            "total_cost": sum(completed.mapped("total_cost")),
            "avg_duration": round(
                sum(completed.mapped("duration_actual")) / len(completed), 2
            ) if completed else 0.0,
            "currency": self.env.company.currency_id.name,
        }

    @api.model
    def get_reports_extended(self, filters=None):
        base = self.get_reports(filters)
        self._check_manager()
        filters = filters or {}
        Wo = self.env["pm.work.order"].sudo()
        domain = self._domain_company()
        if filters.get("date_from"):
            domain = expression.AND([domain, [("date_scheduled", ">=", filters["date_from"])]])
        if filters.get("date_to"):
            domain = expression.AND([domain, [("date_scheduled", "<=", filters["date_to"])]])
        records = Wo.search(domain)
        by_type = {}
        for wo in records:
            mt = wo.maintenance_type or "other"
            by_type[mt] = by_type.get(mt, 0) + 1
        by_month = {}
        for wo in records:
            if wo.date_scheduled:
                key = wo.date_scheduled.strftime("%Y-%m")
                by_month[key] = by_month.get(key, 0) + 1
        cost_total = sum(records.filtered(lambda w: w.state == "completed").mapped("total_cost"))
        return {
            **base,
            "by_maintenance_type": by_type,
            "by_month": by_month,
            "cost_total_completed": cost_total,
        }

    @api.model
    def get_config_tabs(self):
        self._check_manager()
        cfg = self.env["pm.configuration"].get_config()
        row = cfg.read()[0]
        rules = cfg.escalation_rule_ids.read(
            ["id", "name", "severity", "days_overdue", "notify_user_id", "notify_email", "notify_activity", "active"]
        )
        templates = self.env["pm.checklist.template"].search_read(
            expression.AND([self._domain_company(), []]),
            ["id", "name", "active", "description"],
            limit=100,
        )
        reading_tpl = self.env["pm.asset.reading.template"].search_read(
            expression.AND([self._domain_company(), []]),
            ["id", "name", "min_value", "max_value", "unit", "equipment_id"],
            limit=100,
        )
        return {
            "general": {
                "default_lead_days": row.get("default_lead_days"),
                "default_task_duration": row.get("default_task_duration"),
                "reminder_days": row.get("reminder_days"),
                "overdue_grace_days": row.get("overdue_grace_days"),
                "escalation_overdue_days": row.get("escalation_overdue_days"),
            },
            "notifications": {
                "notification_email": row.get("notification_email"),
                "notification_activity": row.get("notification_activity"),
                "notification_sms": row.get("notification_sms"),
                "notify_on_schedule": row.get("notify_on_schedule"),
                "notify_on_overdue": row.get("notify_on_overdue"),
                "notify_on_completion": row.get("notify_on_completion"),
            },
            "escalation": {"rules": rules, "notes": row.get("escalation_matrix_notes") or ""},
            "sequences": {
                "sequence_prefix_wo": row.get("sequence_prefix_wo"),
                "sequence_padding_wo": row.get("sequence_padding_wo"),
            },
            "defaults": {
                "mandatory_checklist_default": row.get("mandatory_checklist_default"),
                "auto_generate_wo_default": row.get("auto_generate_wo_default"),
                "auto_next_schedule_default": row.get("auto_next_schedule_default"),
            },
            "checklist_templates": templates,
            "reading_templates": reading_tpl,
            "config_id": cfg.id,
        }

    @api.model
    def save_config_full(self, payload):
        self._check_manager()
        payload = payload or {}
        cfg = self.env["pm.configuration"].get_config()
        flat = {}
        for section in ("general", "notifications", "sequences", "defaults"):
            flat.update(payload.get(section) or {})
        if "notes" in (payload.get("escalation") or {}):
            flat["escalation_matrix_notes"] = payload["escalation"]["notes"]
        if flat:
            cfg.write(flat)
        rules = (payload.get("escalation") or {}).get("rules")
        if rules is not None:
            Rule = self.env["pm.escalation.rule"]
            existing_ids = set(cfg.escalation_rule_ids.ids)
            keep = set()
            for r in rules:
                rid = r.get("id")
                vals = {
                    "configuration_id": cfg.id,
                    "name": r.get("name") or "Rule",
                    "severity": r.get("severity") or "medium",
                    "days_overdue": r.get("days_overdue") or 1,
                    "notify_user_id": r.get("notify_user_id") or False,
                    "notify_email": bool(r.get("notify_email", True)),
                    "notify_activity": bool(r.get("notify_activity", True)),
                    "active": bool(r.get("active", True)),
                }
                if rid and rid in existing_ids:
                    Rule.browse(rid).write(vals)
                    keep.add(rid)
                else:
                    new_r = Rule.create(vals)
                    keep.add(new_r.id)
            unlink = existing_ids - keep
            if unlink:
                Rule.browse(list(unlink)).unlink()
        return self.get_config_tabs()

    @api.model
    def manage_checklist_template(self, action, values=None, template_id=None):
        self._check_manager()
        Template = self.env["pm.checklist.template"]
        Item = self.env["pm.checklist.item"]
        values = values or {}
        if action == "list":
            return Template.search_read(
                expression.AND([self._domain_company(), []]),
                ["id", "name", "active", "description"],
                limit=100,
            )
        if action == "create":
            tid = Template.create(
                {
                    "name": values.get("name") or "Checklist",
                    "description": values.get("description"),
                    "company_id": self.env.company.id,
                }
            ).id
            for it in values.get("items") or []:
                Item.create(
                    {
                        "template_id": tid,
                        "name": it.get("name") or "Item",
                        "mandatory": bool(it.get("mandatory", True)),
                        "sequence": it.get("sequence") or 10,
                    }
                )
            return Template.browse(tid).read(["id", "name"])[0]
        if action == "update" and template_id:
            tpl = Template.browse(int(template_id))
            tpl.write({k: v for k, v in values.items() if k in ("name", "description", "active")})
            return tpl.read(["id", "name"])[0]
        if action == "delete" and template_id:
            Template.browse(int(template_id)).unlink()
            return {"deleted": True}
        raise ValidationError("Unknown checklist template action.")
