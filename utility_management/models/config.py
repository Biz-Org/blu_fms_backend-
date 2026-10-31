# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .selections import MANAGER_GROUP


class UtilityConfig(models.Model):
    _name = 'utility.management.config'
    _description = 'Utility Settings'
    _inherit = ['utility.management.mixin']
    _check_company_auto = True

    verification_required = fields.Boolean(default=True)
    offline_after_minutes = fields.Integer(default=60)
    missing_reading_after_minutes = fields.Integer(default=60)
    default_anomaly_percent = fields.Float(default=20.0)
    default_escalation_minutes = fields.Integer(default=60)
    mail_notifications = fields.Boolean(default=False)

    _sql_constraints = [
        (
            'config_company_uniq',
            'unique(company_id)',
            'Each company has one utility settings record.',
        ),
    ]

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError('Only a Facility Manager can change utility settings.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_config_service'):
            raise UserError('Settings are saved through the settings service.')
        self._check_manager()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('utility_config_service'):
            raise UserError('Settings are saved through the settings service.')
        self._check_manager()
        return super().write(vals)

    def _cron_offline(self):
        from odoo.addons.utility_management.services.meter_service import MeterService
        MeterService(self.env).mark_offline()

    def _cron_missing(self):
        from odoo.addons.utility_management.services.reading_service import ReadingService
        ReadingService(self.env).flag_missing()
