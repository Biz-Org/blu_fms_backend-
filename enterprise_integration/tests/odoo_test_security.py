# -*- coding: utf-8 -*-
"""Odoo TransactionCase security tests for EI groups / ACLs / credentials.

Requires Odoo 18 runtime.
"""
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'ei_security')
class TestEiSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_user = cls.env.ref('enterprise_integration.group_ei_user')
        group_manager = cls.env.ref('enterprise_integration.group_ei_manager')
        group_admin = cls.env.ref('enterprise_integration.group_ei_admin')

        cls.user_ei = Users.create({
            'name': 'EI User',
            'login': 'ei_user_test',
            'groups_id': [(6, 0, [group_user.id])],
        })
        cls.manager_ei = Users.create({
            'name': 'EI Manager',
            'login': 'ei_manager_test',
            'groups_id': [(6, 0, [group_manager.id])],
        })
        cls.admin_ei = Users.create({
            'name': 'EI Admin',
            'login': 'ei_admin_test',
            'groups_id': [(6, 0, [group_admin.id])],
        })

        cls.integration = cls.env['ei.integration'].create({
            'name': 'Sec Integration',
            'code': 'SEC-INT-001',
            'state': 'active',
        })
        cls.endpoint = cls.env['ei.api.endpoint'].create({
            'name': 'Secure EP',
            'integration_id': cls.integration.id,
            'path': 'secure',
            'method': 'GET',
            'state': 'active',
        })

    def test_user_can_read_integration(self):
        rec = self.env['ei.integration'].with_user(self.user_ei).browse(self.integration.id)
        self.assertEqual(rec.name, 'Sec Integration')

    def test_user_cannot_create_integration(self):
        with self.assertRaises(AccessError):
            self.env['ei.integration'].with_user(self.user_ei).create({
                'name': 'Nope',
                'code': 'NOPE',
            })

    def test_user_cannot_access_credentials_model(self):
        with self.assertRaises(AccessError):
            self.env['ei.api.credential'].with_user(self.user_ei).create({
                'name': 'Hack',
                'endpoint_id': self.endpoint.id,
            })

    def test_manager_can_configure_endpoint(self):
        ep = self.env['ei.api.endpoint'].with_user(self.manager_ei).create({
            'name': 'Mgr EP',
            'integration_id': self.integration.id,
            'path': 'mgr-ep',
            'method': 'POST',
        })
        self.assertTrue(ep.id)

    def test_manager_can_create_credential_masked(self):
        cred = self.env['ei.api.credential'].with_user(self.manager_ei).create({
            'name': 'Mgr Key',
            'endpoint_id': self.endpoint.id,
            'plaintext_key': 'manager-secret-key-001',
        })
        self.assertTrue(cred.key_prefix)
        # Manager read should not expose raw hash to non-admin via read()
        data = cred.with_user(self.manager_ei).read(['key_hash', 'secret_display'])[0]
        self.assertFalse(data.get('key_hash'))

    def test_admin_can_read_key_hash(self):
        cred = self.env['ei.api.credential'].with_user(self.admin_ei).create({
            'name': 'Admin Key',
            'endpoint_id': self.endpoint.id,
            'plaintext_key': 'admin-secret-key-001',
        })
        data = cred.with_user(self.admin_ei).read(['key_hash'])[0]
        self.assertTrue(data.get('key_hash'))

    def test_user_can_read_logs(self):
        log = self.env['ei.log'].sudo().ei_log(
            name='visible',
            category='system',
            level='success',
            integration_id=self.integration.id,
        )
        seen = self.env['ei.log'].with_user(self.user_ei).browse(log.id)
        self.assertEqual(seen.name, 'visible')

    def test_user_cannot_export_wizard(self):
        with self.assertRaises(AccessError):
            self.env['ei.log.export.wizard'].with_user(self.user_ei).create({})

    def test_manager_can_retry_delivery_write(self):
        wh = self.env['ei.webhook'].with_user(self.manager_ei).create({
            'name': 'WH',
            'integration_id': self.integration.id,
            'code': 'sec-wh-1',
            'direction': 'incoming',
            'state': 'active',
        })
        delivery = self.env['ei.webhook.delivery'].sudo().create({
            'webhook_id': wh.id,
            'status': 'failed',
        })
        delivery.with_user(self.manager_ei).action_retry()
        self.assertEqual(delivery.status, 'retrying')
