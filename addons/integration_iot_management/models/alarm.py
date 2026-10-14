# -*- coding: utf-8 -*-

from odoo import fields, models

from .constants import FIRE_ALARM_CONDITIONS


class IntegrationIotAlarmEvent(models.Model):
    """Fire alarm integration events.

    This is monitoring/history for connected fire alarm systems. It does not
    create Fire & Safety incidents, drills, or inspections.
    """

    _name = "integration.iot.alarm.event"
    _description = "Fire Alarm Integration Event"
    _inherit = ["integration.iot.scoped.mixin"]
    _order = "event_time desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    condition = fields.Selection(FIRE_ALARM_CONDITIONS, required=True, index=True)
    event_time = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    device_id = fields.Many2one("integration.iot.device", ondelete="cascade", index=True, required=True)
    note = fields.Text()
