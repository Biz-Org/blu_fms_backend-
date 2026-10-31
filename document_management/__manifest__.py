# -*- coding: utf-8 -*-
{
    'name': 'Document Management',
    'version': '18.0.1.0.31',
    'category': 'Productivity',
    'summary': 'FMS Document Management — repository, versions, access, approval, search, audit',
    'description': """
Document Management Module
==========================

Installable Odoo 18 application providing these primary UI destinations:

* Document Management Dashboard
* Document Repository
* Document Upload
* Document Details
* Access Control & Sharing
* Approval & Expiry
* Document Workflow
* Document Search
* Activity & Audit
    """,
    'author': 'FMS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/dm_security.xml',
        'security/ir.model.access.csv',
        'security/dm_record_rules.xml',
        'data/dm_sequence_data.xml',
        'views/dm_client_actions.xml',
        'views/dm_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'document_management/static/src/scss/dm_variables.scss',
            'document_management/static/src/scss/dm_screens.scss',
            'document_management/static/src/scss/dm_responsive.scss',
            'document_management/static/src/js/dm_utils.js',
            'document_management/static/src/js/screens/dashboard.js',
            'document_management/static/src/js/screens/repository.js',
            'document_management/static/src/js/screens/upload.js',
            'document_management/static/src/js/screens/details.js',
            'document_management/static/src/js/screens/access.js',
            'document_management/static/src/js/screens/approval.js',
            'document_management/static/src/js/screens/search.js',
            'document_management/static/src/js/screens/audit.js',
            'document_management/static/src/js/dm_app.js',
            'document_management/static/src/xml/dm_app.xml',
            'document_management/static/src/xml/screens/dashboard.xml',
            'document_management/static/src/xml/screens/repository.xml',
            'document_management/static/src/xml/screens/upload.xml',
            'document_management/static/src/xml/screens/details.xml',
            'document_management/static/src/xml/screens/access.xml',
            'document_management/static/src/xml/screens/approval.xml',
            'document_management/static/src/xml/screens/search.xml',
            'document_management/static/src/xml/screens/audit.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
