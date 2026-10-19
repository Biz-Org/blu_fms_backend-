from odoo import fields, models


class ApartmentMaintenance(models.Model):
    _name = "apartment.maintenance"
    _description = "Apartment Maintenance"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    unit_id = fields.Many2one("property.unit", required=True, ondelete="cascade", index=True, tracking=True)
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    tenant_id = fields.Many2one(related="unit_id.tenant_id", store=True)
    state = fields.Selection(
        [("open", "Open"), ("progress", "In Progress"), ("scheduled", "Scheduled"), ("done", "Done")],
        default="open",
        required=True,
        tracking=True,
    )
    category = fields.Char()
    description = fields.Text()
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("emergency", "Emergency")],
        default="medium",
        tracking=True,
    )
    access_date = fields.Date()
    access_slot = fields.Char()
    scheduled_date = fields.Date()
    notes = fields.Text()
    attachment_name = fields.Char()
    attachment = fields.Binary(attachment=True)
