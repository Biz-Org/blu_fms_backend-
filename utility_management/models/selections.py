# -*- coding: utf-8 -*-

UTILITY_TYPES = [
    ('electricity', 'Electricity'),
    ('water', 'Water'),
    ('gas', 'Gas'),
]
METER_ROLES = [
    ('consumption', 'Consumption'),
    ('tank', 'Tank'),
    ('leak_sensor', 'Leak Sensor'),
    ('power_monitor', 'Power Monitor'),
]
READING_MODES = [
    ('cumulative', 'Cumulative'),
    ('interval', 'Interval'),
]
PROTOCOLS = [
    ('mqtt', 'MQTT'),
    ('modbus', 'Modbus'),
    ('rest', 'REST'),
    ('manual', 'Manual'),
    ('import', 'Import'),
    ('other', 'Other'),
]
METER_STATUSES = [
    ('connecting', 'Connecting'),
    ('online', 'Online'),
    ('offline', 'Offline'),
    ('error', 'Error'),
    ('maintenance', 'Maintenance'),
    ('deactivated', 'Deactivated'),
]
METER_TRANSITIONS = {
    'connecting': {'online', 'offline', 'error'},
    'online': {'offline', 'error', 'maintenance', 'connecting', 'deactivated'},
    'offline': {'connecting', 'online', 'error', 'maintenance', 'deactivated'},
    'error': {'connecting', 'maintenance', 'deactivated', 'online'},
    'maintenance': {'connecting', 'online', 'deactivated'},
    'deactivated': {'connecting'},
}
HEALTH_VALUES = [
    ('unknown', 'Unknown'),
    ('healthy', 'Healthy'),
    ('degraded', 'Degraded'),
    ('failed', 'Failed'),
]
READING_SOURCES = [
    ('smart_meter', 'Smart Meter'),
    ('manual', 'Manual Entry'),
    ('imported', 'Imported Reading'),
    ('other', 'Other Integration'),
]
READING_STATUSES = [
    ('recorded', 'Recorded'),
    ('pending_verification', 'Pending Verification'),
    ('verified', 'Verified'),
    ('invalid', 'Invalid'),
    ('corrected', 'Corrected'),
]
READING_TRANSITIONS = {
    'recorded': {'pending_verification', 'verified', 'invalid'},
    'pending_verification': {'verified', 'invalid'},
    'invalid': {'pending_verification'},
    'verified': {'corrected'},
    'corrected': set(),
}
SAFETY_OBSERVATIONS = [
    ('normal', 'Normal'),
    ('warning', 'Warning'),
    ('critical', 'Critical'),
]
SOURCE_KINDS = [
    ('grid', 'Grid'),
    ('generator', 'Generator'),
]
POWER_STATES = [
    ('grid_active', 'Grid Active'),
    ('grid_outage', 'Grid Outage'),
    ('generator_standby', 'Generator Standby'),
    ('generator_active', 'Generator Active'),
    ('generator_fault', 'Generator Fault'),
    ('power_restored', 'Power Restored'),
]
POWER_TRANSITIONS = {
    'grid_active': {'grid_outage', 'generator_active'},
    'grid_outage': {'generator_active', 'power_restored'},
    'generator_standby': {'generator_active', 'generator_fault'},
    'generator_active': {'generator_standby', 'generator_fault', 'power_restored'},
    'generator_fault': {'generator_standby', 'generator_active'},
    'power_restored': {'grid_active'},
}
POWER_EVENT_TYPES = [
    ('outage', 'Outage'),
    ('restore', 'Restore'),
    ('start', 'Start'),
    ('stop', 'Stop'),
    ('fault', 'Fault'),
]
POWER_EVENT_FOR_STATE = {
    'grid_outage': 'outage',
    'power_restored': 'restore',
    'generator_active': 'start',
    'generator_standby': 'stop',
    'generator_fault': 'fault',
    'grid_active': 'restore',
}
LEAK_TYPES = [
    ('water', 'Water Leak'),
    ('gas', 'Gas Leak'),
    ('suspected', 'Suspected Leak'),
    ('other', 'Other Utility Abnormality'),
]
LEAK_SEVERITIES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
LEAK_STATES = [
    ('detected', 'Detected'),
    ('investigating', 'Investigating'),
    ('action_required', 'Action Required'),
    ('resolved', 'Resolved'),
    ('closed', 'Closed'),
]
LEAK_TRANSITIONS = {
    'detected': {'investigating', 'action_required'},
    'investigating': {'action_required', 'resolved'},
    'action_required': {'investigating', 'resolved'},
    'resolved': {'closed'},
    'closed': set(),
}
LEAK_ENTRY_KINDS = [
    ('investigation', 'Investigation'),
    ('action', 'Action'),
    ('resolution', 'Resolution'),
]
ALERT_RULE_TYPES = [
    ('threshold', 'Threshold'),
    ('spike', 'Spike'),
    ('tank_level', 'Tank Level'),
    ('gas_pressure', 'Gas Pressure'),
    ('meter_offline', 'Meter Offline'),
    ('missing_reading', 'Missing Reading'),
    ('grid_outage', 'Grid Outage'),
    ('generator_fault', 'Generator Fault'),
]
ALERT_SEVERITIES = [
    ('informational', 'Informational'),
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
ALERT_STATES = [
    ('new', 'New'),
    ('acknowledged', 'Acknowledged'),
    ('in_progress', 'In Progress'),
    ('resolved', 'Resolved'),
    ('closed', 'Closed'),
]
ALERT_TRANSITIONS = {
    'new': {'acknowledged', 'in_progress'},
    'acknowledged': {'in_progress'},
    'in_progress': {'resolved'},
    'resolved': {'closed'},
    'closed': set(),
}
TANK_BOUNDS = [
    ('low', 'Low'),
    ('high', 'High'),
]
REPORT_TYPES = [
    ('electricity_consumption', 'Electricity Consumption'),
    ('water_consumption', 'Water Consumption'),
    ('gas_consumption', 'Gas Consumption'),
    ('combined_usage', 'Combined Utility Usage'),
    ('grid_vs_generator', 'Grid vs Generator'),
    ('meter_reading', 'Meter Reading'),
    ('leak_detection', 'Leak Detection'),
    ('consumption_alert', 'Consumption Alert'),
    ('utility_trend', 'Utility Trend'),
    ('utility_performance', 'Utility Performance'),
]
GROUPINGS = [
    ('day', 'Day'),
    ('week', 'Week'),
    ('month', 'Month'),
    ('year', 'Year'),
]
COMPARISONS = [
    ('none', 'None'),
    ('previous_period', 'Previous Period'),
]
SCHEDULES = [
    ('none', 'None'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
]
EXECUTION_STATES = [
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
]
EXPORT_FORMATS = [
    ('pdf', 'PDF'),
    ('xlsx', 'Excel'),
    ('csv', 'CSV'),
]
AUDIT_EVENTS = [
    ('meter_change', 'Meter Change'),
    ('reading_correction', 'Reading Correction'),
    ('reading_verification', 'Reading Verification'),
    ('alert_change', 'Alert Change'),
    ('leak_change', 'Leak Change'),
    ('config_change', 'Config Change'),
    ('report_execution', 'Report Execution'),
    ('access_denied', 'Access Denied'),
]
AUDIT_OUTCOMES = [
    ('success', 'Success'),
    ('denied', 'Denied'),
]
SCOPE_DIMENSIONS = [
    ('property', 'Property'),
    ('site', 'Site'),
    ('department', 'Department'),
]
LOCATION_REF_FIELDS = ('property_ref', 'site_ref', 'floor_ref', 'area_ref', 'department_ref')
LOCATION_LABEL_FIELDS = (
    'property_label', 'site_label', 'floor_label', 'area_label', 'department_label',
)
LOCATION_FIELDS = LOCATION_REF_FIELDS + LOCATION_LABEL_FIELDS
SECRET_MARKERS = ('password', 'secret', 'token', 'credential', 'api_key', 'auth')
PHOTO_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}
PHOTO_MAX_BYTES = 5 * 1024 * 1024
MANAGER_GROUP = 'utility_management.group_facility_manager'
STAFF_GROUP = 'utility_management.group_utility_staff'
SCOPED_MODELS = (
    'utility.management.meter',
    'utility.management.connectivity',
    'utility.management.reading',
    'utility.management.power.source',
    'utility.management.power.event',
    'utility.management.leak',
    'utility.management.leak.action',
    'utility.management.alert',
    'utility.management.report.definition',
    'utility.management.report.run',
    'utility.management.audit.event',
)
