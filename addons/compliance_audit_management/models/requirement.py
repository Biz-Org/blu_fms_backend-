# -*- coding: utf-8 -*-

from odoo import fields, models

from .constants import COMPLIANCE_CATEGORIES


class ComplianceRequirement(models.Model):
    _name = "compliance.requirement"
    _description = "Statutory Compliance Requirement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(index=True)
    category = fields.Selection(COMPLIANCE_CATEGORIES, required=True, default="other", tracking=True)
    description = fields.Html()
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    regulatory_authority = fields.Char()
    note = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Requirement code must be unique per company.",
    )
