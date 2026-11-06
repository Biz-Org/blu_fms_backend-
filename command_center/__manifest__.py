# -*- coding: utf-8 -*-
{
    'name': 'Command Center',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'FMS Command Center — alerts, multi-site monitoring, incidents, emergency, reports',
    'description': """
Command Center Module
=====================

Installable Odoo 18 application providing exactly seven primary UI destinations:

* Command Center Dashboard
* Central Alert Management
* Multi-Site & Real-Time Monitoring
* Incident Dashboard
* Emergency Alerts & Escalation
* Command Center Reports
* Command Center Report Builder & Export
    """,
    'author': 'FMS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/cc_security.xml',
        'security/ir.model.access.csv',
        'security/cc_record_rules.xml',
        'data/cc_sequence_data.xml',
        'views/cc_client_actions.xml',
        'views/cc_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'command_center/static/src/scss/cc_variables.scss',
            'command_center/static/src/scss/cc_screens.scss',
            'command_center/static/src/js/cc_utils.js',
            'command_center/static/src/js/screens/dashboard.js',
            'command_center/static/src/js/screens/alerts.js',
            'command_center/static/src/js/screens/monitoring.js',
            'command_center/static/src/js/screens/incidents.js',
            'command_center/static/src/js/screens/emergency.js',
            'command_center/static/src/js/screens/reports.js',
            'command_center/static/src/js/screens/report_builder.js',
            'command_center/static/src/js/cc_app.js',
            'command_center/static/src/xml/cc_app.xml',
            'command_center/static/src/xml/screens/dashboard.xml',
            'command_center/static/src/xml/screens/alerts.xml',
            'command_center/static/src/xml/screens/monitoring.xml',
            'command_center/static/src/xml/screens/incidents.xml',
            'command_center/static/src/xml/screens/emergency.xml',
            'command_center/static/src/xml/screens/reports.xml',
            'command_center/static/src/xml/screens/report_builder.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
