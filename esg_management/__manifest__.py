{
    "name": "ESG & Sustainability",
    "version": "1.0",
    "category": "Real Estate",
    "summary": "Energy, water, carbon, KPI, target, and ESG reporting screens",
    "depends": ["base", "web", "property_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "esg_management/static/src/portal/portal.js",
            "esg_management/static/src/portal/portal.xml",
            "esg_management/static/src/portal/portal.scss",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
