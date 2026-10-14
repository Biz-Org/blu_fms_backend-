# -*- coding: utf-8 -*-

from odoo import models

from .constants import (
    XMLID_AUDITOR,
    XMLID_EXECUTIVE,
    XMLID_FACILITY,
    XMLID_GUARD,
    XMLID_SAFETY_MANAGER,
    XMLID_SECURITY,
)


class ResUsers(models.Model):
    _inherit = "res.users"

    def _fs_is_safety_manager(self):
        self.ensure_one()
        return self.has_group(XMLID_SAFETY_MANAGER)

    def _fs_is_security_manager(self):
        self.ensure_one()
        return self.has_group(XMLID_SECURITY)

    def _fs_is_guard(self):
        self.ensure_one()
        return self.has_group(XMLID_GUARD)

    def _fs_can_verify_actions(self):
        self.ensure_one()
        return self._fs_is_safety_manager()

    def _fs_can_activate_emergency(self):
        self.ensure_one()
        return self._fs_is_safety_manager() or self._fs_is_security_manager()

    def _fs_has_fs_access(self):
        self.ensure_one()
        return any(
            self.has_group(xmlid)
            for xmlid in (
                XMLID_SAFETY_MANAGER,
                XMLID_SECURITY,
                XMLID_GUARD,
                XMLID_FACILITY,
                XMLID_AUDITOR,
                XMLID_EXECUTIVE,
            )
        )
