# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.translate import _


class IntegrationIotScopedMixin(models.AbstractModel):
    """Location fields shared by IoT transactional records.

    property/building/area are INTEGRATION PLACEHOLDERS for FMS Property
    Management (#2). They are module-scoped and must be retargeted later.
    """

    _name = "integration.iot.scoped.mixin"
    _description = "IoT scoped record"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    property_id = fields.Many2one(
        "integration.iot.property",
        ondelete="restrict",
        index=True,
        check_company=True,
        help="INTEGRATION PLACEHOLDER: retarget to FMS Property Management.",
    )
    building_id = fields.Many2one(
        "integration.iot.building",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('property_id', '=', property_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS building/tower.",
    )
    area_id = fields.Many2one(
        "integration.iot.area",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('building_id', '=', building_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS floor/zone/room/area.",
    )

    def _iot_location_label(self):
        self.ensure_one()
        parts = [
            self.property_id.name,
            self.building_id.name,
            self.area_id.name,
        ]
        return " / ".join([part for part in parts if part])

    @api.constrains("building_id", "property_id")
    def _iot_check_building_property(self):
        for record in self:
            if (
                record.building_id
                and record.property_id
                and record.building_id.property_id != record.property_id
            ):
                raise ValidationError(_("Building must belong to the selected property."))

    @api.constrains("area_id", "building_id")
    def _iot_check_area_building(self):
        for record in self:
            if (
                record.area_id
                and record.building_id
                and record.area_id.building_id != record.building_id
            ):
                raise ValidationError(_("Area must belong to the selected building."))

    def _iot_require_admin(self, message=None):
        if self.env.su:
            return True
        if not self.env.user._iot_is_integration_admin():
            raise AccessError(
                message or _("Only an Integration Admin can perform this action.")
            )
        return True

    def _iot_matches_location(self, other):
        """True when this record's location is empty or matches `other`."""
        self.ensure_one()
        if self.property_id and other.property_id and self.property_id != other.property_id:
            return False
        if self.building_id and other.building_id and self.building_id != other.building_id:
            return False
        if self.area_id and other.area_id and self.area_id != other.area_id:
            return False
        return True
