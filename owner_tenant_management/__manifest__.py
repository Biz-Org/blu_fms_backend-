{
    "name": "Owner Tenant Management",
    "version": "1.0",
    "category": "Real Estate",
    "summary": "Owner and tenant portal: property, lease, payments, ledger, maintenance, messages",
    "depends": ["base", "mail", "web", "property_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "owner_tenant_management/static/src/portal/portal.js",
            "owner_tenant_management/static/src/portal/portal.xml",
            "owner_tenant_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
