# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.translate import _


class FireSafetyDrill(models.Model):
    _inherit = "fire.safety.drill"

    cc_announcement_id = fields.Many2one(
        "community.communication.announcement",
        string="Community Announcement",
        copy=False,
        readonly=True,
        ondelete="set null",
    )
    cc_announcement_notified = fields.Boolean(
        string="Community Participants Notified",
        copy=False,
        readonly=True,
        help="Set when Schedule Drill / Notify Participants has already published "
             "the linked Community announcement for the current participants.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        drills = super().create(vals_list)
        drills._fs_cc_sync_announcement()
        return drills

    def write(self, vals):
        res = super().write(vals)
        tracked = {
            "participant_ids",
            "name",
            "scheduled_datetime",
            "drill_type",
            "description",
            "conducted_by",
            "property_id",
            "building_id",
            "area_id",
        }
        changed = tracked.intersection(vals)
        if changed:
            # Keep announcement content/audience in sync (sudo inside helper).
            self._fs_cc_sync_announcement()
            # Content/audience changed → a later Notify Participants should re-send.
            if "cc_announcement_notified" not in vals:
                super(FireSafetyDrill, self.sudo()).write({
                    "cc_announcement_notified": False,
                })
        return res

    def action_notify_participants(self):
        """Reuse the Schedule Drill announcement path; never require CC ACLs."""
        super().action_notify_participants()
        statuses = [
            drill._fs_cc_sync_announcement(from_notify_action=True)
            for drill in self
        ]
        if statuses and all(status == "already_notified" for status in statuses):
            return {
                "status": "already_notified",
                "message": _("Participants were already notified for this mock drill."),
            }
        if not any(drill.participant_ids for drill in self):
            return {
                "status": "skipped",
                "message": _("Select at least one participant before notifying."),
            }
        return {
            "status": "notified",
            "message": _("Participants notified via Community Announcements."),
        }

    def _fs_cc_linked_announcement(self):
        """Browse the linked announcement with sudo so FS staff need no CC rights."""
        self.ensure_one()
        Announcement = self.env["community.communication.announcement"].sudo()
        announcement_id = self.sudo().cc_announcement_id.id
        return Announcement.browse(announcement_id) if announcement_id else Announcement

    def _fs_cc_default_community(self):
        Community = self.env["community.communication.community"].sudo()
        company = self.company_id or self.env.company
        community = Community.search([("company_id", "=", company.id)], limit=1)
        if not community:
            community = Community.search([], limit=1)
        if not community:
            community = Community.create({
                "name": company.name or "Community",
                "code": "MAIN",
                "company_id": company.id,
            })
        return community

    def _fs_cc_location_label(self):
        self.ensure_one()
        parts = [
            self.property_id.display_name,
            self.building_id.display_name,
            self.area_id.display_name,
        ]
        return ", ".join(part for part in parts if part) or _("Not specified")

    def _fs_cc_announcement_body(self):
        self.ensure_one()
        when = (
            fields.Datetime.context_timestamp(self, self.scheduled_datetime)
            if self.scheduled_datetime
            else None
        )
        date_label = when.strftime("%Y-%m-%d") if when else _("Not specified")
        time_label = when.strftime("%H:%M") if when else _("Not specified")
        location = self._fs_cc_location_label()
        parts = [
            Markup("<p>%s</p>") % _("A mock drill has been scheduled for you."),
            Markup("<ul>"),
            Markup("<li><strong>%s</strong> %s</li>") % (_("Date:"), date_label),
            Markup("<li><strong>%s</strong> %s</li>") % (_("Time:"), time_label),
            Markup("<li><strong>%s</strong> %s</li>") % (_("Location:"), location),
            Markup("</ul>"),
            Markup("<p>%s</p>") % _("Please participate as scheduled."),
        ]
        if self.description:
            parts.append(Markup("<div>%s</div>") % self.description)
        return Markup("").join(parts)

    def _fs_cc_mark_notified(self, announcement):
        """Link announcement + mark notified without re-entering write sync."""
        self.ensure_one()
        super(FireSafetyDrill, self.sudo()).write({
            "cc_announcement_id": announcement.id,
            "cc_announcement_notified": True,
        })

    def _fs_cc_sync_announcement(self, force_publish=False, from_notify_action=False):
        """
        Create/update the Community announcement for selected participants.

        Always uses sudo for announcement IO so Safety Managers do not need
        Community & Communication ACLs (same approach as Schedule Drill create).
        """
        Announcement = self.env["community.communication.announcement"].sudo()
        last_status = "skipped"
        for drill in self:
            users = drill.participant_ids
            if not users:
                last_status = "skipped"
                continue

            announcement = drill._fs_cc_linked_announcement()
            audience_ids = set(users.ids)

            if (
                from_notify_action
                and drill.sudo().cc_announcement_notified
                and announcement
                and announcement.exists()
                and announcement.state == "published"
                and set(announcement.audience_user_ids.ids) == audience_ids
            ):
                last_status = "already_notified"
                continue

            community = (
                announcement.community_id
                if announcement and announcement.exists()
                else drill._fs_cc_default_community()
            )
            vals = {
                "title": _("Mock Drill: %s") % (drill.name or _("Safety Drill")),
                "body": drill._fs_cc_announcement_body(),
                "category": "safety",
                "priority": "high",
                "community_id": community.id,
                "audience_type": "users",
                "audience_user_ids": [(6, 0, users.ids)],
                "audience_resident_ids": [(5, 0, 0)],
                "author_id": self.env.user.id,
                "date_publish": fields.Datetime.now(),
                "is_pinned": True,
            }

            created_new = False
            if (
                announcement
                and announcement.exists()
                and announcement.state in ("draft", "scheduled", "published")
            ):
                announcement.write({
                    "title": vals["title"],
                    "body": vals["body"],
                    "audience_type": "users",
                    "audience_user_ids": vals["audience_user_ids"],
                    "audience_resident_ids": [(5, 0, 0)],
                    "community_id": community.id,
                    "category": "safety",
                    "priority": "high",
                    "is_pinned": True,
                })
            else:
                announcement = Announcement.create(vals)
                created_new = True

            if announcement.state in ("draft", "scheduled"):
                announcement.action_publish()
                drill._fs_cc_mark_notified(announcement)
                last_status = "notified"
            elif from_notify_action or force_publish:
                announcement._cc_send_mail_template(
                    "community_communication.mail_template_announcement_published"
                )
                drill._fs_cc_mark_notified(announcement)
                last_status = "notified"
            else:
                # Quiet content sync after edits (e.g. participant list change).
                if created_new:
                    drill._fs_cc_mark_notified(announcement)
                    last_status = "notified"
                else:
                    if not drill.sudo().cc_announcement_id:
                        super(FireSafetyDrill, drill.sudo()).write({
                            "cc_announcement_id": announcement.id,
                        })
                    last_status = "updated"

        return last_status
