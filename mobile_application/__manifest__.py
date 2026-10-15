# -*- coding: utf-8 -*-
{
    "name": "Mobile Application",
    "version": "19.0.1.0.0",
    "category": "Services/Mobile",
    "summary": "Unified mobile-first FMS application for residents, staff, and security",
    "description": """
Mobile-first presentation layer for the Facility Management System.

Provides role-based mobile home, services, bookings, alerts, profile,
visitor management, digital ID, and integrations with other FMS modules
when installed.
    """,
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "mail",
        "web",
    ],
    "data": [
        "security/mobile_groups.xml",
        "security/ir.model.access.csv",
        "security/mobile_rules.xml",
        "data/ir_sequence_data.xml",
        "views/native_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mobile_application/static/src/mobile_app.scss",
            "mobile_application/static/src/utils/**/*.js",
            "mobile_application/static/src/services/**/*.js",
            "mobile_application/static/src/components/**/*.js",
            "mobile_application/static/src/components/**/*.xml",
            "mobile_application/static/src/screens/**/*.js",
            "mobile_application/static/src/screens/**/*.xml",
            "mobile_application/static/src/mobile_app.xml",
            "mobile_application/static/src/screens/mobile_screens.xml",
            "mobile_application/static/src/mobile_app.js",
        ],
    },
}
