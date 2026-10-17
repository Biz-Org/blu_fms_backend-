from odoo import SUPERUSER_ID, api

from odoo.addons.maintenance.hooks import remove_legacy_root_menus


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    remove_legacy_root_menus(env)
