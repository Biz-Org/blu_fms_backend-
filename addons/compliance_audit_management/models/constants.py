# -*- coding: utf-8 -*-

COMPLIANCE_CATEGORIES = [
    ("ehs", "Environmental Health & Safety"),
    ("fire_life_safety", "Fire & Life Safety"),
    ("hvac", "HVAC & Mechanical Systems"),
    ("accessibility", "Accessibility (ADA)"),
    ("health_safety", "Health & Safety"),
    ("mechanical", "Mechanical"),
    ("environmental", "Environmental"),
    ("building", "Building"),
    ("equipment", "Equipment"),
    ("regulatory", "Regulatory"),
    ("other", "Other"),
]

CHECKLIST_RESULTS = [
    ("compliant", "Compliant"),
    ("non_compliant", "Non-Compliant"),
    ("na", "Not Applicable"),
]

CHECK_STATES = [
    ("scheduled", "Scheduled"),
    ("in_progress", "In Progress"),
    ("pending", "Pending"),
    ("completed", "Completed"),
]

AUDIT_KINDS = [
    ("audit", "Audit"),
    ("inspection", "Inspection"),
]

AUDIT_TYPES = [
    ("internal", "Internal Audit"),
    ("external", "External Audit"),
    ("regulatory", "Regulatory Audit"),
    ("statutory", "Statutory Audit"),
    ("compliance", "Compliance Audit"),
    ("follow_up", "Follow-up Audit"),
]

INSPECTION_TYPES = [
    ("regulatory", "Regulatory Inspection"),
    ("statutory", "Statutory Inspection"),
    ("safety", "Safety Inspection"),
    ("equipment", "Equipment Inspection"),
    ("building", "Building Inspection"),
    ("environmental", "Environmental Inspection"),
]

AUDIT_STATES = [
    ("scheduled", "Scheduled"),
    ("in_progress", "In Progress"),
    ("pending_review", "Pending Review"),
    ("completed", "Completed"),
    ("failed", "Failed"),
    ("closed", "Closed"),
]

FINDING_STATES = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("converted", "Converted to Non-Compliance"),
    ("dismissed", "Dismissed"),
]

SEVERITY_LEVELS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

NC_STATES = [
    ("open", "Open"),
    ("assigned", "Assigned"),
    ("in_progress", "In Progress"),
    ("pending_verification", "Pending Verification"),
    ("resolved", "Resolved"),
    ("closed", "Closed"),
]

ACTION_STATES = [
    ("open", "Open"),
    ("in_progress", "In Progress"),
    ("pending_verification", "Pending Verification"),
    ("verified", "Verified"),
    ("closed", "Closed"),
]

DOCUMENT_TYPES = [
    ("license", "License"),
    ("certificate", "Certificate"),
    ("permit", "Permit"),
    ("approval", "Approval"),
    ("other", "Other"),
]

DOCUMENT_STATES = [
    ("active", "Active"),
    ("expiring_soon", "Expiring Soon"),
    ("renewal_due", "Renewal Due"),
    ("under_renewal", "Under Renewal"),
    ("expired", "Expired"),
    ("renewed", "Renewed"),
    ("archived", "Archived"),
]

RENEWAL_REMINDERS = [
    ("7", "7 days before expiry"),
    ("15", "15 days before expiry"),
    ("30", "30 days before expiry"),
    ("60", "60 days before expiry"),
    ("90", "90 days before expiry"),
]

REGULATORY_REPORT_STATES = [
    ("draft", "Draft"),
    ("in_preparation", "In Preparation"),
    ("submitted", "Submitted"),
]

PRIORITY_LEVELS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

ALERT_TYPES = [
    ("compliance_check", "Compliance Check"),
    ("audit", "Audit"),
    ("inspection", "Inspection"),
    ("document_renewal", "Document Renewal"),
    ("license_renewal", "License Renewal"),
    ("regulatory_submission", "Regulatory Submission"),
    ("corrective_action", "Corrective Action Deadline"),
]

ALERT_STATES = [
    ("open", "Open"),
    ("acknowledged", "Acknowledged"),
    ("escalated", "Escalated"),
    ("closed", "Closed"),
]

REPEAT_FREQUENCIES = [
    ("none", "Does not repeat"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("annually", "Annually"),
]
