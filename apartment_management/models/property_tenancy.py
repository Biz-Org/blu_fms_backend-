from odoo import fields, models


class PropertyTenancy(models.Model):
    _inherit = "property.tenancy"

    monthly_rent = fields.Float(string="Monthly Rent")
    security_deposit = fields.Float(string="Security Deposit")
    auto_renew = fields.Boolean(string="Auto Renew")
    renewal_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("declined", "Declined"),
        ],
        default="pending",
        required=True,
    )
    payment_method = fields.Char(default="ACH Auto pay")
    late_fee = fields.Float(default=50.0)
    notice_days = fields.Integer(default=60)
