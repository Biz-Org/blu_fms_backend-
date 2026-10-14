# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _


class ComplianceStateMixin(models.AbstractModel):
    _name = "compliance.state.mixin"
    _description = "Controlled Compliance state transitions"

    _ca_state_transitions = {}

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.context.get("ca_allow_state_write")
            and not self.env.su
        ):
            changing = self.filtered(lambda rec: rec.state != vals["state"])
            if changing:
                raise UserError(_("Use the workflow actions to change record state."))
        return super().write(vals)

    def _ca_set_state(self, new_state):
        allowed = self._ca_state_transitions
        for record in self:
            if new_state == record.state:
                continue
            destinations = allowed.get(record.state, set())
            if new_state not in destinations:
                raise UserError(
                    _("Cannot change %(name)s from %(current)s to %(target)s.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                        "target": new_state,
                    }
                )
        self.with_context(ca_allow_state_write=True).write({"state": new_state})
        return True


class ComplianceScopedMixin(models.AbstractModel):
    """Location and assignment fields shared by transactional compliance records.

    property/building/area are INTEGRATION PLACEHOLDERS for FMS Property
    Management (#2). site_id aliases property_id until Site exists.
    """

    _name = "compliance.scoped.mixin"
    _description = "Compliance scoped record"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    property_id = fields.Many2one(
        "compliance.property",
        ondelete="restrict",
        index=True,
        check_company=True,
        help="INTEGRATION PLACEHOLDER: retarget to FMS Property Management.",
    )
    building_id = fields.Many2one(
        "compliance.building",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('property_id', '=', property_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS building/tower.",
    )
    area_id = fields.Many2one(
        "compliance.area",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('building_id', '=', building_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS floor/zone/area.",
    )
    site_id = fields.Many2one(
        "compliance.property",
        string="Site",
        related="property_id",
        store=True,
        index=True,
        help="INTEGRATION PLACEHOLDER: site currently aliases property.",
    )
    department_id = fields.Char(
        string="Department",
        index=True,
        help="INTEGRATION PLACEHOLDER: future Workforce/Admin department.",
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        index=True,
        ondelete="restrict",
        tracking=True,
    )

    @api.constrains("building_id", "property_id")
    def _ca_check_building_property(self):
        for record in self:
            if (
                record.building_id
                and record.property_id
                and record.building_id.property_id != record.property_id
            ):
                raise ValidationError(_("Building must belong to the selected property."))

    @api.constrains("area_id", "building_id")
    def _ca_check_area_building(self):
        for record in self:
            if (
                record.area_id
                and record.building_id
                and record.area_id.building_id != record.building_id
            ):
                raise ValidationError(_("Area must belong to the selected building."))

    def _ca_require_manager(self, message=None):
        if self.env.su:
            return True
        if not self.env.user._ca_is_compliance_manager():
            raise AccessError(
                message or _("Only a Compliance Manager can perform this action.")
            )
        return True

    def _ca_require_groups(self, xmlids, message=None):
        if self.env.su:
            return True
        if not any(self.env.user.has_group(xmlid) for xmlid in xmlids):
            raise AccessError(message or _("You are not allowed to perform this action."))
        return True

    def _ca_copy_scope_from(self, origin):
        if not origin:
            return
        vals = {}
        if not self.company_id and origin.company_id:
            vals["company_id"] = origin.company_id.id
        if not self.property_id and getattr(origin, "property_id", False):
            vals["property_id"] = origin.property_id.id
        if not self.building_id and getattr(origin, "building_id", False):
            vals["building_id"] = origin.building_id.id
        if not self.area_id and getattr(origin, "area_id", False):
            vals["area_id"] = origin.area_id.id
        if not self.assigned_user_id and getattr(origin, "assigned_user_id", False):
            vals["assigned_user_id"] = origin.assigned_user_id.id
        if vals:
            self.write(vals)
