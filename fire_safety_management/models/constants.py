# -*- coding: utf-8 -*-

INSPECTION_TYPES = [
    ("fire_inspection", "Fire Inspection"),
    ("safety_audit", "Safety Audit"),
]

INSPECTION_STATES = [
    ("scheduled", "Scheduled"),
    ("in_progress", "In Progress"),
    ("pending", "Pending"),
    ("completed", "Completed"),
    ("closed", "Closed"),
]

CHECKLIST_RESULTS = [
    ("pass", "Pass"),
    ("fail", "Fail"),
    ("na", "N/A"),
]

CHECKLIST_CATEGORIES = [
    ("fire_extinguishers", "Fire Extinguishers"),
    ("fire_alarms", "Fire Alarms"),
    ("fire_exits", "Fire Exits"),
    ("emergency_lighting", "Emergency Lighting"),
    ("evacuation_routes", "Evacuation Routes"),
    ("emergency_signage", "Emergency Signage"),
    ("fire_safety_equipment", "Fire Safety Equipment"),
]

INCIDENT_TYPES = [
    ("fire", "Fire"),
    ("smoke_detection", "Smoke Detection"),
    ("fire_alarm", "Fire Alarm"),
    ("electrical", "Electrical Incident"),
    ("gas_leak", "Gas Leak"),
    ("safety_hazard", "Safety Hazard"),
    ("injury", "Injury/Accident"),
    ("false_alarm", "False Alarm"),
    ("other", "Other"),
]

SEVERITY_LEVELS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

INCIDENT_STATES = [
    ("open", "Open"),
    ("investigating", "Investigating"),
    ("resolved", "Resolved"),
]

DRILL_TYPES = [
    ("fire_evacuation", "Fire Evacuation Drill"),
    ("emergency_evacuation", "Emergency Evacuation Drill"),
    ("disaster_preparedness", "Disaster Preparedness Drill"),
    ("other", "Other"),
]

DRILL_STATES = [
    ("scheduled", "Scheduled"),
    ("rescheduled", "Rescheduled"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

EQUIPMENT_TYPES = [
    ("fire_extinguisher", "Fire Extinguishers"),
    ("fire_hydrant", "Fire Hydrants"),
    ("fire_hose", "Fire Hoses"),
    ("fire_alarm", "Fire Alarms"),
    ("smoke_detector", "Smoke Detectors"),
    ("sprinkler", "Sprinklers"),
    ("fire_pump", "Fire Pumps"),
    ("emergency_light", "Emergency Lights"),
    ("fire_door", "Fire Doors"),
    ("exit_sign", "Emergency Exit Signs"),
]

EQUIPMENT_CONDITIONS = [
    ("operational", "Operational"),
    ("under_maintenance", "Under Maintenance"),
    ("faulty", "Faulty"),
    ("replaced", "Replaced"),
]

EQUIPMENT_STATES = [
    ("operational", "Operational"),
    ("inspection_due", "Inspection Due"),
    ("service_due", "Service Due"),
    ("under_maintenance", "Under Maintenance"),
    ("faulty", "Faulty"),
    ("expired", "Expired"),
    ("replaced", "Replaced"),
]

EMERGENCY_TYPES = [
    ("fire", "Fire"),
    ("smoke", "Smoke"),
    ("gas_leak", "Gas Leak"),
    ("electrical", "Electrical Emergency"),
    ("evacuation", "Evacuation"),
    ("other", "Other"),
]

EMERGENCY_STATES = [
    ("active", "Active"),
    ("closed", "Closed"),
]

FINDING_STATES = [
    ("open", "Open"),
    ("in_progress", "In Progress"),
    ("closed", "Closed"),
]

ACTION_STATES = [
    ("open", "Open"),
    ("done", "Awaiting Verification"),
    ("closed", "Closed"),
]

LINE_RESULTS = CHECKLIST_RESULTS

XMLID_SAFETY_MANAGER = "fire_safety_management.group_fire_safety_manager"
XMLID_SECURITY = "fire_safety_management.group_fire_safety_security"
XMLID_GUARD = "fire_safety_management.group_fire_safety_guard"
XMLID_FACILITY = "fire_safety_management.group_fire_safety_facility"
XMLID_AUDITOR = "fire_safety_management.group_fire_safety_auditor"
XMLID_EXECUTIVE = "fire_safety_management.group_fire_safety_executive"
