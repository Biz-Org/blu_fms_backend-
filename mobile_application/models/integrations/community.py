# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import html2plaintext


class MobileIntegrationCommunity(models.AbstractModel):
    _name = "mobile.integration.community"
    _description = "Community & Communication integration"

    @property
    def available(self):
        return "community.communication.announcement" in self.env

    def _resident_community_ids(self, user):
        Resident = self.env.get("community.communication.resident")
        if not Resident:
            return []
        residents = Resident.search([("user_id", "=", user.id)])
        return residents.mapped("community_id").ids

    def get_updates(self, user, limit=5):
        if not self.available:
            return {"available": False, "items": []}
        domain = [("state", "=", "published")]
        community_ids = self._resident_community_ids(user)
        if community_ids:
            domain.append(("community_id", "in", community_ids))
        Announcement = self.env["community.communication.announcement"]
        records = Announcement.search(domain, limit=limit, order="date_publish desc, id desc")
        items = []
        for rec in records:
            items.append({
                "id": rec.id,
                "title": rec.title,
                "category": rec.category,
                "date": fields_datetime_to_iso(rec.date_publish),
                "kind": "announcement",
                "route": "community_announcements",
            })
        Notice = self.env.get("community.communication.notice")
        if Notice:
            ndomain = [("state", "=", "published")]
            if community_ids:
                ndomain.append(("community_id", "in", community_ids))
            for rec in Notice.search(ndomain, limit=limit, order="date_publish desc, id desc"):
                items.append({
                    "id": rec.id,
                    "title": rec.title,
                    "category": rec.category or "notice",
                    "date": fields_datetime_to_iso(rec.date_publish),
                    "kind": "notice",
                    "route": "community_notices",
                })
        return {"available": True, "items": items[:limit]}

    def list_announcements(self, user, limit=20, offset=0):
        if not self.available:
            return {"available": False, "items": [], "total": 0}
        domain = [("state", "=", "published")]
        community_ids = self._resident_community_ids(user)
        if community_ids:
            domain.append(("community_id", "in", community_ids))
        Model = self.env["community.communication.announcement"]
        total = Model.search_count(domain)
        records = Model.search(domain, limit=limit, offset=offset, order="date_publish desc, id desc")
        return {
            "available": True,
            "total": total,
            "items": [
                {
                    "id": r.id,
                    "title": r.title,
                    "body_preview": html2plaintext(r.body or "")[:240],
                    "date": fields_datetime_to_iso(r.date_publish),
                }
                for r in records
            ],
        }

    def announcement_detail(self, user, announcement_id):
        if not self.available:
            return {"available": False}
        rec = self.env["community.communication.announcement"].browse(announcement_id)
        rec.check_access("read")
        return {
            "available": True,
            "id": rec.id,
            "title": rec.title,
            "body": rec.body,
            "date": fields_datetime_to_iso(rec.date_publish),
        }

    def list_events(self, user, limit=20):
        if not self.available or "community.communication.event" not in self.env:
            return {"available": False, "items": []}
        domain = [("state", "=", "published")]
        community_ids = self._resident_community_ids(user)
        if community_ids:
            domain.append(("community_id", "in", community_ids))
        Event = self.env["community.communication.event"]
        records = Event.search(domain, limit=limit, order="date_start asc")
        return {
            "available": True,
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "date_start": fields_datetime_to_iso(r.date_start),
                    "venue": r.venue_id.display_name if r.venue_id else "",
                }
                for r in records
            ],
        }

    def list_polls(self, user, limit=20):
        if not self.available or "community.communication.poll" not in self.env:
            return {"available": False, "items": []}
        domain = [("state", "=", "open")]
        community_ids = self._resident_community_ids(user)
        if community_ids:
            domain.append(("community_id", "in", community_ids))
        Poll = self.env["community.communication.poll"]
        records = Poll.search(domain, limit=limit)
        return {
            "available": True,
            "items": [{"id": r.id, "question": r.question} for r in records],
        }


def fields_datetime_to_iso(value):
    if not value:
        return ""
    return fields.Datetime.to_string(value)
