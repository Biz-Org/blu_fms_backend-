# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tools.translate import _


class BaseIotAdapter:
    """Vendor-agnostic integration boundary.

    Real BMS/IoT/HVAC/lighting/fire/meter connectors should subclass this
    without changing FMS models. This module ships a mock adapter only.
    """

    kind = "mock"

    def __init__(self, integration):
        self.integration = integration

    def ping(self):
        raise NotImplementedError

    def execute(self, device, command, params=None):
        raise NotImplementedError


class MockIotAdapter(BaseIotAdapter):
    kind = "mock"

    def ping(self):
        return {
            "ok": True,
            "mode": "simulated",
            "message": "Mock adapter ready. No external system is connected.",
        }

    def execute(self, device, command, params=None):
        return {
            "ok": True,
            "simulated": True,
            "command": command,
            "params": params or {},
            "message": "Simulated execution. No physical equipment was changed.",
        }


class UnconfiguredIotAdapter(BaseIotAdapter):
    """Placeholder for future live connectors. Never reports physical success."""

    kind = "unconfigured"

    def ping(self):
        return {
            "ok": False,
            "mode": "unconfigured",
            "message": "Live vendor adapter is not implemented. Credentials are stored only.",
        }

    def execute(self, device, command, params=None):
        raise UserError(
            _("Live integration is not connected. The action was not sent to physical equipment.")
        )


ADAPTERS = {
    "mock": MockIotAdapter,
}


def get_adapter(integration):
    kind = integration.system_kind or "mock"
    cls = ADAPTERS.get(kind)
    if cls:
        return cls(integration)
    return UnconfiguredIotAdapter(integration)
