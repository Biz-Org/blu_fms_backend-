# -*- coding: utf-8 -*-
{
    "name": "Integration & IoT Management",
    "version": "19.0.1.0.0",
    "category": "Services/IoT",
    "summary": "IoT devices, BMS monitoring, building automation, and energy visibility",
    "description": """
Integration & IoT Management for facility management.

Standalone Odoo 19 addon for connected devices and BMS integrations,
sensor data, lighting/HVAC/fire-alarm/environmental monitoring,
automation rules, embedded alerts, and energy consumption visibility.

Does not claim a live vendor connection. Mock/simulated adapters are
used until a real integration is configured.
    """,
    "author": "FMS Integration",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "mail",
    ],
    "data": [
        "security/iot_groups.xml",
        "security/ir.model.access.csv",
        "security/iot_rules.xml",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "views/location_views.xml",
        "views/integration_views.xml",
        "views/device_views.xml",
        "views/sensor_views.xml",
        "views/schedule_views.xml",
        "views/automation_views.xml",
        "views/alert_views.xml",
        "views/energy_views.xml",
        "views/menus.xml",
        "data/iot_users.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "integration_iot_management/static/src/scss/_tokens.scss",
            "integration_iot_management/static/src/scss/integration_iot.scss",
            "integration_iot_management/static/src/owl/ui/**/*",
            "integration_iot_management/static/src/owl/screens/**/*",
        ],
    },
}
