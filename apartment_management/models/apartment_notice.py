from odoo import fields, models


class ApartmentNotice(models.Model):
    _name = "apartment.notice"
    _description = "Apartment Notice"
    _order = "date desc, id desc"

    title = fields.Char(required=True)
    body = fields.Text()
    unit_id = fields.Many2one("property.unit", ondelete="cascade", index=True)
    tenant_id = fields.Many2one("res.partner", ondelete="cascade", index=True)
    category = fields.Selection(
        [
            ("payments", "Payments"),
            ("lease", "Lease"),
            ("maintenance", "Maintenance"),
            ("documents", "Documents"),
            ("messages", "Messages"),
        ],
        default="messages",
        required=True,
        index=True,
    )
    date = fields.Datetime(default=fields.Datetime.now, index=True)
    unread = fields.Boolean(default=True)
    archived = fields.Boolean()
