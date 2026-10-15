# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import (
    AUDIT_KINDS,
    AUDIT_STATES,
    AUDIT_TYPES,
    CHECKLIST_RESULTS,
    INSPECTION_TYPES,
)


class ComplianceAudit(models.Model):
    _name = "compliance.audit"
    _description = "Compliance Audit / Inspection"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "date_planned desc, id desc"
    _check_company_auto = True
    _ca_state_transitions = {
        "scheduled": {"in_progress"},
        "in_progress": {"pending_review", "completed", "failed"},
        "pending_review": {"completed", "failed", "in_progress"},
        "completed": {"closed"},
        "failed": {"closed", "in_progress"},
        "closed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    kind = fields.Selection(AUDIT_KINDS, required=True, default="audit", tracking=True, index=True)
    audit_type = fields.Selection(AUDIT_TYPES, tracking=True)
    inspection_type = fields.Selection(INSPECTION_TYPES, tracking=True)
    date_planned = fields.Date(required=True, tracking=True, index=True)
    scope = fields.Text(string="Scope / Requirements")
    template_id = fields.Many2one(
        "compliance.checklist.template",
        ondelete="restrict",
        check_company=True,
    )
    notes = fields.Text()
    recommendations = fields.Html()
    outcome = fields.Text()
    state = fields.Selection(
        AUDIT_STATES,
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    line_ids = fields.One2many("compliance.audit.line", "audit_id")
    line_count = fields.Integer(compute="_compute_line_count")
    finding_ids = fields.One2many("compliance.finding", "audit_id")
    finding_count = fields.Integer(compute="_compute_finding_count")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_audit_attachment_rel",
        "audit_id",
        "attachment_id",
        string="Evidence",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.depends("finding_ids")
    def _compute_finding_count(self):
        for record in self:
            record.finding_count = len(record.finding_ids)

    @api.depends("date_planned", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        open_states = {"scheduled", "in_progress", "pending_review"}
        for record in self:
            record.is_overdue = (
                record.state in open_states
                and bool(record.date_planned)
                and record.date_planned < today
            )

    def _search_is_overdue(self, operator, value):
        # Odoo 19 rewrites Boolean '=' to 'in' [True] (False → 'not in').
        if operator != "in":
            return NotImplemented
        today = fields.Date.context_today(self)
        return [
            ("state", "in", ["scheduled", "in_progress", "pending_review"]),
            ("date_planned", "<", today),
        ]

    @api.constrains("kind", "audit_type", "inspection_type")
    def _check_type_fields(self):
        for record in self:
            if record.kind == "audit" and not record.audit_type:
                raise UserError(_("Select an audit type."))
            if record.kind == "inspection" and not record.inspection_type:
                raise UserError(_("Select an inspection type."))

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                kind = vals.get("kind", "audit")
                code = "compliance.audit" if kind == "audit" else "compliance.inspection"
                vals["reference"] = Sequence.next_by_code(code) or _("New")
        records = super().create(vals_list)
        for record in records:
            if record.template_id and not record.line_ids:
                record.template_id.action_copy_items_to_audit(record)
        return records

    def action_start(self):
        self._ca_require_manager()
        self._ca_set_state("in_progress")
        return True

    def action_pending_review(self):
        self._ca_require_manager()
        self._ca_set_state("pending_review")
        return True

    def action_complete(self):
        self._ca_require_manager()
        for record in self:
            missing = record.line_ids.filtered(lambda line: line.required and not line.result)
            if missing:
                raise UserError(_("Complete all required checklist items before finishing."))
        self._ca_set_state("completed")
        return True

    def action_fail(self):
        self._ca_require_manager()
        self._ca_set_state("failed")
        return True

    def action_close(self):
        self._ca_require_manager()
        self._ca_set_state("closed")
        return True

    @api.model
    def get_audit_kpis(self):
        """KPI strip for the Audits & Inspections OWL screen."""
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        scheduled_month = self.search_count(
            [
                ("state", "=", "scheduled"),
                ("date_planned", ">=", month_start),
                ("date_planned", "<", next_month),
            ]
        )
        in_progress = self.search_count([("state", "=", "in_progress")])
        overdue = self.search_count(
            [
                ("state", "in", ["scheduled", "in_progress", "pending_review"]),
                ("date_planned", "<", today),
            ]
        )
        total = self.search_count([])
        done = self.search_count([("state", "in", ["completed", "closed"])])
        completion_rate = int(round(100.0 * done / total)) if total else 0
        return {
            "scheduled_month": scheduled_month,
            "in_progress": in_progress,
            "overdue": overdue,
            "completion_rate": completion_rate,
        }

    @api.model
    def get_template_preview(self, template_id):
        template = self.env["compliance.checklist.template"].browse(template_id)
        if not template.exists():
            return []
        return [
            {"id": item.id, "name": item.name, "required": item.required}
            for item in template.item_ids.sorted("sequence")
        ]


class ComplianceAuditLine(models.Model):
    _name = "compliance.audit.line"
    _description = "Compliance Audit / Inspection Line"
    _order = "sequence, id"
    _check_company_auto = True

    audit_id = fields.Many2one(
        "compliance.audit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="audit_id.company_id", store=True, index=True)
    item_id = fields.Many2one("compliance.checklist.item", ondelete="set null")
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    result = fields.Selection(CHECKLIST_RESULTS)
    remarks = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_audit_line_attachment_rel",
        "line_id",
        "attachment_id",
        string="Evidence",
    )
