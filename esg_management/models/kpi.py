from odoo import fields, models


class EsgKpi(models.Model):
    _name = "esg.kpi"
    _description = "Sustainability KPI"
    _order = "category, name"

    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("waste", "Waste"),
        ],
        required=True,
        default="energy",
    )
    target = fields.Float(required=True)
    actual = fields.Float()
    unit = fields.Char(required=True, default="kWh")
    direction = fields.Selection(
        [("lower", "Lower is better"), ("higher", "Higher is better")],
        default="lower",
        required=True,
    )
    metric = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("waste", "Waste Diversion"),
            ("renewable", "Renewable Mix"),
        ],
        help="When set, the portal recalculates actual from meter readings.",
    )
    scale = fields.Float(default=1.0, help="Divide the reading total by this number.")


class EsgTarget(models.Model):
    _name = "esg.target"
    _description = "Sustainability Target"
    _order = "due_date, name"

    name = fields.Char(required=True)
    subtitle = fields.Char()
    category = fields.Selection(
        [
            ("carbon", "Carbon Reduction"),
            ("water", "Water Conservation"),
            ("energy", "Energy Reduction"),
            ("waste", "Waste"),
        ],
        required=True,
        default="energy",
    )
    metric = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("waste", "Waste Diversion"),
            ("renewable", "Renewable Mix"),
        ],
        required=True,
    )
    measure = fields.Selection(
        [("total", "Total"), ("intensity", "Intensity"), ("rate", "Rate")],
        default="total",
        required=True,
    )
    direction = fields.Selection(
        [("lower", "Lower is better"), ("higher", "Higher is better")],
        default="lower",
        required=True,
    )
    baseline = fields.Float(required=True)
    target_value = fields.Float(required=True, string="Target")
    current = fields.Float()
    unit = fields.Char(required=True)
    due_date = fields.Date()


class EsgActivity(models.Model):
    _name = "esg.activity"
    _description = "ESG Activity"
    _order = "occurred_at desc, id desc"

    name = fields.Char(required=True)
    detail = fields.Char()
    occurred_at = fields.Datetime(default=fields.Datetime.now)
    metric = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("report", "Report"),
        ],
        default="energy",
    )


class EsgReport(models.Model):
    _name = "esg.report"
    _description = "ESG Report"
    _order = "report_date desc, id desc"

    name = fields.Char(required=True)
    template = fields.Selection(
        [
            ("energy", "Energy"),
            ("water", "Water"),
            ("carbon", "Carbon"),
            ("kpis", "KPIs"),
            ("performance", "ESG Performance"),
            ("targets", "Targets"),
        ],
        required=True,
        default="energy",
    )
    period_label = fields.Char(string="Period")
    property_id = fields.Many2one("property.property")
    building_id = fields.Many2one("property.building")
    report_date = fields.Date(default=fields.Date.context_today)
    status = fields.Selection(
        [("processing", "In Progress"), ("done", "Done")],
        default="done",
        required=True,
    )
