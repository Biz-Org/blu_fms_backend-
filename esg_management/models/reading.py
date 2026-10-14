from odoo import fields, models


class EsgReading(models.Model):
    _name = "esg.reading"
    _description = "ESG Meter Reading"
    _order = "date desc, id desc"

    property_id = fields.Many2one("property.property", required=True, ondelete="cascade")
    building_id = fields.Many2one("property.building", ondelete="set null")
    metric = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("waste", "Waste Diversion"),
            ("renewable", "Renewable Mix"),
        ],
        required=True,
        index=True,
    )
    date = fields.Date(required=True, index=True)
    value = fields.Float(required=True)
    unit = fields.Char()
    scope = fields.Selection(
        [("1", "Scope 1"), ("2", "Scope 2"), ("3", "Scope 3")],
        string="Emission Scope",
    )
    peak = fields.Boolean(string="Peak Hours")
    segment = fields.Selection(
        [
            ("office", "Office"),
            ("warehouse", "Warehouse"),
            ("manufacturing", "Manufacturing"),
            ("logistics", "Logistics"),
            ("other", "Other"),
        ],
        default="office",
    )
    note = fields.Char()
