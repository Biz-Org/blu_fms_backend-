# -*- coding: utf-8 -*-

from odoo import fields, models

from .constants import EMERGENCY_TYPES


class FireSafetyProcedure(models.Model):
    _name = "fire.safety.procedure"
    _description = "Fire & Safety Procedure"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    procedure_type = fields.Selection(EMERGENCY_TYPES, default="fire")
    active = fields.Boolean(default=True)
    summary = fields.Text()
    body = fields.Html()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_procedure_attachment_rel",
        "procedure_id",
        "attachment_id",
    )
