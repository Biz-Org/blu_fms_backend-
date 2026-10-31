# -*- coding: utf-8 -*-
{
    'name': 'Video Analytics',
    'version': '18.0.0.30.0',
    'category': 'Productivity',
    'summary': 'FMS Video Analytics — cameras, events, AI detection, occupancy',
    'description': """
Video Analytics Module
======================

Installable Odoo 18 application providing exactly six primary UI destinations:

* Video Analytics Dashboard
* CCTV Integration & Live Streaming
* Video Event Playback & Investigation
* AI Detection & Zone Monitoring
* Occupancy & Crowd Monitoring
* Video-Based Alerts & Event Management
    """,
    'author': 'FMS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/va_security.xml',
        'security/ir.model.access.csv',
        'security/va_record_rules.xml',
        'data/va_sequence_data.xml',
        'views/va_client_actions.xml',
        'views/va_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'video_analytics/static/src/scss/va_variables.scss',
            'video_analytics/static/src/js/va_utils.js',
            'video_analytics/static/src/js/screens/va_dashboard.js',
            'video_analytics/static/src/js/screens/va_cctv.js',
            'video_analytics/static/src/js/screens/va_playback.js',
            'video_analytics/static/src/js/screens/va_detection.js',
            'video_analytics/static/src/js/screens/va_occupancy.js',
            'video_analytics/static/src/js/screens/va_alerts.js',
            'video_analytics/static/src/js/va_app.js',
            'video_analytics/static/src/xml/va_shared.xml',
            'video_analytics/static/src/xml/va_app.xml',
            'video_analytics/static/src/xml/screens/va_dashboard.xml',
            'video_analytics/static/src/xml/screens/va_cctv.xml',
            'video_analytics/static/src/xml/screens/va_playback.xml',
            'video_analytics/static/src/xml/screens/va_detection.xml',
            'video_analytics/static/src/xml/screens/va_occupancy.xml',
            'video_analytics/static/src/xml/screens/va_alerts.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
