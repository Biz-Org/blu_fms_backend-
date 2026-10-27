# -*- coding: utf-8 -*-

from odoo import fields, models

from .constants import PAYMENT_STATES, XMLID_GROUP_RESIDENT


class MobilePaymentRecord(models.Model):
    _name = "mobile.payment.record"
    _description = "Mobile Payment Record"
    _order = "create_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    description = fields.Char(required=True)
    amount = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    state = fields.Selection(PAYMENT_STATES, default="pending", required=True, index=True)
    provider_ref = fields.Char(help="External payment provider reference when configured.")
    external_model = fields.Char(index=True)
    external_id = fields.Integer(index=True)
    idempotency_key = fields.Char(index=True)

    _sql_constraints = [
        (
            "idempotency_uniq",
            "unique(idempotency_key)",
            "This payment was already recorded.",
        ),
    ]
