# Part of Preventive Maintenance Management.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PmAssetReadingTemplate(models.Model):
    _name = "pm.asset.reading.template"
    _description = "PM Asset Reading Template"
    _order = "name"

    name = fields.Char(required=True)
    equipment_id = fields.Many2one("maintenance.equipment", string="Asset", ondelete="cascade", index=True)
    min_value = fields.Float(string="Minimum")
    max_value = fields.Float(string="Maximum")
    unit = fields.Char(string="Unit")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    @api.constrains("min_value", "max_value")
    def _check_min_max(self):
        for rec in self:
            if rec.max_value and rec.min_value > rec.max_value:
                raise ValidationError("Minimum cannot exceed maximum.")


class PmAssetReadingResult(models.Model):
    _name = "pm.asset.reading.result"
    _description = "PM Asset Reading Result"
    _order = "id"

    work_order_id = fields.Many2one(
        "pm.work.order", required=True, ondelete="cascade", index=True
    )
    template_id = fields.Many2one("pm.asset.reading.template", ondelete="set null")
    name = fields.Char(required=True)
    min_value = fields.Float(string="Minimum")
    max_value = fields.Float(string="Maximum")
    value = fields.Float(string="Recorded Value")
    unit = fields.Char()
    is_out_of_range = fields.Boolean(compute="_compute_out_of_range", store=True)

    @api.depends("value", "min_value", "max_value")
    def _compute_out_of_range(self):
        for rec in self:
            out = False
            if rec.value is not False and rec.value is not None:
                if rec.min_value and rec.value < rec.min_value:
                    out = True
                if rec.max_value and rec.value > rec.max_value:
                    out = True
            rec.is_out_of_range = out
