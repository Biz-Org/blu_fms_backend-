# -*- coding: utf-8 -*-

XMLID_GROUP_RESIDENT = "mobile_application.group_mobile_resident"
XMLID_GROUP_STAFF = "mobile_application.group_mobile_staff"
XMLID_GROUP_SECURITY = "mobile_application.group_mobile_security"

SERVICE_REQUEST_STATES = [
    ("submitted", "Submitted"),
    ("assigned", "Assigned"),
    ("in_progress", "In Progress"),
    ("pending", "Pending"),
    ("completed", "Completed"),
    ("closed", "Closed"),
]

VISITOR_STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("denied", "Denied"),
    ("verified", "Verified"),
    ("checked_in", "Checked In"),
    ("checked_out", "Checked Out"),
    ("cancelled", "Cancelled"),
]

BOOKING_STATES = [
    ("requested", "Requested"),
    ("confirmed", "Confirmed"),
    ("pending", "Pending"),
    ("cancelled", "Cancelled"),
    ("completed", "Completed"),
]

PAYMENT_STATES = [
    ("pending", "Pending"),
    ("successful", "Successful"),
    ("failed", "Failed"),
    ("refunded", "Refunded"),
]

NOTIFICATION_TYPES = [
    ("service", "Service Request"),
    ("visitor", "Visitor"),
    ("payment", "Payment"),
    ("booking", "Booking"),
    ("community", "Community"),
    ("helpdesk", "Helpdesk"),
    ("security", "Security"),
    ("system", "System"),
]
