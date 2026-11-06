# -*- coding: utf-8 -*-
{
    "name": "Facility Booking Management",
    "version": "18.0.1.0.0",
    "category": "Facility Management",
    "summary": "Facility reservations, approvals, blocking, payments, and analytics",
    "description": """
Facility Booking Management for FMS — complete booking lifecycle with OWL operational UI.
    """,
    "author": "FMS",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "portal",
        "web",
    ],
    "data": [
        "security/facility_booking_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "data/sequences.xml",
        "data/facility_type_data.xml",
        "data/default_config.xml",
        "data/mail_template_data.xml",
        "data/cron_data.xml",
        "views/facility_views.xml",
        "views/facility_slot_views.xml",
        "views/facility_block_views.xml",
        "views/booking_views.xml",
        "views/booking_configuration_views.xml",
        "views/menus.xml",
        "wizards/booking_reject_wizard_views.xml",
        "wizards/booking_cancel_wizard_views.xml",
        "report/booking_receipt_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "facility_booking_management/static/src/portal/facility_booking.scss",
            "facility_booking_management/static/src/portal/facility_booking.xml",
            "facility_booking_management/static/src/portal/facility_booking.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
