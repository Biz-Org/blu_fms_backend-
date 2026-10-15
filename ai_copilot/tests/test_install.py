# -*- coding: utf-8 -*-

from odoo.modules.module import get_manifest
from odoo.tests import tagged

from .common import AiCopilotCase


@tagged("post_install", "-at_install")
class TestAiCopilotInstall(AiCopilotCase):
    def test_models_and_groups(self):
        for model in (
            "ai.copilot.config",
            "ai.copilot.conversation",
            "ai.copilot.message",
            "ai.copilot.document",
            "ai.copilot.audit",
            "ai.copilot.service",
        ):
            self.assertIn(model, self.env)
        self.env.ref("ai_copilot.group_copilot_user")
        self.env.ref("ai_copilot.group_copilot_admin")
        self.assertTrue(self.env["ai.copilot.config"].sudo().search_count([]))

    def test_root_menu_opens_client_action(self):
        menu = self.env.ref("ai_copilot.menu_ai_copilot_root")
        action = self.env.ref("ai_copilot.action_ai_copilot")
        self.assertEqual(menu.action, action)
        self.assertEqual(action.type, "ir.actions.client")
        self.assertEqual(action.tag, "ai_copilot.action_copilot")
        self.assertEqual(action.path, "ai-copilot")
        native = self.env.ref("ai_copilot.action_ai_copilot_document")
        self.assertEqual(native.type, "ir.actions.act_window")
        self.assertNotEqual(native.path, "ai-copilot")

    def test_backend_assets_registered(self):
        manifest = get_manifest("ai_copilot")
        backend = " ".join(str(item) for item in manifest.get("assets", {}).get("web.assets_backend", []))
        self.assertIn("ai_copilot/static/src/scss/_tokens.scss", backend)
        self.assertIn("ai_copilot/static/src/owl/ui", backend)
        self.assertIn("ai_copilot/static/src/owl/screens", backend)
