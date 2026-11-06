# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError, UserError

OPERATIONAL_STATUSES = [
    ('normal', 'Normal'),
    ('degraded', 'Degraded'),
    ('emergency', 'Emergency'),
    ('offline', 'Offline'),
]
OPERATIONAL_STATUS_VALUES = {item[0] for item in OPERATIONAL_STATUSES}

SEVERITIES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
SEVERITY_VALUES = {item[0] for item in SEVERITIES}

ALERT_SOURCES = [
    ('manual', 'Manual'),
    ('command_center', 'Command Center'),
    ('video_analytics', 'Video Analytics'),
    ('other', 'Other'),
]
ALERT_SOURCE_VALUES = {item[0] for item in ALERT_SOURCES}

ALERT_STATES = [
    ('open', 'Open'),
    ('acknowledged', 'Acknowledged'),
    ('investigating', 'Investigating'),
    ('resolved', 'Resolved'),
    ('closed', 'Closed'),
]
ALERT_STATE_VALUES = {item[0] for item in ALERT_STATES}

ESCALATION_MODES = [
    ('automatic', 'Automatic'),
    ('manual', 'Manual'),
]
ESCALATION_MODE_VALUES = {item[0] for item in ESCALATION_MODES}

ESCALATION_RESULTS = [
    ('triggered', 'Triggered'),
    ('notified', 'Notified'),
    ('failed', 'Failed'),
    ('acknowledged', 'Acknowledged'),
]
ESCALATION_RESULT_VALUES = {item[0] for item in ESCALATION_RESULTS}

REPORT_SOURCES = [
    ('alerts', 'Alerts'),
    ('incidents', 'Incidents'),
    ('sites', 'Sites'),
    ('emergency', 'Emergency'),
]
REPORT_SOURCE_VALUES = {item[0] for item in REPORT_SOURCES}

EXPORT_FORMATS = [
    ('csv', 'CSV'),
    ('json', 'JSON'),
]
EXPORT_FORMAT_VALUES = {item[0] for item in EXPORT_FORMATS}

ALERT_PROTECTED_FIELDS = {
    'state',
    'acknowledged_uid',
    'acknowledged_at',
    'resolved_uid',
    'resolved_at',
    'closed_at',
    'is_emergency',
}

INCIDENT_PROTECTED_FIELDS = {
    'state',
    'opened_at',
    'acknowledged_at',
    'resolved_at',
    'closed_at',
}


class CcMixin(models.AbstractModel):
    _name = 'cc.mixin'
    _description = 'Command Center Access Helpers'

    def _cc_require_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _cc_require_user(self):
        self._cc_require_group(
            'command_center.group_cc_user',
            'Only Command Center Users can perform this action.',
        )

    def _cc_require_manager(self):
        self._cc_require_group(
            'command_center.group_cc_manager',
            'Only Command Center Managers can perform this action.',
        )

    def _cc_require_admin(self):
        self._cc_require_group(
            'command_center.group_cc_admin',
            'Only Command Center Administrators can perform this action.',
        )

    def _cc_guard_lifecycle_fields(self, vals, protected, message, creating=False):
        if self.env.context.get('cc_lifecycle'):
            return
        blocked = set(protected).intersection(vals)
        if creating:
            if vals.get('state') in (None, False, 'open'):
                blocked.discard('state')
            if not vals.get('is_emergency'):
                blocked.discard('is_emergency')
            blocked.discard('opened_at')
            for fname in (
                'acknowledged_uid', 'acknowledged_at',
                'resolved_uid', 'resolved_at', 'closed_at',
            ):
                if not vals.get(fname):
                    blocked.discard(fname)
        if blocked:
            raise UserError(message)
