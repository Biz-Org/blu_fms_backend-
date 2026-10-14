from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    security_clearance = fields.Selection(
        [("standard", "Standard"), ("restricted", "Restricted"), ("high", "High")],
        default="standard",
    )
    access_level = fields.Char(default="Employee")
    authorized_gate_ids = fields.Many2many("gate.gate", string="Authorized Gates")
    access_start_date = fields.Date()
    access_end_date = fields.Date()
    badge_id = fields.Char()
    face_enrolled = fields.Boolean()


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    gate_authorized = fields.Boolean(default=True)
    access_type = fields.Selection(
        [("staff", "Staff"), ("visitor", "Visitor"), ("delivery", "Delivery"), ("contractor", "Contractor")],
        default="staff",
    )
    security_level = fields.Selection([("standard", "Standard"), ("high", "High")], default="standard")
    blacklisted = fields.Boolean()
    allowed_gate_ids = fields.Many2many("gate.gate", string="Allowed Gates")
    permit_number = fields.Char()
    permit_expiry = fields.Date()
