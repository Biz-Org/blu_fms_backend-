# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import CommunityCommunicationCase


@tagged("post_install", "-at_install")
class TestEventWorkflow(CommunityCommunicationCase):
    def _event_vals(self, **extra):
        vals = {
            "name": "Community Sports Day",
            "community_id": self.community.id,
            "date_start": fields.Datetime.now() + timedelta(days=5),
            "date_end": fields.Datetime.now() + timedelta(days=5, hours=3),
            "require_registration": True,
            "capacity": 50,
        }
        vals.update(extra)
        return vals

    def test_officer_can_create_and_publish_event(self):
        event = self.env["community.communication.event"].with_user(self.officer).create(
            self._event_vals()
        )
        self.assertEqual(event.state, "draft")
        event.with_user(self.officer).action_publish()
        self.assertEqual(event.state, "published")

    def test_resident_cannot_create_or_publish_event(self):
        with self.assertRaises(AccessError):
            self.env["community.communication.event"].with_user(self.portal_user).create(
                self._event_vals(name="Rogue Event")
            )
        event = self.env["community.communication.event"].create(self._event_vals())
        with self.assertRaises(AccessError):
            event.with_user(self.portal_user).action_publish()
        with self.assertRaises(AccessError):
            event.with_user(self.portal_user).write({"name": "Hacked"})
        with self.assertRaises(AccessError):
            event.with_user(self.portal_user).action_cancel()

    def test_published_event_visible_draft_hidden(self):
        draft = self.env["community.communication.event"].create(self._event_vals(name="Draft Picnic"))
        published = self.env["community.communication.event"].create(self._event_vals(name="Published Picnic"))
        published.action_publish()
        Event = self.env["community.communication.event"].with_user(self.portal_user)
        self.assertFalse(Event.search([("id", "=", draft.id)]))
        self.assertTrue(Event.search([("id", "=", published.id)]))

    def test_resident_register_links_event_and_resident(self):
        event = self.env["community.communication.event"].create(self._event_vals())
        event.action_publish()
        registration = event.with_user(self.portal_user).action_register()
        self.assertEqual(registration.event_id, event)
        self.assertEqual(registration.resident_id, self.resident)
        self.assertEqual(registration.state, "confirmed")
        self.assertEqual(event.confirmed_count, 1)
        mine = event.with_user(self.portal_user).get_my_registration()
        self.assertEqual(mine["id"], registration.id)
        self.assertEqual(mine["state"], "confirmed")

    def test_duplicate_registration_rejected(self):
        event = self.env["community.communication.event"].create(self._event_vals())
        event.action_publish()
        event.with_user(self.portal_user).action_register()
        with self.assertRaises(UserError):
            event.with_user(self.portal_user).action_register()
        with self.assertRaises(UserError):
            self.env["community.communication.event.registration"].with_user(self.portal_user).create({
                "event_id": event.id,
                "resident_id": self.resident.id,
            })

    def test_resident_can_unregister_own_only(self):
        event = self.env["community.communication.event"].create(self._event_vals(capacity=0))
        event.action_publish()
        own = event.with_user(self.portal_user).action_register()
        other = event.with_user(self.portal_user_b).action_register()
        event.with_user(self.portal_user).action_unregister()
        self.assertEqual(own.state, "cancelled")
        self.assertEqual(other.state, "confirmed")
        with self.assertRaises(AccessError):
            other.with_user(self.portal_user).write({"state": "cancelled"})
        with self.assertRaises(AccessError):
            other.with_user(self.portal_user).action_cancel()

    def test_resident_cannot_staff_registration_actions(self):
        event = self.env["community.communication.event"].create(self._event_vals())
        event.action_publish()
        registration = event.with_user(self.portal_user).action_register()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_confirm()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_reject()
        with self.assertRaises(AccessError):
            registration.with_user(self.portal_user).action_attended()

    def test_officer_can_manage_registrations(self):
        event = self.env["community.communication.event"].create(self._event_vals(capacity=1))
        event.action_publish()
        first = event.with_user(self.portal_user).action_register()
        second = event.with_user(self.portal_user_b).action_register()
        self.assertEqual(second.state, "waitlisted")
        seen = event.with_user(self.officer).registration_ids
        self.assertIn(first, seen)
        self.assertIn(second, seen)
        first.with_user(self.officer).action_attended()
        self.assertEqual(first.state, "attended")
        second.with_user(self.officer).action_reject()
        self.assertEqual(second.state, "rejected")

    def test_capacity_waitlist_and_unlimited(self):
        limited = self.env["community.communication.event"].create(self._event_vals(capacity=1, name="Limited"))
        limited.action_publish()
        first = limited.with_user(self.portal_user).action_register()
        second = limited.with_user(self.portal_user_b).action_register()
        self.assertEqual(first.state, "confirmed")
        self.assertEqual(second.state, "waitlisted")
        self.assertEqual(limited.confirmed_count, 1)
        self.assertEqual(limited.spots_available, 0)

        unlimited = self.env["community.communication.event"].create(
            self._event_vals(capacity=0, name="Unlimited")
        )
        unlimited.action_publish()
        confirmed = unlimited.with_user(self.portal_user).action_register()
        self.assertEqual(confirmed.state, "confirmed")
        self.assertEqual(unlimited.spots_available, 0)
        self.assertFalse(unlimited.capacity)

    def test_registration_deadline(self):
        event = self.env["community.communication.event"].create(self._event_vals(
            date_deadline=fields.Datetime.now() - timedelta(hours=1),
        ))
        event.action_publish()
        with self.assertRaises(UserError):
            event.with_user(self.portal_user).action_register()

    def test_event_audience_buildings(self):
        event = self.env["community.communication.event"].create(self._event_vals(
            audience_type="buildings",
            building_ids=[(6, 0, self.building_a.ids)],
        ))
        event.action_publish()
        Event = self.env["community.communication.event"]
        self.assertTrue(Event.with_user(self.portal_user).search([("id", "=", event.id)]))
        self.assertFalse(Event.with_user(self.portal_user_b).search([("id", "=", event.id)]))
