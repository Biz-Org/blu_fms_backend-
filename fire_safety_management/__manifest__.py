# -*- coding: utf-8 -*-
{
    "name": "Fire & Safety Management",
    "version": "18.0.1.7.0",
    "category": "Services/Fire Safety",
    "summary": "Fire & safety inspections, incidents, equipment, drills, and emergency response",
    "description": """
Fire & Safety Management for facility management.

Standalone Odoo 18 addon (FMS module #23) for digital safety audits,
incident logging, mock drills, fire equipment, emergency response,
and safety compliance reporting.
    """,
    "author": "FMS Fire & Safety",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "mail",
    ],
    "data": [
        "security/fire_safety_groups.xml",
        "security/ir.model.access.csv",
        "security/fire_safety_rules.xml",
        "data/ir_sequence_data.xml",
        "data/ir_config_data.xml",
        "data/ir_cron_data.xml",
        "data/mail_template_data.xml",
        "data/checklist_data.xml",
        "views/location_views.xml",
        "views/checklist_views.xml",
        "views/inspection_views.xml",
        "views/finding_views.xml",
        "views/action_views.xml",
        "views/incident_views.xml",
        "views/drill_views.xml",
        "views/equipment_views.xml",
        "views/emergency_views.xml",
        "views/procedure_views.xml",
        "views/contact_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fire_safety_management/static/src/scss/_tokens.scss",
            "fire_safety_management/static/src/scss/fire_safety.scss",
            "fire_safety_management/static/src/owl/ui/**/*",
            "fire_safety_management/static/src/owl/screens/**/*",
        ],
    },
}
