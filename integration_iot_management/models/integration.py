# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .adapter import get_adapter
from .constants import AUTH_TYPES, CONNECTION_MODES, INTEGRATION_KINDS, INTEGRATION_STATES


class IntegrationIotIntegration(models.Model):
    _name = "integration.iot.integration"
    _description = "IoT / BMS Integration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    system_kind = fields.Selection(
        INTEGRATION_KINDS,
        required=True,
        default="mock",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        INTEGRATION_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    connection_mode = fields.Selection(
        CONNECTION_MODES,
        compute="_compute_connection_mode",
        store=True,
    )
    endpoint_url = fields.Char()
    auth_type = fields.Selection(AUTH_TYPES, default="none", required=True)
    auth_username = fields.Char(copy=False)
    auth_secret = fields.Char(
        copy=False,
        groups="integration_iot_management.group_integration_admin",
        help="Stored secret. Never sent to OWL screens.",
    )
    auth_secret_set = fields.Boolean(compute="_compute_auth_secret_set")
    last_heartbeat = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    active = fields.Boolean(default=True)
    note = fields.Text()
    device_ids = fields.One2many("integration.iot.device", "integration_id")

    @api.depends("system_kind", "state")
    def _compute_connection_mode(self):
        for record in self:
            if record.system_kind == "mock":
                record.connection_mode = "simulated"
            elif record.state == "connected":
                record.connection_mode = "live"
            else:
                record.connection_mode = "unconfigured"

    @api.depends("auth_secret")
    def _compute_auth_secret_set(self):
        for record in self:
            record.auth_secret_set = bool(record.auth_secret)

    def write(self, vals):
        if "auth_secret" in vals or "auth_username" in vals or "auth_type" in vals:
            self._iot_require_admin(_("Only an Integration Admin can change integration credentials."))
        if "state" in vals or "system_kind" in vals or "endpoint_url" in vals or "active" in vals:
            self._iot_require_admin(_("Only an Integration Admin can change integration configuration."))
        return super().write(vals)

    def _iot_require_admin(self, message=None):
        return self.env["integration.iot.device"]._iot_require_admin(message)

    def action_set_secret(self, secret):
        self._iot_require_admin()
        if not secret:
            raise UserError(_("Secret cannot be empty."))
        self.write({"auth_secret": secret, "state": "configured" if self.state == "draft" else self.state})
        return True

    def action_clear_secret(self):
        self._iot_require_admin()
        self.write({"auth_secret": False})
        return True

    def action_enable(self):
        self._iot_require_admin()
        self.write({"state": "configured" if self.state == "disabled" else self.state, "active": True})
        return True

    def action_disable(self):
        self._iot_require_admin()
        self.write({"state": "disabled", "active": False})
        self.env["integration.iot.log"]._iot_record(
            kind="integration_failure",
            name=_("Integration disabled: %s") % self.display_name,
            integration=self,
        )
        return True

    def action_test_connection(self):
        self.ensure_one()
        self._iot_require_admin()
        adapter = get_adapter(self)
        result = adapter.ping()
        vals = {
            "last_heartbeat": fields.Datetime.now() if result.get("ok") else False,
            "last_error": False if result.get("ok") else result.get("message"),
            "state": "connected" if result.get("ok") else "error",
        }
        self.write(vals)
        if not result.get("ok"):
            self.env["integration.iot.log"]._iot_record(
                kind="integration_failure",
                name=_("Connection test failed: %s") % self.display_name,
                integration=self,
                note=result.get("message"),
            )
            self.env["integration.iot.alert"]._iot_ensure_alert(
                name=_("BMS communication failure: %s") % self.display_name,
                alert_type="bms_failure",
                priority="high",
                integration=self,
                origin=self,
            )
        return result
