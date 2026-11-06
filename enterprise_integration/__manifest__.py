# -*- coding: utf-8 -*-
{
    'name': 'Enterprise Integration',
    'version': '18.0.1.4.13',
    'category': 'Productivity',
    'summary': 'PrecastMPS Enterprise Integration — APIs, Webhooks, Connectors, Sync, Master Data, Monitoring',
    'description': """
PrecastMPS Enterprise Integration Module
========================================

Installable Odoo 18 application providing:

* Enterprise Integration Dashboard
* API & Webhook Management
* Enterprise Connectors (ERP, CRM, Bank, WhatsApp, Legacy)
* Data Synchronization
* Master Data Integration
* Integration Monitoring & Logs

Exactly six primary UI navigation destinations.
    """,
    'author': 'PrecastMPS',
    'website': 'https://precastmps.example',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/ei_security.xml',
        'security/ir.model.access.csv',
        'security/ei_record_rules.xml',
        'data/ei_sequence_data.xml',
        'data/ei_master_entity_data.xml',
        'data/ei_master_demo_data.xml',
        'data/ei_connector_catalog_data.xml',
        'data/ei_cron_data.xml',
        'views/ei_dashboard_views.xml',
        'views/ei_api_webhook_views.xml',
        'views/ei_connector_views.xml',
        'views/ei_sync_views.xml',
        'views/ei_master_data_views.xml',
        'views/ei_monitoring_views.xml',
        'views/ei_wizard_views.xml',
        'views/ei_client_actions.xml',
        'views/ei_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'enterprise_integration/static/src/scss/ei_variables.scss',
            'enterprise_integration/static/src/js/ei_app.js',
            'enterprise_integration/static/src/xml/ei_app.xml',
            'enterprise_integration/static/src/js/ei_dashboard.js',
            'enterprise_integration/static/src/xml/ei_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
