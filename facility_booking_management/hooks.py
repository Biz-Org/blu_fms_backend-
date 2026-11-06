# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Assign existing properties to admin community managers for initial access."""
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if not admin:
        return
    Property = env["fms.property"].sudo()
    for prop in Property.search([]):
        if admin not in prop.manager_ids:
            prop.manager_ids = [(4, admin.id)]
