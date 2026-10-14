{
    "name": "GateFlow AI",
    "version": "1.0",
    "category": "Human Resources",
    "summary": "Gate command, visitors, vehicles, AI validation, and perimeter security",
    "depends": ["base", "mail", "web", "hr", "hr_attendance", "fleet", "maintenance"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gate_management/static/src/portal/portal.js",
            "gate_management/static/src/portal/portal.xml",
            "gate_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
