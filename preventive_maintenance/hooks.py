# Part of Preventive Maintenance Management.

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODULE = "preventive_maintenance"

# Dev-only default credentials (set on first install / hook when users are created)
PM_DEV_USERS = (
    {
        "login": "pm.manager",
        "name": "PM Maintenance Manager",
        "email": "pm.manager@example.com",
        "password": "PMManager@123",
        "role": "manager",
        "set_password": True,
    },
    {
        "login": "pm.technician",
        "name": "PM Technician",
        "email": "pm.technician@example.com",
        "password": "PMTech@123",
        "role": "technician",
        "set_password": True,
    },
)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _register_manager_group_xmlid_alias(env)
    _ensure_pm_groups(env)
    _configure_pm_admin_account(env)
    _ensure_dev_pm_users(env)


def _register_manager_group_xmlid_alias(env):
    """Expose xml id group_pm_manager (alias) for existing group_pm_maintenance_manager."""
    manager = env.ref(f"{MODULE}.group_pm_maintenance_manager", raise_if_not_found=False)
    if not manager:
        return
    alias = f"{MODULE}.group_pm_manager"
    existing = env.ref(alias, raise_if_not_found=False)
    if existing and existing.id != manager.id:
        _logger.warning("Duplicate PM manager groups detected; keeping id %s", manager.id)
        return
    env["ir.model.data"]._update_xmlids(
        [{"xml_id": alias, "record": manager, "noupdate": True}]
    )


def _ensure_pm_groups(env):
    admin = env.ref(f"{MODULE}.group_pm_admin", raise_if_not_found=False)
    manager = env.ref(f"{MODULE}.group_pm_maintenance_manager", raise_if_not_found=False)
    if admin and manager and manager not in admin.implied_ids:
        admin.write({"implied_ids": [(4, manager.id), (4, env.ref(f"{MODULE}.group_pm_technician").id)]})


def _configure_pm_admin_account(env):
    """Attach PM Admin to login 'admin' when present without touching superuser password."""
    admin_group = env.ref(f"{MODULE}.group_pm_admin")
    Users = env["res.users"].sudo()
    existing = Users.search([("login", "=", "admin")], limit=1)
    if not existing:
        _logger.info("No login 'admin' found; skipping PM Admin attachment.")
        return
    if existing.id == SUPERUSER_ID:
        _logger.info("Assigning PM Admin group to existing Odoo administrator (password unchanged).")
    existing.write({"groups_id": [(4, admin_group.id)]})


def _ensure_dev_pm_users(env):
    Users = env["res.users"].sudo()
    for spec in PM_DEV_USERS:
        user = Users.search([("login", "=", spec["login"])], limit=1)
        if not user:
            partner = env["res.partner"].sudo().create(
                {
                    "name": spec["name"],
                    "email": spec["email"],
                }
            )
            user = Users.with_context(no_reset_password=True).create(
                {
                    "name": spec["name"],
                    "login": spec["login"],
                    "email": spec["email"],
                    "partner_id": partner.id,
                    "company_id": env.company.id,
                    "company_ids": [(6, 0, env.company.ids)],
                }
            )
            user._pm_assign_role_groups(spec["role"])
        if spec.get("set_password"):
            user.sudo().write({"password": spec["password"]})
            user.write({"pm_password_reset_required": True})
