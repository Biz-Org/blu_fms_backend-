# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError

DETECTION_TYPES = [
    ('intrusion', 'Intrusion'),
    ('fire_smoke', 'Fire/Smoke'),
    ('ppe_violation', 'PPE Violation'),
    ('vehicle_speeding', 'Vehicle Speeding'),
    ('crowd_density', 'Crowd Density'),
    ('object_detection', 'Object Detection'),
]
DETECTION_TYPE_VALUES = {item[0] for item in DETECTION_TYPES}

SEVERITIES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
SEVERITY_VALUES = {item[0] for item in SEVERITIES}

CAMERA_STATUSES = [
    ('online', 'Online'),
    ('offline', 'Offline'),
    ('degraded', 'Degraded'),
    ('inactive', 'Inactive'),
]

STREAM_PROTOCOLS = [
    ('none', 'None'),
    ('hls', 'HLS'),
    ('dash', 'DASH'),
    ('http', 'HTTP'),
    ('other', 'Other'),
]

DETECTION_STATES = [
    ('new', 'New'),
    ('linked', 'Linked'),
    ('skipped', 'Skipped'),
    ('dismissed', 'Dismissed'),
]

EVENT_STATES = [
    ('open', 'Alert'),
    ('acknowledged', 'Verification'),
    ('investigating', 'Incident'),
    ('resolved', 'Resolution'),
    ('closed', 'Closed'),
    ('false_positive', 'False Positive'),
]


class VaMixin(models.AbstractModel):
    _name = 'va.mixin'
    _description = 'Video Analytics Access Helpers'

    def _va_require_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _va_require_user(self):
        self._va_require_group(
            'video_analytics.group_va_user',
            'Only Video Analytics Users can perform this action.',
        )

    def _va_require_manager(self):
        self._va_require_group(
            'video_analytics.group_va_manager',
            'Only Video Analytics Managers can perform this action.',
        )

    def _va_require_admin(self):
        self._va_require_group(
            'video_analytics.group_va_admin',
            'Only Video Analytics Administrators can perform this action.',
        )
