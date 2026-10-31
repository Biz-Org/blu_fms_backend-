# -*- coding: utf-8 -*-
{
    'name': 'Utility Management',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'FMS Utility Management',
    'description': """
Utility Management
==================

Core domain for electricity, water, and gas monitoring.
Twelve primary screens. Business records stay behind the UI API.
    """,
    'author': 'FMS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/utility_security.xml',
        'security/ir.model.access.csv',
        'security/utility_record_rules.xml',
        'data/utility_sequence_data.xml',
        'data/utility_mail_template_data.xml',
        'report/utility_report_templates.xml',
        'data/utility_cron_data.xml',
        'views/utility_client_actions.xml',
        'views/utility_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'utility_management/static/src/scss/utility_shell.scss',
            'utility_management/static/src/js/utility_app.js',
            'utility_management/static/src/xml/utility_app.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
