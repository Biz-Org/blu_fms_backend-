# Part of Preventive Maintenance Management. See LICENSE file for full copyright and licensing details.
{
    "name": "Preventive Maintenance Management",
    "version": "18.0.1.0.1",
    "category": "Maintenance",
    "summary": "Planned and recurring preventive maintenance for facility assets",
    "description": """
Preventive Maintenance — planned maintenance, schedules, work orders,
checklists, inspection, history and reporting (FMS Module 12).
    """,
    "author": "FMS",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "mail",
        "maintenance",
        "product",
        "uom",
    ],
    "data": [
        "security/pm_security.xml",
        "security/ir.model.access.csv",
        "data/pm_sequences.xml",
        "data/pm_cron.xml",
        "views/pm_client_action.xml",
        "views/pm_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "preventive_maintenance/static/src/scss/pm_app.scss",
            "preventive_maintenance/static/src/xml/pm_app.xml",
            "preventive_maintenance/static/src/js/pm_app.js",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
}
