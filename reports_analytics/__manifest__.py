# -*- coding: utf-8 -*-
{
    "name": "Reports & Analytics",
    "version": "18.0.2.0.1",
    "category": "FMS",
    "summary": "Reports, analytics, KPIs and dashboards for FMS",
    "description": """
Reports & Analytics for facility management.

Standalone Odoo 18 addon that reads authorized data from FMS operational
modules and exposes report definitions, KPIs, dashboards, execution history,
scheduled delivery, alerts, and audit trails without duplicating operational records.
    """,
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
    "depends": [
        "mail",
    ],
    "data": [
        "security/analytics_groups.xml",
        "security/ir.model.access.csv",
        "security/analytics_rules.xml",
        "data/data_source_data.xml",
        "data/kpi_data.xml",
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
        "report/execution_report.xml",
        "views/report_views.xml",
        "views/kpi_views.xml",
        "views/dashboard_views.xml",
        "views/execution_views.xml",
        "views/data_source_views.xml",
        "views/schedule_views.xml",
        "views/alert_views.xml",
        "views/audit_log_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "reports_analytics/static/src/scss/_tokens.scss",
            "reports_analytics/static/src/scss/reports_analytics.scss",
            "reports_analytics/static/src/owl/ui/**/*",
            "reports_analytics/static/src/owl/screens/ra_screen.js",
            "reports_analytics/static/src/owl/screens/**/*",
        ],
    },
}
