from odoo import api, fields, models


class ApartmentDocument(models.Model):
    _name = "apartment.document"
    _description = "Apartment Document"
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    unit_id = fields.Many2one("property.unit", ondelete="cascade", index=True)
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    tenant_id = fields.Many2one(related="unit_id.tenant_id", store=True)
    property_name = fields.Char()
    category = fields.Selection(
        [
            ("lease", "Lease"),
            ("invoice", "Invoices"),
            ("maintenance", "Maintenance"),
            ("property", "Property"),
            ("notice", "Notices"),
        ],
        default="property",
        required=True,
        index=True,
    )
    date = fields.Date(default=fields.Date.today)
    status = fields.Selection(
        [
            ("verified", "Verified"),
            ("pending", "Pending Review"),
            ("archived", "Archived"),
            ("paid", "Paid"),
        ],
        default="verified",
    )
    file = fields.Binary(attachment=True)
    file_name = fields.Char()
    size_label = fields.Char()
    uploaded_by = fields.Char()
    uploaded_user_id = fields.Many2one("res.users", default=lambda self: self.env.user, ondelete="set null")
    version = fields.Char(default="v1.0")
    tags = fields.Char()
    kind = fields.Char()
    pages = fields.Integer(default=12)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("property_name") and vals.get("unit_id"):
                unit = self.env["property.unit"].browse(vals["unit_id"])
                vals["property_name"] = unit.property_id.name if unit.property_id else False
            if not vals.get("file_name") and vals.get("name"):
                vals["file_name"] = vals["name"]
        return super().create(vals_list)
