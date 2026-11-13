# Part of Preventive Maintenance Management.

import json

from odoo import api, fields, models


class PmAuditMixin(models.AbstractModel):
    """Create ``pm.audit.log`` rows for workflow and configuration changes."""

    _name = "pm.audit.mixin"
    _description = "PM Audit Mixin"

    def _pm_audit_log(self, action, details, res_model=None, res_id=None, old_vals=None, new_vals=None):
        self.ensure_one()
        Audit = self.env["pm.audit.log"].sudo()
        vals = {
            "res_model": res_model or self._name,
            "res_id": res_id if res_id is not None else self.id,
            "action_type": action,
            "details": details,
            "user_id": self.env.user.id,
            "company_id": getattr(self, "company_id", self.env.company).id,
        }
        if old_vals is not None or new_vals is not None:
            vals["value_before"] = json.dumps(old_vals) if old_vals else False
            vals["value_after"] = json.dumps(new_vals) if new_vals else False
        Audit.create(vals)
