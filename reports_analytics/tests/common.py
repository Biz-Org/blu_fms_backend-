# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, new_test_user, tagged


class ReportsAnalyticsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(
            cls.env,
            login="ra_admin",
            groups="reports_analytics.group_analytics_admin",
        )
        cls.manager = new_test_user(
            cls.env,
            login="ra_manager",
            groups="reports_analytics.group_analytics_manager",
        )
        cls.management = new_test_user(
            cls.env,
            login="ra_management",
            groups="reports_analytics.group_analytics_management",
        )
        cls.other = new_test_user(
            cls.env,
            login="ra_other",
            groups="base.group_user",
        )
        cls.source = cls.env["analytics.data.source"].create({
            "name": "Partners",
            "technical_identifier": "test.res.partner",
            "model_name": "res.partner",
            "module": "base",
            "category": "operations",
        })
        cls.missing_source = cls.env["analytics.data.source"].create({
            "name": "Missing Module",
            "technical_identifier": "test.missing.model",
            "model_name": "fms.does.not.exist",
            "module": "missing_module",
            "category": "maintenance",
        })
