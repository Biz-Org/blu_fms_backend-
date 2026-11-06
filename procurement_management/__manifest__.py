# -*- coding: utf-8 -*-
{
    'name': 'Procurement Management',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'FMS Procurement Management foundation',
    'description': """
Procurement Management
======================

Procurement domain for Facility Management.

Twelve primary screens. Business rules run on the server.
    """,
    'author': 'FMS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/pm_security.xml',
        'security/ir.model.access.csv',
        'security/pm_record_rules.xml',
        'data/pm_sequence_data.xml',
        'data/pm_mail_template_data.xml',
        'data/pm_cron_data.xml',
        'report/pm_report_templates.xml',
        'views/pm_client_actions.xml',
        'views/pm_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'procurement_management/static/src/scss/pm_variables.scss',
            'procurement_management/static/src/scss/pm_shell.scss',
            'procurement_management/static/src/scss/pm_ui.scss',
            'procurement_management/static/src/js/pm_app.js',
            'procurement_management/static/src/xml/pm_app.xml',
            'procurement_management/static/src/xml/pm_screens.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
