# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import PRIORITY_LEVELS, REGULATORY_REPORT_STATES


class ComplianceRegulatoryReport(models.Model):
    _name = "compliance.regulatory.report"
    _description = "Regulatory Report / Submission"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "deadline desc, id desc"
    _check_company_auto = True
    _ca_state_transitions = {
        "draft": {"in_preparation", "submitted"},
        "in_preparation": {"submitted", "draft"},
        "submitted": set(),
    }

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    regulatory_authority = fields.Char(required=True, tracking=True)
    requirement_id = fields.Many2one(
        "compliance.requirement",
        ondelete="restrict",
        index=True,
        check_company=True,
    )
    reporting_period = fields.Char(required=True)
    description = fields.Html()
    owner_id = fields.Many2one(
        "res.users",
        string="Report Owner",
        default=lambda self: self.env.user,
        tracking=True,
    )
    deadline = fields.Date(required=True, tracking=True, index=True)
    priority = fields.Selection(PRIORITY_LEVELS, default="medium", required=True)
    submission_date = fields.Date(readonly=True)
    submission_reference = fields.Char()
    state = fields.Selection(
        REGULATORY_REPORT_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    is_due = fields.Boolean(compute="_compute_is_overdue")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "compliance_regulatory_attachment_rel",
        "report_id",
        "attachment_id",
        string="Supporting Documents",
    )
    acknowledgement_ids = fields.Many2many(
        "ir.attachment",
        "compliance_regulatory_ack_rel",
        "report_id",
        "attachment_id",
        string="Submission Acknowledgement",
    )

    @api.depends("deadline", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            open_state = record.state != "submitted"
            record.is_overdue = open_state and bool(record.deadline) and record.deadline < today
            record.is_due = (
                open_state
                and bool(record.deadline)
                and record.deadline >= today
                and (record.deadline - today).days <= 30
            )

    def _search_is_overdue(self, operator, value):
        # Odoo 18 evaluates boolean searches with '=' / '!='.
        positive = (
            operator in ("=", "==") and bool(value)
            or operator in ("!=", "<>") and not value
            or operator == "in" and True in set(value or []) and False not in set(value or [])
            or operator == "not in" and False in set(value or []) and True not in set(value or [])
        )
        today = fields.Date.context_today(self)
        overdue_domain = [("state", "!=", "submitted"), ("deadline", "<", today)]
        if positive:
            return overdue_domain
        return ["!"] + overdue_domain

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = (
                    self.env["ir.sequence"].next_by_code("compliance.regulatory.report") or _("New")
                )
            if vals.get("owner_id") and not vals.get("assigned_user_id"):
                vals["assigned_user_id"] = vals["owner_id"]
        return super().create(vals_list)

    def action_prepare(self):
        self._ca_require_manager()
        self._ca_set_state("in_preparation")
        return True

    def action_submit(self):
        self._ca_require_manager()
        self.write({"submission_date": fields.Date.context_today(self)})
        self._ca_set_state("submitted")
        return True

    @api.model
    def get_regulatory_kpis(self):
        """KPI strip for the Regulatory Reporting OWL screen."""
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        open_domain = [("state", "!=", "submitted")]
        due_soon = self.search_count(
            open_domain
            + [
                ("deadline", ">=", today),
                ("deadline", "<=", soon),
            ]
        )
        overdue = self.search_count(open_domain + [("deadline", "<", today)])
        in_preparation = self.search_count([("state", "=", "in_preparation")])
        submitted = self.search_count([("state", "=", "submitted")])
        return {
            "due_soon": due_soon,
            "overdue": overdue,
            "in_preparation": in_preparation,
            "submitted": submitted,
        }
