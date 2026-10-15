# -*- coding: utf-8 -*-

from odoo import api, models


class CommunityCommunicationScheduler(models.AbstractModel):
    _name = "community.communication.scheduler"
    _description = "Community scheduled jobs"

    @api.model
    def _cron_process(self):
        self.env["community.communication.announcement"]._cron_publish_and_expire()
        self.env["community.communication.notice"]._cron_publish_and_archive()
        self.env["community.communication.poll"]._cron_open_and_close()
        self.env["community.communication.event"]._cron_send_reminders()
        self.env["community.communication.event"]._cron_complete_past()
