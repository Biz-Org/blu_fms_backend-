# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .constants import CHECKLIST_CATEGORIES


class FireSafetyChecklistTemplate(models.Model):
    _name = "fire.safety.checklist.template"
    _description = "Fire & Safety Checklist Template"
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
    inspection_type = fields.Selection(
        [
            ("fire_inspection", "Fire Inspection"),
            ("safety_audit", "Safety Audit"),
            ("both", "Both"),
        ],
        default="both",
        required=True,
    )
    active = fields.Boolean(default=True)
    item_ids = fields.One2many("fire.safety.checklist.item", "template_id")
    item_count = fields.Integer(compute="_compute_item_count")
    note = fields.Text()

    @api.depends("item_ids")
    def _compute_item_count(self):
        for template in self:
            template.item_count = len(template.item_ids)

    def action_copy_items_to_inspection(self, inspection):
        self.ensure_one()
        Line = self.env["fire.safety.inspection.line"]
        for item in self.item_ids.sorted("sequence"):
            Line.create(
                {
                    "inspection_id": inspection.id,
                    "item_id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "sequence": item.sequence,
                    "required": item.required,
                }
            )
        return True


class FireSafetyChecklistItem(models.Model):
    _name = "fire.safety.checklist.item"
    _description = "Fire & Safety Checklist Item"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "fire.safety.checklist.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="template_id.company_id", store=True)
    name = fields.Char(required=True)
    category = fields.Selection(CHECKLIST_CATEGORIES)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    guidance = fields.Text()
