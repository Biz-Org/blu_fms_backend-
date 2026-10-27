# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MobileSyncLog(models.Model):
    _name = "mobile.sync.log"
    _description = "Mobile Sync Log"
    _order = "write_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    sync_key = fields.Char(required=True, index=True)
    last_value = fields.Char()
    idempotency_key = fields.Char(index=True)

    _sql_constraints = [
        (
            "user_key_uniq",
            "unique(user_id, sync_key)",
            "Sync key must be unique per user.",
        ),
    ]
    @api.model
    def touch(self, sync_key, value=None):
        log = self.search([("user_id", "=", self.env.user.id), ("sync_key", "=", sync_key)], limit=1)
        if log:
            log.write({"last_value": value or fields.Datetime.now().isoformat()})
        else:
            self.create({
                "user_id": self.env.user.id,
                "sync_key": sync_key,
                "last_value": value or fields.Datetime.now().isoformat(),
            })
