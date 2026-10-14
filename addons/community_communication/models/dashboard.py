# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _


class CommunityCommunicationDashboard(models.AbstractModel):
    _name = "community.communication.dashboard"
    _description = "Community dashboard and analytics"

    @api.model
    def get_dashboard_data(self):
        now = fields.Datetime.now()
        week_start = now - timedelta(days=now.weekday())
        Announcement = self.env["community.communication.announcement"]
        Discussion = self.env["community.communication.discussion"]
        Poll = self.env["community.communication.poll"]
        Event = self.env["community.communication.event"]
        Feedback = self.env["community.communication.feedback"]

        overview = {
            state: Announcement.search_count([("state", "=", state)])
            for state in ("published", "scheduled", "expired")
        }
        engagement = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            nxt = day + timedelta(days=1)
            day_domain = [("create_date", ">=", day), ("create_date", "<", nxt)]
            engagement.append({
                "label": day.strftime("%a"),
                "announcements": Announcement.search_count(day_domain),
                "discussions": Discussion.search_count(day_domain),
                "polls": Poll.search_count(day_domain),
            })

        events = Event.search(
            [("state", "=", "published"), ("date_start", ">=", now)],
            order="date_start asc",
            limit=5,
        )
        polls = Poll.search([("state", "=", "active")], order="date_end asc", limit=4)

        activity = []
        for rec in Announcement.search([], order="write_date desc", limit=6):
            activity.append(self._activity_row(rec, rec.title, "Announcement", rec.state, rec.author_id))
        for rec in Discussion.search([("state", "!=", "removed")], order="last_activity_at desc", limit=4):
            activity.append(self._activity_row(rec, rec.title, "Discussion", rec.state, rec.author_id))
        for rec in Poll.search([], order="write_date desc", limit=3):
            activity.append(self._activity_row(rec, rec.question, "Poll", rec.state, rec.author_id))
        for rec in Feedback.search([], order="create_date desc", limit=3):
            activity.append(self._activity_row(rec, rec.subject, "Feedback", rec.state, rec.resident_id))
        activity.sort(key=lambda row: row["sort"], reverse=True)

        return {
            "kpis": {
                "announcements": Announcement.search_count([]),
                "discussions": Discussion.search_count([("state", "=", "active")]),
                "polls": Poll.search_count([("state", "=", "active")]),
                "events": Event.search_count([("state", "=", "published"), ("date_start", ">=", now)]),
                "feedback": Feedback.search_count([("state", "in", ["submitted", "in_progress"])]),
            },
            "overview": overview,
            "engagement": engagement,
            "upcoming_events": [{
                "id": event.id,
                "name": event.name,
                "date": event.date_start.isoformat() if event.date_start else "",
                "date_label": event.date_start.strftime("%b %d").upper() if event.date_start else "",
                "location": event.location or (event.venue_id.name or ""),
                "registrations": event.confirmed_count,
                "category": event.category,
            } for event in events],
            "activity": activity[:8],
            "active_polls": [{
                "id": poll.id,
                "question": poll.question,
                "state": poll.state,
                "votes": poll.participant_count,
                "rate": int(round((poll.response_rate or 0.0) * 100)),
            } for poll in polls],
        }

    @api.model
    def announcement_expiring_soon_domain(self):
        now = fields.Datetime.now()
        return [
            ("state", "=", "published"),
            ("date_expiry", "!=", False),
            ("date_expiry", ">=", now),
            ("date_expiry", "<=", now + timedelta(days=7)),
        ]

    @api.model
    def get_list_kpis(self, model_name):
        Model = self.env[model_name]
        if model_name == "community.communication.announcement":
            expiring_domain = self.announcement_expiring_soon_domain()
            return [
                {"key": "all", "label": "Total Announcements", "value": Model.search_count([]), "filter": False},
                {"key": "published", "label": "Published", "value": Model.search_count([("state", "=", "published")]), "filter": "published"},
                {"key": "scheduled", "label": "Scheduled", "value": Model.search_count([("state", "=", "scheduled")]), "filter": "scheduled"},
                {
                    "key": "expiring",
                    "label": "Expiring Soon",
                    "value": Model.search_count(expiring_domain),
                    "filter": "expiring_soon",
                    "tone": "danger",
                },
            ]
        if model_name == "community.communication.discussion":
            return [
                {"key": "all", "label": "Total Discussions", "value": Model.search_count([("state", "!=", "removed")])},
                {"key": "active", "label": "Active Discussions", "value": Model.search_count([("state", "=", "active")]), "filter": "active"},
                {"key": "comments", "label": "Comments", "value": self.env["community.communication.discussion.comment"].search_count([("state", "=", "active")])},
                {
                    "key": "reported",
                    "label": "Reported Content",
                    "value": self.env["community.communication.report"].search_count([("state", "=", "pending")]),
                    "tone": "danger",
                    "action": "community_communication.action_cc_report",
                },
            ]
        if model_name == "community.communication.poll":
            polls = Model.search([])
            participants = sum(polls.mapped("participant_count"))
            avg_rate = int(round(100 * (sum(polls.mapped("response_rate")) / len(polls)))) if polls else 0
            return [
                {"key": "all", "label": "Total Polls", "value": Model.search_count([]), "filter": False},
                {"key": "active", "label": "Active Polls", "value": Model.search_count([("state", "=", "active")]), "filter": "active"},
                {"key": "participants", "label": "Total Participants", "value": participants},
                {"key": "rate", "label": "Response Rate", "value": "%s%%" % avg_rate},
            ]
        if model_name == "community.communication.group":
            groups = Model.search([])
            members = sum(groups.mapped("member_count"))
            engaged = len(groups.filtered(lambda g: g.discussion_ids))
            avg = int(round(100 * engaged / len(groups))) if groups else 0
            return [
                {"key": "all", "label": "Total Groups", "value": len(groups)},
                {"key": "active", "label": "Active Groups", "value": Model.search_count([("state", "=", "active")]), "filter": "active"},
                {"key": "members", "label": "Total Members", "value": members},
                {"key": "engagement", "label": "Avg Engagement", "value": "%s%%" % avg},
            ]
        if model_name == "community.communication.feedback":
            return [
                {"key": "submitted", "label": "Submitted", "value": Model.search_count([("state", "=", "submitted")]), "filter": "submitted"},
                {"key": "in_progress", "label": "In Progress", "value": Model.search_count([("state", "=", "in_progress")]), "filter": "in_progress"},
                {"key": "resolved", "label": "Resolved", "value": Model.search_count([("state", "=", "resolved")]), "filter": "resolved"},
                {"key": "closed", "label": "Closed", "value": Model.search_count([("state", "=", "closed")]), "filter": "closed"},
            ]
        return []

    @api.model
    def get_analytics_data(self, days=30, building_id=False):
        if not self.env.user._cc_is_community_officer():
            raise AccessError(_("Only community staff can access engagement analytics."))
        now = fields.Datetime.now()
        start = now - timedelta(days=int(days or 30))
        domain = [("create_date", ">=", start)]
        building_domain = []
        if building_id:
            building_domain = [("building_ids", "in", [int(building_id)])]

        Announcement = self.env["community.communication.announcement"]
        Discussion = self.env["community.communication.discussion"]
        Poll = self.env["community.communication.poll"]
        Event = self.env["community.communication.event"]
        Feedback = self.env["community.communication.feedback"]
        Registration = self.env["community.communication.event.registration"]

        anns = Announcement.search(domain + building_domain)
        discussions = Discussion.search(domain)
        polls = Poll.search(domain)
        events = Event.search([("date_start", ">=", start)])
        feedback = Feedback.search(domain)

        weeks = []
        for index in range(4):
            w_start = start + timedelta(days=index * 7)
            w_end = w_start + timedelta(days=7)
            weeks.append({
                "label": "Week %s" % (index + 1),
                "announcements": Announcement.search_count([("create_date", ">=", w_start), ("create_date", "<", w_end)]),
                "discussions": Discussion.search_count([("create_date", ">=", w_start), ("create_date", "<", w_end)]),
                "polls": Poll.search_count([("create_date", ">=", w_start), ("create_date", "<", w_end)]),
            })

        views = sum(anns.mapped("view_count"))
        acks = sum(anns.mapped("ack_count"))
        published = len(anns.filtered(lambda a: a.state == "published"))
        most_viewed = anns.sorted("view_count", reverse=True)[:3]

        categories = defaultdict(int)
        for disc in discussions:
            categories[disc.category or "other"] += 1
        cat_total = sum(categories.values()) or 1

        submitted = len(feedback.filtered(lambda f: f.state == "submitted"))
        resolved = len(feedback.filtered(lambda f: f.state in ("resolved", "closed")))

        registrations = Registration.search([("registered_on", ">=", start)])
        attended = registrations.filtered(lambda r: r.state == "attended")
        cancelled = registrations.filtered(lambda r: r.state == "cancelled")

        buildings = self.env["community.communication.building"].search([], limit=8)
        by_building = []
        for building in buildings:
            count = Announcement.search_count([("building_ids", "in", building.ids)])
            count += Event.search_count([("building_id", "=", building.id)])
            by_building.append({"name": building.name, "value": count})

        peak_building = max(by_building, key=lambda row: row["value"]) if by_building else {"name": "—", "value": 0}
        avg_poll_rate = int(round(100 * (sum(polls.mapped("response_rate")) / len(polls)))) if polls else 0

        return {
            "days": int(days or 30),
            "buildings": [{"id": b.id, "name": b.name} for b in buildings],
            "trend": weeks,
            "announcements": {
                "published": published,
                "views": views,
                "view_rate": int(round(100 * sum(anns.mapped("view_rate")) / len(anns))) if anns else 0,
                "ack_rate": int(round(100 * sum(anns.mapped("ack_rate")) / len(anns))) if anns else 0,
                "most_viewed": [{"title": rec.title, "views": rec.view_count} for rec in most_viewed],
            },
            "discussions": {
                "active": Discussion.search_count([("state", "=", "active")]),
                "interactions": sum(discussions.mapped("comment_count")),
                "categories": [
                    {"name": name, "pct": int(round(100 * value / cat_total))}
                    for name, value in sorted(categories.items(), key=lambda item: item[1], reverse=True)[:4]
                ],
            },
            "feedback": {
                "submitted": len(feedback),
                "resolved": resolved,
                "open": submitted,
            },
            "polls": {
                "active": Poll.search_count([("state", "=", "active")]),
                "participants": sum(polls.mapped("participant_count")),
                "avg_rate": avg_poll_rate,
                "bars": [{"name": poll.question[:18], "value": poll.participant_count} for poll in polls[:5]],
            },
            "events": {
                "registrations": len(registrations),
                "attendance": int(round(100 * len(attended) / len(registrations))) if registrations else 0,
                "cancellations": len(cancelled),
            },
            "by_building": by_building,
            "insights": [
                {"label": "Most Engaged Building", "value": peak_building["name"]},
                {"label": "Most Active Category", "value": (max(categories, key=categories.get) if categories else "—")},
                {"label": "Peak Engagement Time", "value": "Not enough data"},
                {"label": "Needs Attention", "value": "Polls (low response)" if avg_poll_rate and avg_poll_rate < 40 else "Healthy engagement"},
            ],
        }

    def _activity_row(self, record, name, type_label, state, author):
        author_name = author.display_name if author else "Anonymous"
        sort = record.write_date or record.create_date
        return {
            "id": record.id,
            "model": record._name,
            "name": name,
            "type": type_label,
            "user": author_name,
            "date": fields.Datetime.to_string(sort) if sort else "",
            "state": state,
            "sort": fields.Datetime.to_string(sort) if sort else "",
        }
