# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import COMPLIANCE_CATEGORIES


class ComplianceChecklistTemplate(models.Model):
    _name = "compliance.checklist.template"
    _description = "Compliance Checklist Template"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    category = fields.Selection(COMPLIANCE_CATEGORIES, default="other")
    requirement_ids = fields.Many2many(
        "compliance.requirement",
        "compliance_checklist_requirement_rel",
        "template_id",
        "requirement_id",
        string="Requirements",
    )
    preview_text = fields.Text(
        help="Short summary shown when selecting this template (UI checklist preview).",
    )
    active = fields.Boolean(default=True)
    item_ids = fields.One2many("compliance.checklist.item", "template_id")
    item_count = fields.Integer(compute="_compute_item_count")
    note = fields.Text()

    @api.depends("item_ids")
    def _compute_item_count(self):
        for template in self:
            template.item_count = len(template.item_ids)

    def action_copy_items_to_check(self, check):
        self.ensure_one()
        Line = self.env["compliance.check.line"]
        for item in self.item_ids.sorted("sequence"):
            Line.create(
                {
                    "check_id": check.id,
                    "item_id": item.id,
                    "name": item.name,
                    "sequence": item.sequence,
                    "required": item.required,
                }
            )
        return True

    def action_copy_items_to_audit(self, audit):
        self.ensure_one()
        Line = self.env["compliance.audit.line"]
        for item in self.item_ids.sorted("sequence"):
            Line.create(
                {
                    "audit_id": audit.id,
                    "item_id": item.id,
                    "name": item.name,
                    "sequence": item.sequence,
                    "required": item.required,
                }
            )
        return True


class ComplianceChecklistItem(models.Model):
    _name = "compliance.checklist.item"
    _description = "Compliance Checklist Item"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "compliance.checklist.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="template_id.company_id", store=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    guidance = fields.Text()
