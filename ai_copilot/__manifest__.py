# -*- coding: utf-8 -*-
{
    "name": "AI Copilot",
    "version": "18.0.1.0.0",
    "category": "FMS",
    "summary": "Permission-aware AI assistant for facility management",
    "description": """
AI Copilot for facility management.

Conversational assistant that answers from FMS records and approved
knowledge documents the current user is allowed to read. Generative
responses use a server-side provider configuration. Changes to FMS
data are proposed in the chat and run only after confirmation, using
the user's normal Odoo access rights.
    """,
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
    "depends": [
        "web",
    ],
    "data": [
        "security/copilot_groups.xml",
        "security/ir.model.access.csv",
        "security/copilot_rules.xml",
        "data/config_data.xml",
        "views/copilot_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_copilot/static/src/scss/_tokens.scss",
            "ai_copilot/static/src/scss/ai_copilot.scss",
            "ai_copilot/static/src/owl/ui/**/*",
            "ai_copilot/static/src/owl/screens/**/*",
        ],
    },
}
