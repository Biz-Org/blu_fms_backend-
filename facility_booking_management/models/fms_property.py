# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class FmsProperty(models.Model):
    _name = "fms.property"
    _description = "FMS Property"
    _order = "name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(string="Property Code", index=True)
    building = fields.Char()
    address = fields.Text()
    city = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    manager_ids = fields.Many2many(
        "res.users",
        "fms_property_manager_rel",
        "property_id",
        "user_id",
        string="Community Managers",
        help="Users allowed to manage this property and its facilities/bookings.",
    )
    resident_count = fields.Integer(compute="_compute_resident_count")

    _sql_constraints = [
        (
            "fms_property_code_company_uniq",
            "unique(code, company_id)",
            "Property code must be unique within the company.",
        ),
    ]

    @api.constrains("code")
    def _check_code_not_empty_duplicate(self):
        for rec in self:
            if not rec.code:
                continue
            duplicate = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("code", "=", rec.code),
                    ("company_id", "=", rec.company_id.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("A property with this code already exists."))

    def _compute_resident_count(self):
        Resident = self.env["fms.resident"]
        for rec in self:
            rec.resident_count = Resident.search_count([("property_id", "=", rec.id)])

    @api.model
    def _fbm_migrate_property_managers_once(self):
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("facility_booking_management.property_managers_migrated"):
            return
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin:
            for prop in self.sudo().search([]):
                if admin not in prop.manager_ids:
                    prop.manager_ids = [(4, admin.id)]
        ICP.set_param("facility_booking_management.property_managers_migrated", "1")

    @api.model
    def _is_community_manager(self):
        return self.env.user.has_group("facility_booking_management.group_facility_manager")

    @api.model
    def _is_resident(self):
        return self.env.user.has_group("facility_booking_management.group_facility_resident")

    @api.model
    def _check_community_manager_access(self):
        if not self._is_community_manager():
            raise AccessError(_("Only community managers can perform this action."))

    @api.model
    def _serialize_property(self, prop):
        return {
            "id": prop.id,
            "name": prop.name,
            "code": prop.code or "",
            "building": prop.building or "",
            "address": prop.address or "",
            "city": prop.city or "",
            "active": prop.active,
            "manager_ids": prop.manager_ids.ids,
            "manager_names": ", ".join(prop.manager_ids.mapped("name")),
            "resident_count": prop.resident_count,
        }

    @api.model
    def search_properties(self, domain=None, limit=100, offset=0, search=None):
        domain = list(domain or [])
        if search:
            domain = ["|", "|", ("name", "ilike", search), ("code", "ilike", search), ("city", "ilike", search)] + domain
        records = self.search(domain, limit=limit, offset=offset, order="name")
        return {
            "records": [self._serialize_property(r) for r in records],
            "total": self.search_count(domain),
        }

    @api.model
    def save_property_from_ui(self, values, property_id=None):
        self._check_community_manager_access()
        vals = dict(values or {})
        for key in ("manager_names", "resident_count", "id"):
            vals.pop(key, None)
        manager_ids = vals.pop("manager_ids", None)
        if vals.get("code") == "":
            vals["code"] = False
        if "active" in vals:
            vals["active"] = bool(vals["active"])

        if property_id:
            prop = self.browse(property_id)
            if not prop.exists():
                raise AccessError(_("Property not found."))
            prop.write(vals)
        else:
            if not vals.get("name"):
                raise ValidationError(_("Property name is required."))
            manager_list = list(manager_ids or [])
            if self.env.uid not in manager_list:
                manager_list.append(self.env.uid)
            vals["manager_ids"] = [(6, 0, manager_list)]
            prop = self.create(vals)
            return self._serialize_property(prop)

        if manager_ids is not None:
            manager_list = list(manager_ids)
            if self.env.uid not in manager_list:
                manager_list.append(self.env.uid)
            prop.manager_ids = [(6, 0, manager_list)]
        elif self.env.user not in prop.manager_ids:
            prop.manager_ids = [(4, self.env.uid)]
        return self._serialize_property(prop)
