# Part of Preventive Maintenance Management.

from odoo import fields, models


class PmChecklistTemplate(models.Model):
    _name = "pm.checklist.template"
    _description = "PM Checklist Template"
    _order = "name"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)
    description = fields.Text()
    item_ids = fields.One2many("pm.checklist.item", "template_id", string="Items")


class PmChecklistItem(models.Model):
    _name = "pm.checklist.item"
    _description = "PM Checklist Item"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "pm.checklist.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Checklist Point", required=True)
    mandatory = fields.Boolean(default=True)
    instruction = fields.Text()
