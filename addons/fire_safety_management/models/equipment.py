# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import EQUIPMENT_CONDITIONS, EQUIPMENT_STATES, EQUIPMENT_TYPES


class FireSafetyEquipmentHistory(models.Model):
    _name = "fire.safety.equipment.history"
    _description = "Fire & Safety Equipment Service/Replacement History"
    _order = "event_date desc, id desc"

    equipment_id = fields.Many2one(
        "fire.safety.equipment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="equipment_id.company_id", store=True)
    event_type = fields.Selection(
        [
            ("service", "Service"),
            ("inspection", "Inspection"),
            ("replacement", "Replacement"),
            ("fault", "Fault"),
        ],
        required=True,
        default="service",
    )
    event_date = fields.Date(required=True, default=fields.Date.context_today)
    summary = fields.Char(required=True)
    notes = fields.Text()
    performed_by_id = fields.Many2one("res.users", default=lambda self: self.env.user)


class FireSafetyEquipment(models.Model):
    _name = "fire.safety.equipment"
    _description = "Fire & Safety Equipment"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
    ]
    _order = "code, name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, copy=False, index=True, tracking=True)
    equipment_type = fields.Selection(EQUIPMENT_TYPES, required=True, tracking=True, index=True)
    location_detail = fields.Char()
    install_date = fields.Date()
    inspection_due_date = fields.Date(index=True, tracking=True)
    service_due_date = fields.Date(index=True, tracking=True)
    expiry_date = fields.Date(index=True, tracking=True)
    condition = fields.Selection(
        EQUIPMENT_CONDITIONS,
        default="operational",
        required=True,
        tracking=True,
        help="Manual operational condition. Due/expired overlays are computed into state.",
    )
    status_as_of = fields.Date(
        default=fields.Date.context_today,
        help="Technical date used so due/expired overlays recompute overnight.",
    )
    state = fields.Selection(
        EQUIPMENT_STATES,
        compute="_compute_state",
        store=True,
        index=True,
    )
    last_inspection_date = fields.Date()
    last_service_date = fields.Date()
    notes = fields.Html()
    history_ids = fields.One2many("fire.safety.equipment.history", "equipment_id")
    reminder_activity_ids = fields.One2many(
        "mail.activity",
        "res_id",
        domain=lambda self: [("res_model", "=", self._name)],
    )

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Equipment code must be unique per company.",
    )

    @api.depends(
        "condition",
        "inspection_due_date",
        "service_due_date",
        "expiry_date",
        "status_as_of",
    )
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            as_of = record.status_as_of or today
            if record.condition in ("replaced", "faulty", "under_maintenance"):
                record.state = record.condition
            elif record.expiry_date and record.expiry_date < as_of:
                record.state = "expired"
            elif record.service_due_date and record.service_due_date <= as_of:
                record.state = "service_due"
            elif record.inspection_due_date and record.inspection_due_date <= as_of:
                record.state = "inspection_due"
            else:
                record.state = "operational"

    def action_mark_faulty(self):
        self._fs_require_safety_manager()
        self.write({"condition": "faulty"})
        self._log_history("fault", _("Marked faulty"))
        return True

    def action_mark_under_maintenance(self):
        self._fs_require_safety_manager()
        self.write({"condition": "under_maintenance"})
        self._log_history("service", _("Marked under maintenance"))
        return True

    def action_mark_replaced(self):
        self._fs_require_safety_manager()
        self.write({"condition": "replaced"})
        self._log_history("replacement", _("Marked replaced"))
        return True

    def action_mark_operational(self):
        self._fs_require_safety_manager()
        self.write({"condition": "operational"})
        return True

    def _log_history(self, event_type, summary):
        History = self.env["fire.safety.equipment.history"]
        for record in self:
            History.create(
                {
                    "equipment_id": record.id,
                    "event_type": event_type,
                    "summary": summary,
                }
            )

    @api.model
    def _cron_refresh_equipment_status(self):
        today = fields.Date.context_today(self)
        records = self.search([("condition", "!=", "replaced")])
        records.write({"status_as_of": today})
        due = records.filtered(
            lambda rec: rec.state in ("inspection_due", "service_due", "expired")
        )
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return True
        for equipment in due:
            existing = self.env["mail.activity"].search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", equipment.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("summary", "ilike", equipment.state.replace("_", " ")),
                ],
                limit=1,
            )
            if existing:
                continue
            user = equipment.assigned_user_id or self.env.ref("base.user_admin", raise_if_not_found=False)
            if not user:
                continue
            equipment.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary=_("Equipment %(code)s is %(state)s")
                % {"code": equipment.code, "state": equipment.state},
                date_deadline=today,
            )
        return True
