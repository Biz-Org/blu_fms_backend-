# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _


class FireSafetyStateMixin(models.AbstractModel):
    _name = "fire.safety.state.mixin"
    _description = "Controlled Fire & Safety state transitions"

    _fs_state_transitions = {}

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.context.get("fs_allow_state_write")
            and not self.env.su
        ):
            changing = self.filtered(lambda rec: rec.state != vals["state"])
            if changing:
                raise UserError(_("Use the workflow actions to change record state."))
        return super().write(vals)

    def _fs_set_state(self, new_state):
        allowed = self._fs_state_transitions
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
        self.with_context(fs_allow_state_write=True).write({"state": new_state})
        return True


class FireSafetyScopedMixin(models.AbstractModel):
    """Location and assignment fields shared by transactional FS records.

    property/building/area are INTEGRATION PLACEHOLDERS for FMS Property
    Management (#2). site_id aliases property_id until Site exists.
    department_id is a future Workforce identifier, not a master-data module.
    """

    _name = "fire.safety.scoped.mixin"
    _description = "Fire & Safety scoped record"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    property_id = fields.Many2one(
        "fire.safety.property",
        ondelete="restrict",
        index=True,
        check_company=True,
        help="INTEGRATION PLACEHOLDER: retarget to FMS Property Management.",
    )
    building_id = fields.Many2one(
        "fire.safety.building",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('property_id', '=', property_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS building/tower.",
    )
    area_id = fields.Many2one(
        "fire.safety.area",
        ondelete="restrict",
        index=True,
        check_company=True,
        domain="[('building_id', '=', building_id)]",
        help="INTEGRATION PLACEHOLDER: retarget to FMS floor/zone/area.",
    )
    site_id = fields.Many2one(
        "fire.safety.property",
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
    )

    @api.constrains("building_id", "property_id")
    def _fs_check_building_property(self):
        for record in self:
            if (
                record.building_id
                and record.property_id
                and record.building_id.property_id != record.property_id
            ):
                raise ValidationError(_("Building must belong to the selected property."))

    @api.constrains("area_id", "building_id")
    def _fs_check_area_building(self):
        for record in self:
            if (
                record.area_id
                and record.building_id
                and record.area_id.building_id != record.building_id
            ):
                raise ValidationError(_("Area must belong to the selected building."))

    def _fs_require_safety_manager(self, message=None):
        if self.env.su:
            return True
        if not self.env.user._fs_is_safety_manager():
            raise AccessError(message or _("Only a Safety Manager can perform this action."))
        return True

    def _fs_require_groups(self, xmlids, message=None):
        if self.env.su:
            return True
        if not any(self.env.user.has_group(xmlid) for xmlid in xmlids):
            raise AccessError(message or _("You are not allowed to perform this action."))
        return True
