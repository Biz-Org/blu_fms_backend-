{
    "name": "Resident Management",
    "version": "1.0",
    "category": "Real Estate",
    "summary": "Resident directory, onboarding, KYC, household, move-in/out, and communication",
    "depends": ["base", "mail", "web", "property_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "resident_management/static/src/portal/portal.js",
            "resident_management/static/src/portal/portal.xml",
            "resident_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
