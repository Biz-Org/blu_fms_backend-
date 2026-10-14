{
    "name": "Workforce Management",
    "version": "1.0",
    "category": "Human Resources",
    "summary": "Staff, technicians, shifts, roster, attendance, leave, skills, and tasks",
    "depends": ["base", "web", "hr", "hr_attendance"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "workforce_management/static/src/portal/portal.js",
            "workforce_management/static/src/portal/portal.xml",
            "workforce_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
