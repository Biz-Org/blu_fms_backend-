# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, new_test_user


class AiCopilotCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(
            cls.env,
            login="ai_copilot_admin",
            groups="ai_copilot.group_copilot_admin",
        )
        cls.user = new_test_user(
            cls.env,
            login="ai_copilot_user",
            groups="ai_copilot.group_copilot_user",
        )
        cls.other = new_test_user(
            cls.env,
            login="ai_copilot_other",
            groups="base.group_user",
        )
        cls.service = cls.env["ai.copilot.service"]
