# Part of Preventive Maintenance Management.

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .pm_access import GROUP_PM_ADMIN, GROUP_PM_MANAGER, GROUP_PM_TECHNICIAN


class ResUsers(models.Model):
    _inherit = "res.users"

    pm_password_reset_required = fields.Boolean(
        string="PM: Must Change Password",
        help="When set, the PM app reminds the user to change their password after first login.",
    )

    pm_role = fields.Selection(
        [
            ("admin", "PM Admin"),
            ("manager", "Maintenance Manager"),
            ("technician", "Technician"),
        ],
        string="PM Application Role",
        compute="_compute_pm_role",
        search="_search_pm_role",
    )

    def _compute_pm_role(self):
        admin_g = self.env.ref(GROUP_PM_ADMIN, raise_if_not_found=False)
        manager_g = self.env.ref(GROUP_PM_MANAGER, raise_if_not_found=False)
        tech_g = self.env.ref(GROUP_PM_TECHNICIAN, raise_if_not_found=False)
        for user in self:
            role = False
            if admin_g and admin_g in user.groups_id:
                role = "admin"
            elif manager_g and manager_g in user.groups_id:
                role = "manager"
            elif tech_g and tech_g in user.groups_id:
                role = "technician"
            user.pm_role = role

    @api.model
    def _search_pm_role(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            return []
        admin_g = self.env.ref(GROUP_PM_ADMIN, raise_if_not_found=False)
        manager_g = self.env.ref(GROUP_PM_MANAGER, raise_if_not_found=False)
        tech_g = self.env.ref(GROUP_PM_TECHNICIAN, raise_if_not_found=False)
        group_map = {"admin": admin_g, "manager": manager_g, "technician": tech_g}
        if operator == "=":
            g = group_map.get(value)
            return [("groups_id", "in", g.ids)] if g else [("id", "=", 0)]
        if operator == "!=":
            g = group_map.get(value)
            return [("groups_id", "not in", g.ids)] if g else []
        return []

    def _is_pm_application_user(self):
        self.ensure_one()
        refs = [
            self.env.ref(GROUP_PM_ADMIN, raise_if_not_found=False),
            self.env.ref(GROUP_PM_MANAGER, raise_if_not_found=False),
            self.env.ref(GROUP_PM_TECHNICIAN, raise_if_not_found=False),
        ]
        pm_groups = [g for g in refs if g]
        return any(g in self.groups_id for g in pm_groups)

    def _pm_assign_role_groups(self, role):
        """Mutually exclusive manager vs technician; admin receives manager + technician implied."""
        self.ensure_one()
        admin_g = self.env.ref(GROUP_PM_ADMIN)
        manager_g = self.env.ref(GROUP_PM_MANAGER)
        tech_g = self.env.ref(GROUP_PM_TECHNICIAN)
        internal = self.env.ref("base.group_user")
        cmds = [(3, admin_g.id), (3, manager_g.id), (3, tech_g.id)]
        if role == "admin":
            cmds += [(4, internal.id), (4, admin_g.id)]
        elif role == "manager":
            cmds += [(4, internal.id), (4, manager_g.id)]
        elif role == "technician":
            cmds += [(4, internal.id), (4, tech_g.id)]
        else:
            raise ValidationError("Unknown PM role.")
        self.write({"groups_id": cmds})

    @api.model
    def pm_change_password(self, user_id, new_password):
        """Secure password change for PM-managed users (admin callers only)."""
        if not self.env.user.has_group(GROUP_PM_ADMIN):
            raise AccessError("Only PM Admins can reset PM user passwords.")
        if not new_password or len(new_password) < 6:
            raise ValidationError("Password must be at least 6 characters.")
        user = self.browse(int(user_id))
        if not user.exists() or not user._is_pm_application_user():
            raise AccessError("This user is not managed by Preventive Maintenance.")
        user.sudo().write({"password": new_password})
        user.sudo().write({"pm_password_reset_required": True})
        return True

    @api.model
    def pm_ack_password_changed(self):
        """Clear forced reset flag after user changes password via standard Odoo."""
        self.env.user.write({"pm_password_reset_required": False})
        return True
