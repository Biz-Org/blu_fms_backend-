# -*- coding: utf-8 -*-

REPORT_TYPES = [
    ("tabular", "Tabular"),
    ("summary", "Summary"),
    ("kpi", "KPI"),
    ("chart", "Chart"),
    ("comparative", "Comparative"),
    ("cross_module", "Cross-Module"),
    ("operational", "Operational"),
    ("analytical", "Analytical"),
    ("quarterly", "Quarterly"),
]

REPORT_STATUSES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("scheduled", "Scheduled"),
    ("archived", "Archived"),
]

EXECUTION_STATUSES = [
    ("pending", "Pending"),
    ("running", "Running"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("cancelled", "Cancelled"),
]

KPI_CATEGORIES = [
    ("operations", "Operations"),
    ("maintenance", "Maintenance"),
    ("compliance", "Compliance"),
    ("fire_safety", "Fire & Safety"),
    ("community", "Community"),
    ("energy", "Energy"),
    ("finance", "Finance"),
    ("service_requests", "Service Requests"),
    ("asset_performance", "Asset Performance"),
]

KPI_AGGREGATIONS = [
    ("count", "Count"),
    ("sum", "Sum"),
    ("avg", "Average"),
    ("min", "Minimum"),
    ("max", "Maximum"),
]

DASHBOARD_TYPES = [
    ("executive", "Executive"),
    ("operational", "Operational"),
    ("module", "Module"),
    ("comparative", "Comparative"),
    ("custom", "Custom"),
]

AUDIT_ACTIONS = [
    ("create", "Create"),
    ("write", "Update"),
    ("archive", "Archive"),
    ("restore", "Restore"),
    ("run", "Run Report"),
    ("schedule", "Schedule"),
    ("export", "Export"),
    ("share", "Share"),
    ("analyze", "Run Analysis"),
    ("alert", "Alert"),
    ("other", "Other"),
]

VISUALIZATIONS = [
    ("table", "Table"),
    ("kpi", "KPI"),
    ("bar", "Bar"),
    ("line", "Line"),
    ("pie", "Pie"),
    ("donut", "Donut"),
    ("area", "Area"),
]

OUTPUT_FORMATS = [
    ("pdf", "PDF"),
    ("xlsx", "Excel"),
    ("csv", "CSV"),
]

SCHEDULE_FREQUENCIES = [
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("custom", "Custom"),
]

ALERT_TYPES = [
    ("threshold", "Threshold"),
    ("target", "Target"),
    ("trend", "Trend"),
    ("availability", "Availability"),
]

ALERT_SEVERITIES = [
    ("info", "Informational"),
    ("warning", "Warning"),
    ("high", "High"),
    ("critical", "Critical"),
]

ALERT_CONDITIONS = [
    ("gt", "Greater Than (>)"),
    ("gte", "Greater or Equal (>=)"),
    ("lt", "Less Than (<)"),
    ("lte", "Less or Equal (<=)"),
    ("eq", "Equal (=)"),
]

ALERT_FREQUENCIES = [
    ("once", "Once"),
    ("hourly", "Hourly while persistent"),
    ("daily", "Daily while persistent"),
    ("every", "Every evaluation"),
]

ANALYSIS_TYPES = [
    ("operational", "Operational"),
    ("financial", "Financial"),
    ("trends", "Trend Analysis"),
    ("cross_module", "Cross-Module"),
    ("predictive", "Predictive"),
]

DATE_RANGE_KEYS = [
    ("last_7", "Last 7 Days"),
    ("last_30", "Last 30 Days"),
    ("last_90", "Last 90 Days"),
    ("this_month", "This Month"),
    ("this_quarter", "This Quarter"),
    ("this_year", "This Year"),
    ("previous", "Previous Period"),
    ("custom", "Custom"),
]

WEEKDAYS = [
    ("0", "Monday"),
    ("1", "Tuesday"),
    ("2", "Wednesday"),
    ("3", "Thursday"),
    ("4", "Friday"),
    ("5", "Saturday"),
    ("6", "Sunday"),
]
