# -*- coding: utf-8 -*-

INTEGRATION_KINDS = [
    ("mock", "Mock / Development"),
    ("bms", "BMS"),
    ("iot_gateway", "IoT Gateway"),
    ("lighting", "Lighting System"),
    ("hvac", "HVAC System"),
    ("fire_alarm", "Fire Alarm System"),
    ("energy_meter", "Energy Meter"),
]

INTEGRATION_STATES = [
    ("draft", "Draft"),
    ("configured", "Configured"),
    ("connected", "Ready"),
    ("error", "Error"),
    ("disabled", "Disabled"),
]

AUTH_TYPES = [
    ("none", "None"),
    ("api_key", "API Key"),
    ("basic", "Username / Password"),
    ("oauth", "OAuth"),
]

CONNECTION_MODES = [
    ("simulated", "Simulated"),
    ("unconfigured", "Not Connected"),
    ("live", "Live"),
]

DEVICE_TYPES = [
    ("lighting", "Smart Lighting Controller"),
    ("hvac", "HVAC Controller"),
    ("fire_alarm", "Fire Alarm Panel"),
    ("environmental", "Air Quality Sensor"),
    ("temperature", "Temperature Sensor"),
    ("motion", "Motion Sensor"),
    ("meter", "Smart Meter"),
    ("gateway", "IoT Gateway"),
    ("other", "Other"),
]

DEVICE_STATUSES = [
    ("online", "Online"),
    ("offline", "Offline"),
    ("warning", "Warning"),
    ("faulty", "Faulty"),
    ("maintenance", "Maintenance"),
]

POWER_STATES = [
    ("on", "On"),
    ("off", "Off"),
]

HVAC_MODES = [
    ("off", "Off"),
    ("cool", "Cool"),
    ("heat", "Heat"),
    ("fan", "Fan"),
    ("auto", "Auto"),
]

FIRE_ALARM_CONDITIONS = [
    ("normal", "Normal"),
    ("alarm", "Alarm"),
    ("fault", "Fault"),
    ("communication_failure", "Communication Failure"),
]

SENSOR_PARAMETERS = [
    ("temperature", "Temperature"),
    ("humidity", "Humidity"),
    ("air_quality", "Air Quality"),
    ("co2", "CO₂"),
    ("occupancy", "Occupancy"),
    ("energy", "Energy"),
    ("other", "Other"),
]

READING_QUALITIES = [
    ("valid", "Valid"),
    ("abnormal", "Abnormal"),
    ("missing", "Missing / Unavailable"),
]

READING_SOURCES = [
    ("simulated", "Simulated"),
    ("manual", "Manual"),
    ("live", "Live"),
]

SCHEDULE_KINDS = [
    ("lighting", "Lighting"),
    ("hvac", "HVAC"),
]

LIGHTING_ACTIONS = [
    ("turn_on", "Turn On"),
    ("turn_off", "Turn Off"),
]

COMPARISON_OPERATORS = [
    ("gt", ">"),
    ("gte", "≥"),
    ("lt", "<"),
    ("lte", "≤"),
    ("eq", "="),
    ("neq", "≠"),
]

AUTOMATION_ACTIONS = [
    ("increase_hvac_cooling", "Increase HVAC Cooling"),
    ("decrease_hvac_cooling", "Decrease HVAC Cooling"),
    ("set_hvac_setpoint", "Set HVAC Setpoint"),
    ("lighting_on", "Turn Lighting On"),
    ("lighting_off", "Turn Lighting Off"),
    ("raise_alert", "Raise Alert"),
]

SCHEDULE_MODES = [
    ("always", "Always Active"),
    ("scheduled", "Set Schedule"),
]

EXECUTION_STATES = [
    ("simulated", "Simulated"),
    ("success", "Executed"),
    ("failed", "Failed"),
    ("overridden", "Manually Overridden"),
]

ALERT_TYPES = [
    ("device_offline", "IoT Device Offline"),
    ("device_malfunction", "Device Malfunction"),
    ("fire_alarm_triggered", "Fire Alarm Triggered"),
    ("fire_alarm_fault", "Fire Alarm System Fault"),
    ("hvac_fault", "HVAC Fault"),
    ("threshold_exceeded", "Environmental Threshold Exceeded"),
    ("air_quality", "Air Quality Deterioration"),
    ("sensor_unavailable", "Sensor Data Unavailable"),
    ("bms_failure", "BMS Communication Failure"),
    ("energy_abnormal", "Abnormal Energy Consumption"),
]

ALERT_PRIORITIES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

ALERT_STATES = [
    ("open", "Open"),
    ("acknowledged", "Acknowledged"),
    ("closed", "Closed"),
]

LOG_KINDS = [
    ("device_connected", "Device Connected"),
    ("device_disconnected", "Device Disconnected"),
    ("reading_received", "Reading Received"),
    ("threshold_exceeded", "Threshold Exceeded"),
    ("automation_triggered", "Automation Triggered"),
    ("automation_executed", "Automation Action Executed"),
    ("manual_override", "Manual Override"),
    ("hvac_adjusted", "HVAC Adjusted"),
    ("lighting_changed", "Lighting Changed"),
    ("fire_alarm_event", "Fire Alarm Event"),
    ("integration_failure", "Integration Communication Failure"),
    ("device_updated", "Device Updated"),
]

AREA_KINDS = [
    ("floor", "Floor"),
    ("zone", "Zone"),
    ("room", "Room"),
    ("area", "Area"),
]

WEEKDAYS = [
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
]

DEFAULT_OFFLINE_MINUTES = 15
DEFAULT_STALE_MINUTES = 30
