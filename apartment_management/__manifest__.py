{
    "name": "Apartment Management",
    "version": "1.1",
    "category": "Real Estate",
    "summary": "Tenant portal, lease, payments, maintenance, and staff backend",
    "depends": ["base", "mail", "web", "property_management"],
    "data": [
        "security/apartment_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/payment_views.xml",
        "views/maintenance_views.xml",
        "views/communication_views.xml",
        "views/tenancy_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "apartment_management/static/src/portal/portal.js",
            "apartment_management/static/src/portal/portal.xml",
            "apartment_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
