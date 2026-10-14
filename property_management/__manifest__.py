{
    "name": "Property Management",
    "version": "1.1",
    "category": "Real Estate",
    "summary": "Portfolio dashboard, properties, buildings, units and occupancy",
    "depends": ["base", "mail", "web", "spreadsheet_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "views/property_views.xml",
        "views/structure_views.xml",
        "views/relation_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "property_management/static/src/dashboard/dashboard.js",
            "property_management/static/src/dashboard/dashboard.xml",
            "property_management/static/src/dashboard/dashboard.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
