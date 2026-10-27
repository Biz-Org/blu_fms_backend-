# -*- coding: utf-8 -*-

import json
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import AiCopilotCase


@tagged("post_install", "-at_install")
class TestAiCopilotFlow(AiCopilotCase):
    def test_missing_provider_still_returns_real_document_facts(self):
        config = self.env["ai.copilot.config"].sudo()._ensure_config()
        config.write({"provider": "none", "api_key": False, "enabled": True})
        self.env["ai.copilot.document"].with_user(self.admin).create({
            "name": "Lobby SOP",
            "category": "sop",
            "summary": "LOBBY_SOP_TOKEN reception closes at 18:00.",
            "body": "LOBBY_SOP_TOKEN reception closes at 18:00.",
        })
        result = self.service.with_user(self.user).ask(False, "What does the lobby SOP say?")
        assistant = result["messages"][-1]
        blob = json.dumps(assistant)
        self.assertIn("LOBBY_SOP_TOKEN", blob)
        self.assertFalse(assistant["payload"]["provider"]["configured"])
        self.assertFalse(assistant["payload"]["provider"]["used"])
        self.assertIn("not configured", assistant["payload"]["provider_note"].lower())
        self.assertNotIn("12 items", blob.lower())

    def test_no_results_does_not_invent_counts(self):
        result = self.service.with_user(self.user).ask(
            False,
            "Show overdue maintenance requests for tower zz-no-such-place",
        )
        assistant = result["messages"][-1]
        self.assertIn(assistant["payload"]["status"], ("no_results", "unavailable", "restricted", "ok"))
        blob = json.dumps(assistant)
        self.assertNotIn("12 items", blob.lower())
        self.assertNotRegex(blob, r"I found [1-9][0-9]*")

    def test_follow_up_uses_previous_documents(self):
        self.env["ai.copilot.document"].with_user(self.admin).create({
            "name": "Weekend amenities",
            "category": "community",
            "body": "AMENITY_POOL_TOKEN The pool is open Saturday.",
        })
        first = self.service.with_user(self.user).ask(False, "What does the weekend amenities SOP say?")
        second = self.service.with_user(self.user).ask(first["id"], "Tell me more about those")
        self.assertEqual(first["id"], second["id"])
        self.assertGreaterEqual(len(second["messages"]), 4)
        self.assertIn("AMENITY_POOL_TOKEN", json.dumps(second["messages"][-1]))

    def test_feedback_and_history(self):
        result = self.service.with_user(self.user).ask(False, "Hello")
        message = result["messages"][-1]
        self.service.with_user(self.user).set_feedback(message["id"], "up")
        stored = self.env["ai.copilot.message"].with_user(self.user).browse(message["id"])
        self.assertEqual(stored.feedback, "up")
        history = self.service.with_user(self.user).list_conversations()
        self.assertTrue(any(item["id"] == result["id"] for item in history))

    def test_equipment_query_uses_authorized_records_only(self):
        if "fire.safety.equipment" not in self.env:
            self.skipTest("Fire & Safety is not installed")
        equipment = self.env["fire.safety.equipment"].sudo().create({
            "name": "Extinguisher North Stair Unique",
            "code": "AI-EXT-991",
            "equipment_type": "fire_extinguisher",
            "service_due_date": fields.Date.context_today(self.env.user) - timedelta(days=2),
        })
        reader = self.env["res.users"].create({
            "name": "Copilot Facility Reader",
            "login": "ai_copilot_facility",
            "groups_id": [(6, 0, [
                self.env.ref("ai_copilot.group_copilot_user").id,
                self.env.ref("fire_safety_management.group_fire_safety_facility").id,
            ])],
        })
        result = self.service.with_user(reader).ask(False, "What equipment needs servicing?")
        assistant = result["messages"][-1]
        self.assertEqual(assistant["payload"]["status"], "ok")
        self.assertIn(equipment.name, json.dumps(assistant))
        source = next(item for item in assistant["payload"]["sources"] if item["model"] == "fire.safety.equipment")
        expected = self.env["fire.safety.equipment"].with_user(reader).search_count([
            "|", "|", "|",
            ("service_due_date", "<=", fields.Date.context_today(reader)),
            ("inspection_due_date", "<=", fields.Date.context_today(reader)),
            ("expiry_date", "<=", fields.Date.context_today(reader)),
            ("state", "in", ["service_due", "inspection_due", "expired", "faulty", "under_maintenance"]),
        ])
        self.assertEqual(source["count"], expected)
        self.assertGreaterEqual(source["count"], 1)
        blocked = self.service.with_user(self.user).ask(False, "What equipment needs servicing?")
        self.assertNotIn(equipment.name, json.dumps(blocked))
        self.assertEqual(blocked["messages"][-1]["payload"]["status"], "restricted")

    def test_bad_provider_url_is_rejected(self):
        with self.assertRaises(Exception):
            self.service.with_user(self.admin).save_settings({
                "provider": "compatible",
                "base_url": "http://example.com/v1",
                "enabled": True,
            })
        config = self.env["ai.copilot.config"].sudo()._ensure_config()
        self.assertNotEqual(config.base_url, "http://example.com/v1")
