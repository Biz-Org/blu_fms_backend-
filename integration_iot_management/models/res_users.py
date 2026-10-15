# -*- coding: utf-8 -*-

from odoo import models

XMLID_ADMIN = "integration_iot_management.group_integration_admin"


class ResUsers(models.Model):
    _inherit = "res.users"

    def _iot_is_integration_admin(self):
        self.ensure_one()
        return self.has_group(XMLID_ADMIN) or self.has_group("base.group_system")
