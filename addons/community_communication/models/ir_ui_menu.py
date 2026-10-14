# -*- coding: utf-8 -*-

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        if not self.env.user._cc_is_community_webclient_resident():
            return visible
        root = self.env.ref(
            "community_communication.menu_community_communication_root",
            raise_if_not_found=False,
        )
        if not root:
            return visible
        allowed = set(self.sudo().search([("id", "child_of", root.id)]).ids)
        return frozenset(menu_id for menu_id in visible if menu_id in allowed)
