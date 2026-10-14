# -*- coding: utf-8 -*-

from odoo import models

XMLID_MANAGER = "compliance_audit_management.group_compliance_manager"
XMLID_AUDITOR = "compliance_audit_management.group_compliance_auditor"


class ResUsers(models.Model):
    _inherit = "res.users"

    def _ca_is_compliance_manager(self):
        self.ensure_one()
        return self.has_group(XMLID_MANAGER) or self.has_group("base.group_system")

    def _ca_is_compliance_auditor(self):
        self.ensure_one()
        return self.has_group(XMLID_AUDITOR)
