# -*- coding: utf-8 -*-
{
    'name': 'Workflow Engine',
    'version': '18.0.1.8.2',
    'category': 'Productivity',
    'summary': 'PrecastMPS Workflow Engine — process builder, approvals, tasks, notifications',
    'description': """
PrecastMPS Workflow Engine Module
=================================

Installable Odoo 18 application providing:

* Workflow Engine Dashboard
* Workflow Builder
* Workflow Templates
* Approval & Rule Management
* Task & Execution Management
* Notifications & Approval Tracking
* Workflow Analytics & Reports

Exactly seven primary UI navigation destinations.
    """,
    'author': 'PrecastMPS',
    'website': 'https://precastmps.example',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/we_security.xml',
        'security/ir.model.access.csv',
        'security/we_record_rules.xml',
        'data/we_cron_data.xml',
        'views/we_client_actions.xml',
        'views/we_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'workflow_engine/static/src/scss/we_variables.scss',
            'workflow_engine/static/src/scss/we_activity_clip.css',
            'workflow_engine/static/src/js/we_utils.js',
            'workflow_engine/static/src/js/we_mockup.js',
            'workflow_engine/static/src/js/screens/we_dashboard.js',
            'workflow_engine/static/src/js/screens/we_builder.js',
            'workflow_engine/static/src/js/screens/we_templates.js',
            'workflow_engine/static/src/js/screens/we_approvals.js',
            'workflow_engine/static/src/js/screens/we_tasks.js',
            'workflow_engine/static/src/js/screens/we_notifications.js',
            'workflow_engine/static/src/js/screens/we_analytics.js',
            'workflow_engine/static/src/js/we_app.js',
            'workflow_engine/static/src/xml/we_app.xml',
            'workflow_engine/static/src/xml/screens/we_dashboard.xml',
            'workflow_engine/static/src/xml/screens/we_builder.xml',
            'workflow_engine/static/src/xml/screens/we_templates.xml',
            'workflow_engine/static/src/xml/screens/we_approvals.xml',
            'workflow_engine/static/src/xml/screens/we_tasks.xml',
            'workflow_engine/static/src/xml/screens/we_notifications.xml',
            'workflow_engine/static/src/xml/screens/we_analytics.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
