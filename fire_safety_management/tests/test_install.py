# -*- coding: utf-8 -*-

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFireSafetyInstall(TransactionCase):
    def test_module_installed(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "fire_safety_management")],
            limit=1,
        )
        self.assertEqual(module.state, "installed")

    def test_manifest_depends_only_on_mail(self):
        manifest = get_manifest("fire_safety_management")
        self.assertEqual(manifest.get("depends"), ["mail"])
        self.assertNotIn("community_communication", manifest.get("depends"))
        self.assertTrue(manifest.get("application"))
        self.assertTrue(manifest["version"].startswith("18.0"))

    def test_security_groups_exist(self):
        self.env.ref("fire_safety_management.group_fire_safety_manager")
        self.env.ref("fire_safety_management.group_fire_safety_security")
        self.env.ref("fire_safety_management.group_fire_safety_guard")
        self.env.ref("fire_safety_management.group_fire_safety_facility")
        self.env.ref("fire_safety_management.group_fire_safety_auditor")
        self.env.ref("fire_safety_management.group_fire_safety_executive")

    def test_models_registered(self):
        for model in (
            "fire.safety.property",
            "fire.safety.building",
            "fire.safety.area",
            "fire.safety.inspection",
            "fire.safety.checklist.template",
            "fire.safety.checklist.item",
            "fire.safety.inspection.line",
            "fire.safety.finding",
            "fire.safety.action",
            "fire.safety.incident",
            "fire.safety.drill",
            "fire.safety.equipment",
            "fire.safety.emergency",
            "fire.safety.procedure",
            "fire.safety.contact",
            "fire.safety.dashboard",
        ):
            self.assertIn(model, self.env)

    def test_backend_assets_registered(self):
        manifest = get_manifest("fire_safety_management")
        backend = " ".join(str(item) for item in manifest.get("assets", {}).get("web.assets_backend", []))
        self.assertIn("fire_safety_management/static/src/scss/_tokens.scss", backend)
        self.assertIn("fire_safety_management/static/src/scss/fire_safety.scss", backend)
        self.assertIn("fire_safety_management/static/src/owl", backend)

    def test_root_menu_exists(self):
        menu = self.env.ref("fire_safety_management.menu_fire_safety_root")
        self.assertTrue(menu)

    def test_root_menu_opens_owl_dashboard(self):
        menu = self.env.ref("fire_safety_management.menu_fire_safety_root")
        action = self.env["ir.actions.client"].browse(menu.action.id)
        self.assertEqual(action.type, "ir.actions.client")
        self.assertEqual(action.tag, "fire_safety_management.action_dashboard")

    def test_owl_client_actions_registered(self):
        mapping = {
            "action_fs_dashboard_ui": "fire_safety_management.action_dashboard",
            "action_fs_inspections_ui": "fire_safety_management.action_inspections",
            "action_fs_incidents_ui": "fire_safety_management.action_incidents",
            "action_fs_incident_report_ui": "fire_safety_management.action_incidents",
            "action_fs_drills_ui": "fire_safety_management.action_drills",
            "action_fs_drill_create_ui": "fire_safety_management.action_drills",
            "action_fs_equipment_ui": "fire_safety_management.action_equipment",
            "action_fs_equipment_create_ui": "fire_safety_management.action_equipment",
            "action_fs_emergency_ui": "fire_safety_management.action_emergency",
            "action_fs_emergency_activate_ui": "fire_safety_management.action_emergency",
            "action_fs_reports_ui": "fire_safety_management.action_reports",
        }
        for xmlid, tag in mapping.items():
            action = self.env.ref(f"fire_safety_management.{xmlid}")
            self.assertEqual(action.type, "ir.actions.client")
            self.assertEqual(action.tag, tag)
