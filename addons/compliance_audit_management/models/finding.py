# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .constants import FINDING_STATES, SEVERITY_LEVELS


class ComplianceFinding(models.Model):
    _name = "compliance.finding"
    _description = "Compliance Finding"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "compliance.scoped.mixin",
        "compliance.state.mixin",
    ]
    _order = "id desc"
    _check_company_auto = True
    _ca_state_transitions = {
        "draft": {"confirmed", "dismissed"},
        "confirmed": {"converted", "dismissed"},
        "converted": set(),
        "dismissed": set(),
    }

    name = fields.Char(required=True, tracking=True)
    description = fields.Html()
    recommendation = fields.Html()
    severity = fields.Selection(SEVERITY_LEVELS, default="medium", required=True, tracking=True)
    state = fields.Selection(
        FINDING_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    check_id = fields.Many2one("compliance.check", ondelete="cascade", index=True)
    check_line_id = fields.Many2one("compliance.check.line", ondelete="set null")
    audit_id = fields.Many2one("compliance.audit", ondelete="cascade", index=True)
    audit_line_id = fields.Many2one("compliance.audit.line", ondelete="set null")
    requirement_id = fields.Many2one("compliance.requirement", ondelete="restrict", index=True)
    non_compliance_id = fields.Many2one(
        "compliance.non.compliance",
        readonly=True,
        copy=False,
    )
    evidence_ids = fields.Many2many(
        "ir.attachment",
        "compliance_finding_attachment_rel",
        "finding_id",
        "attachment_id",
        string="Evidence",
    )

    @api.constrains("check_id", "audit_id")
    def _check_origin(self):
        for record in self:
            if not record.check_id and not record.audit_id:
                raise ValidationError(
                    _("A finding must belong to a compliance check or an audit/inspection.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._ca_copy_scope_from(record.check_id or record.audit_id)
            if not record.requirement_id and record.check_id:
                record.requirement_id = record.check_id.requirement_id
        return records

    def action_confirm(self):
        self._ca_require_manager()
        self._ca_set_state("confirmed")
        return True

    def action_dismiss(self):
        self._ca_require_manager()
        self._ca_set_state("dismissed")
        return True

    def action_convert_to_non_compliance(self):
        self._ca_require_manager()
        NC = self.env["compliance.non.compliance"]
        for record in self:
            if record.state == "converted" and record.non_compliance_id:
                continue
            if record.state not in ("draft", "confirmed"):
                raise UserError(_("Only draft or confirmed findings can become non-compliance issues."))
            nc = NC.create(
                {
                    "name": record.name,
                    "description": record.description,
                    "severity": record.severity,
                    "requirement_id": record.requirement_id.id,
                    "finding_id": record.id,
                    "check_id": record.check_id.id,
                    "audit_id": record.audit_id.id,
                    "company_id": record.company_id.id,
                    "property_id": record.property_id.id,
                    "building_id": record.building_id.id,
                    "area_id": record.area_id.id,
                    "assigned_user_id": record.assigned_user_id.id,
                    "evidence_ids": [(6, 0, record.evidence_ids.ids)],
                }
            )
            record.non_compliance_id = nc.id
            if record.state == "draft":
                record._ca_set_state("confirmed")
            record._ca_set_state("converted")
        return True
