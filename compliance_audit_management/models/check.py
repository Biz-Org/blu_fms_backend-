# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import CHECK_STATES, CHECKLIST_RESULTS, REPEAT_FREQUENCIES


class ComplianceCheck(models.Model):
    _name = "compliance.check"
    _description = "Compliance Check / Activity"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "due_date, id desc"
    _check_company_auto = True
    _rec_name = "name"
    _ca_state_transitions = {
        "scheduled": {"in_progress", "pending"},
        "in_progress": {"pending", "completed"},
        "pending": {"in_progress", "completed"},
        "completed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        string="Reference",
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    requirement_id = fields.Many2one(
        "compliance.requirement",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        check_company=True,
    )
    category = fields.Selection(
        related="requirement_id.category",
        store=True,
        index=True,
    )
    template_id = fields.Many2one(
        "compliance.checklist.template",
        ondelete="restrict",
        index=True,
        check_company=True,
    )
    due_date = fields.Date(required=True, tracking=True, index=True)
    repeat = fields.Selection(REPEAT_FREQUENCIES, default="none", required=True)
    notes = fields.Text()
    state = fields.Selection(
        CHECK_STATES,
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    line_ids = fields.One2many("compliance.check.line", "check_id")
    line_count = fields.Integer(compute="_compute_line_count")
    finding_ids = fields.One2many("compliance.finding", "check_id")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_check_attachment_rel",
        "check_id",
        "attachment_id",
        string="Evidence",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = (
                record.state != "completed"
                and bool(record.due_date)
                and record.due_date < today
            )

    def _search_is_overdue(self, operator, value):
        # Odoo 19 rewrites Boolean '=' to 'in' [True] (False → 'not in').
        if operator != "in":
            return NotImplemented
        today = fields.Date.context_today(self)
        return [("state", "!=", "completed"), ("due_date", "<", today)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code("compliance.check") or _("New")
        records = super().create(vals_list)
        for record in records:
            if record.template_id and not record.line_ids:
                record.template_id.action_copy_items_to_check(record)
        return records

    def action_start(self):
        self._ca_require_manager()
        self._ca_set_state("in_progress")
        return True

    def action_mark_pending(self):
        self._ca_require_manager()
        self._ca_set_state("pending")
        return True

    def action_complete(self):
        self._ca_require_manager()
        for record in self:
            missing = record.line_ids.filtered(lambda line: line.required and not line.result)
            if missing:
                raise UserError(_("Complete all required checklist items before finishing."))
        self._ca_set_state("completed")
        return True

    @api.model
    def get_activity_kpis(self):
        """KPI strip for the Compliance Activities OWL screen."""
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(days=30)
        overdue = self.search_count(
            [("state", "!=", "completed"), ("due_date", "<", today)]
        )
        pending = self.search_count([("state", "=", "pending")])
        scheduled_30d = self.search_count(
            [
                ("state", "=", "scheduled"),
                ("due_date", ">=", today),
                ("due_date", "<=", horizon),
            ]
        )
        total = self.search_count([])
        completed = self.search_count([("state", "=", "completed")])
        completion_rate = int(round(100.0 * completed / total)) if total else 0
        return {
            "overdue": overdue,
            "pending": pending,
            "scheduled_30d": scheduled_30d,
            "completion_rate": completion_rate,
        }

    @api.model
    def get_template_preview(self, template_id):
        """Checklist item names for the create-check modal preview."""
        template = self.env["compliance.checklist.template"].browse(template_id)
        if not template.exists():
            return []
        return [
            {"id": item.id, "name": item.name, "required": item.required}
            for item in template.item_ids.sorted("sequence")
        ]


class ComplianceCheckLine(models.Model):
    _name = "compliance.check.line"
    _description = "Compliance Check Line"
    _order = "sequence, id"
    _check_company_auto = True

    check_id = fields.Many2one(
        "compliance.check",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="check_id.company_id", store=True, index=True)
    item_id = fields.Many2one("compliance.checklist.item", ondelete="set null")
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    result = fields.Selection(CHECKLIST_RESULTS)
    remarks = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_check_line_attachment_rel",
        "line_id",
        "attachment_id",
        string="Evidence",
    )
