# -*- coding: utf-8 -*-

"""Optional FMS module adapters (detect model availability at runtime)."""

from odoo import models


class MobileIntegrationExternal(models.AbstractModel):
    _name = "mobile.integration.external"
    _description = "External FMS module integration helpers"

    def _model_available(self, model_name):
        return model_name in self.env

    def service_requests_available(self):
        return self._model_available("service.management.request") or self._model_available("helpdesk.ticket")

    def helpdesk_available(self):
        return self._model_available("helpdesk.ticket")

    def amenity_available(self):
        return self._model_available("property.amenity") or self._model_available("amenity.booking")

    def visitor_module_available(self):
        return self._model_available("visitor.management.request") or self._model_available("visitor.pass")

    def payments_available(self):
        return self._model_available("account.move") or self._model_available("billing.statement")

    def list_external_service_requests(self, user, limit=20):
        if self._model_available("service.management.request"):
            Model = self.env["service.management.request"]
            domain = [("user_id", "=", user.id)] if "user_id" in Model._fields else []
            records = Model.search(domain, limit=limit)
            return {
                "available": True,
                "source": "service.management.request",
                "items": [
                    {
                        "id": r.id,
                        "name": r.display_name,
                        "state": getattr(r, "state", "submitted"),
                        "external": True,
                    }
                    for r in records
                ],
            }
        return {"available": False, "items": []}

    def payment_summary(self, user):
        if not self.payments_available():
            return {"available": False, "balance": 0.0, "items": []}
        return {
            "available": False,
            "message": "Finance module detected but mobile payment mapping is not configured.",
            "balance": 0.0,
            "items": [],
        }
