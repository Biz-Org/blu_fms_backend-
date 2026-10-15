# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests.common import new_test_user


class MobileApplicationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resident = new_test_user(
            cls.env,
            login="mob_resident",
            groups="mobile_application.group_mobile_resident",
        )
        cls.staff = new_test_user(
            cls.env,
            login="mob_staff",
            groups="mobile_application.group_mobile_staff",
        )
        cls.security = new_test_user(
            cls.env,
            login="mob_security",
            groups="mobile_application.group_mobile_security",
        )
        cls.other = new_test_user(
            cls.env,
            login="mob_other",
            groups="base.group_user",
        )
        cls.api = cls.env["mobile.application.service"]
