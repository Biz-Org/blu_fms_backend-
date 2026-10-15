# -*- coding: utf-8 -*-

ANNOUNCEMENT_CATEGORIES = [
    ("general", "General"),
    ("community", "Community"),
    ("maintenance", "Maintenance Updates"),
    ("events", "Events"),
    ("security", "Security"),
    ("safety", "Safety"),
    ("utilities", "Utilities"),
    ("policy", "Policy Updates"),
    ("facility", "Facility Updates"),
    ("emergency", "Emergency"),
    ("other", "Other"),
]

DISCUSSION_CATEGORIES = [
    ("general", "General Discussion"),
    ("suggestions", "Community Suggestions"),
    ("events", "Events"),
    ("neighborhood", "Neighborhood"),
    ("lost_found", "Lost & Found"),
    ("recommendations", "Recommendations"),
    ("facilities", "Facilities"),
    ("activities", "Community Activities"),
    ("environment", "Environment"),
    ("other", "Other"),
]

NOTICE_CATEGORIES = [
    ("general", "General"),
    ("maintenance", "Maintenance"),
    ("security", "Security"),
    ("events", "Events"),
]

GROUP_CATEGORIES = [
    ("building", "Building / Tower"),
    ("association", "Resident Association"),
    ("sports", "Sports"),
    ("hobby", "Hobby"),
    ("cultural", "Cultural"),
    ("fitness", "Fitness"),
    ("parents", "Parents"),
    ("senior", "Senior Citizen"),
    ("volunteer", "Volunteer"),
    ("event", "Event-specific"),
    ("professional", "Professional"),
    ("other", "Other"),
]

EVENT_CATEGORIES = [
    ("fitness", "Fitness"),
    ("meetings", "Meetings"),
    ("sports", "Sports"),
    ("activities", "Activities"),
    ("dates", "Important Dates"),
    ("other", "Other"),
]

POLL_CATEGORIES = [
    ("events", "Events & Activities"),
    ("facilities", "Facilities"),
    ("operations", "Operations"),
    ("other", "Other"),
]

FEEDBACK_CATEGORIES = [
    ("facility", "Facility Maintenance"),
    ("amenities", "Amenities"),
    ("events", "Events"),
    ("communication", "Communication"),
    ("other", "Other"),
]

ALLOWED_ATTACHMENT_MIMETYPES = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
})

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
