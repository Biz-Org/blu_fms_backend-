# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        user = self.env.user
        if (
            user
            and not user._is_public()
            and user._cc_is_community_webclient_resident()
            and "user_companies" not in result
        ):
            result.update(user._cc_webclient_company_session())
        return result
