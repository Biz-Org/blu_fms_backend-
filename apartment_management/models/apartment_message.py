from odoo import fields, models


class ApartmentMessage(models.Model):
    _name = "apartment.message"
    _description = "Apartment Message"
    _order = "date asc, id asc"

    thread = fields.Char(required=True, index=True)
    unit_id = fields.Many2one("property.unit", ondelete="cascade", index=True)
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    tenant_id = fields.Many2one("res.partner", ondelete="set null")
    author = fields.Char()
    email = fields.Char()
    subject = fields.Char()
    tag = fields.Char()
    body = fields.Text()
    date = fields.Datetime(default=fields.Datetime.now, index=True)
    mine = fields.Boolean()
    unread = fields.Boolean()
    attachment = fields.Char()
    attachment_file = fields.Binary(attachment=True)
    voice = fields.Boolean()
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, ondelete="set null")
