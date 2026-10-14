from odoo import api, fields, models


class ApartmentPayment(models.Model):
    _name = "apartment.payment"
    _description = "Apartment Payment"
    _order = "date desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True)
    unit_id = fields.Many2one("property.unit", required=True, ondelete="cascade", index=True)
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    tenant_id = fields.Many2one(related="unit_id.tenant_id", store=True)
    tenancy_id = fields.Many2one("property.tenancy", ondelete="set null")
    amount = fields.Float(required=True)
    date = fields.Date(required=True, default=fields.Date.today, index=True)
    state = fields.Selection(
        [("paid", "Paid"), ("due", "Due"), ("pending", "Pending"), ("failed", "Failed")],
        default="due",
        required=True,
        index=True,
    )
    payment_type = fields.Selection(
        [
            ("rent", "Rent"),
            ("maintenance", "Maintenance"),
            ("utility", "Utility"),
            ("deposit", "Deposit"),
            ("other", "Other"),
        ],
        default="rent",
        required=True,
    )
    method = fields.Char(default="Bank ACH")
    reference = fields.Char(copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.reference:
                rec.reference = f"RTX-{rec.id:04d}"
        return records
