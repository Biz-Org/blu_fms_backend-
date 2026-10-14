# -*- coding: utf-8 -*-
{
    "name": "Community & Communication",
    "version": "19.0.1.9.3",
    "category": "Services/Community",
    "summary": "Community engagement and communication for facility management",
    "description": """
Community engagement and communication for facility management.

Standalone Odoo 19 addon for announcements, forums, polls, events,
notices, resident feedback, groups, and engagement analytics.
    """,
    "author": "FMS Community",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
    "depends": [
        "mail",
        "portal",
    ],
    "data": [
        "security/community_communication_groups.xml",
        "security/ir.model.access.csv",
        "security/community_communication_rules.xml",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "data/mail_template_data.xml",
        "views/community_views.xml",
        "views/announcement_views.xml",
        "views/discussion_views.xml",
        "views/poll_views.xml",
        "views/event_views.xml",
        "views/notice_views.xml",
        "views/feedback_views.xml",
        "views/group_views.xml",
        "views/menus.xml",
        "security/community_communication_webclient_rules.xml",
        "data/cc_sync_access.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_communication/static/src/scss/_tokens.scss",
            "community_communication/static/src/scss/community_communication.scss",
            "community_communication/static/src/owl/utils.js",
            "community_communication/static/src/owl/cc_action.js",
            "community_communication/static/src/owl/ui/**/*",
            "community_communication/static/src/owl/screens/**/*",
        ],
        "web.assets_frontend": [
            "community_communication/static/src/portal/portal.scss",
        ],
    },
}
