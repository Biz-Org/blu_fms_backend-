# -*- coding: utf-8 -*-

from odoo import fields, models


class AiCopilotDocument(models.Model):
    _name = "ai.copilot.document"
    _description = "AI Copilot Knowledge Document"
    _order = "name, id"

    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ("policy", "Policies & Procedures"),
            ("sop", "SOPs"),
            ("manual", "Facility Manuals"),
            ("safety", "Safety Guidelines"),
            ("compliance", "Compliance Documents"),
            ("equipment", "Equipment Manuals"),
            ("community", "Community Guidelines"),
            ("internal", "Internal Documents"),
        ],
        default="internal",
        required=True,
        index=True,
    )
    summary = fields.Char()
    body = fields.Text(required=True)
    restricted = fields.Boolean(
        string="Restrict to Groups",
        help="When set, only members of the allowed groups, and Copilot administrators, can read this document.",
    )
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "ai_copilot_document_group_rel",
        "document_id",
        "group_id",
        string="Allowed Groups",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
