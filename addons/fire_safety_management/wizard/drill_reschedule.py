# -*- coding: utf-8 -*-

from odoo import fields, models


class FireSafetyDrillReschedule(models.TransientModel):
    _name = "fire.safety.drill.reschedule"
    _description = "Reschedule Fire & Safety Mock Drill"

    drill_id = fields.Many2one("fire.safety.drill", required=True, ondelete="cascade")
    new_datetime = fields.Datetime(required=True)
    reason = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        if self.reason:
            self.drill_id.message_post(body=self.reason)
        self.drill_id.action_reschedule_drill(self.new_datetime)
        return {"type": "ir.actions.act_window_close"}
