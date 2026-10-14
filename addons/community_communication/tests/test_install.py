# -*- coding: utf-8 -*-

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommunityCommunicationInstall(TransactionCase):
    def test_module_installed(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "community_communication")],
            limit=1,
        )
        self.assertEqual(module.state, "installed")

    def test_security_groups_exist(self):
        self.env.ref("community_communication.group_community_resident")
        self.env.ref("community_communication.group_community_officer")
        self.env.ref("community_communication.group_community_moderator")
        self.env.ref("community_communication.group_community_admin")

    def test_admin_implies_officer(self):
        admin_group = self.env.ref("community_communication.group_community_admin")
        officer_group = self.env.ref("community_communication.group_community_officer")
        self.assertIn(officer_group, admin_group.all_implied_ids)

    def test_resident_implies_portal_not_internal(self):
        resident = self.env.ref("community_communication.group_community_resident")
        self.assertIn(self.env.ref("base.group_portal"), resident.all_implied_ids)
        self.assertNotIn(self.env.ref("base.group_user"), resident.all_implied_ids)

    def test_root_menu_and_dashboard_action(self):
        menu = self.env.ref("community_communication.menu_community_communication_root")
        action = self.env.ref("community_communication.action_community_dashboard")
        self.assertEqual(menu.action, action)
        self.assertEqual(action.tag, "community_communication.action_dashboard")

    def test_backend_assets_registered(self):
        manifest = get_manifest("community_communication")
        backend = manifest.get("assets", {}).get("web.assets_backend", [])
        listed = " ".join(str(item) for item in backend)
        self.assertIn("community_communication/static/src/scss/_tokens.scss", listed)
        self.assertIn("community_communication/static/src/owl", listed)
        self.assertIn("community_communication/static/src/owl/ui", listed)
        self.assertTrue(
            any("owl/ui" in str(item) for item in backend),
            "Stitch shell and shared OWL UI must be in backend assets",
        )

    def test_feature_menus_use_client_actions(self):
        mapping = {
            "menu_cc_announcement": "community_communication.action_announcements",
            "menu_cc_discussion": "community_communication.action_discussions",
            "menu_cc_poll": "community_communication.action_polls",
            "menu_cc_event": "community_communication.action_events",
            "menu_cc_registration": "community_communication.action_registrations",
            "menu_cc_notice": "community_communication.action_notices",
            "menu_cc_notice_board": "community_communication.action_notices",
            "menu_cc_feedback": "community_communication.action_feedback",
            "menu_cc_group": "community_communication.action_groups",
        }
        for menu_xmlid, tag in mapping.items():
            menu = self.env.ref(f"community_communication.{menu_xmlid}")
            action = self.env["ir.actions.client"].browse(menu.action.id)
            self.assertEqual(action.type, "ir.actions.client", menu_xmlid)
            self.assertEqual(action.tag, tag, menu_xmlid)
