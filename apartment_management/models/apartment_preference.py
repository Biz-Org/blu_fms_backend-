from odoo import fields, models


class ApartmentPreference(models.Model):
    _name = "apartment.preference"
    _description = "Apartment Preference"
    _rec_name = "user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    email_on = fields.Boolean(default=True)
    sms_on = fields.Boolean(default=True)
    push_on = fields.Boolean(default=False)
    two_factor = fields.Boolean(default=True)
    password_changed = fields.Char(default="Last changed 30 days ago")
