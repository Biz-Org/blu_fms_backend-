# Part of Preventive Maintenance Management.

from odoo import fields, models


class PmEscalationRule(models.Model):
    _name = "pm.escalation.rule"
    _description = "PM Escalation Rule"
    _order = "sequence, id"

    configuration_id = fields.Many2one(
        "pm.configuration", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
    )
    days_overdue = fields.Integer(string="Days Overdue", default=1)
    notify_user_id = fields.Many2one("res.users", string="Notify User")
    notify_email = fields.Boolean(default=True)
    notify_activity = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
