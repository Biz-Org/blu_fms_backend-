# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .constants import ANNOUNCEMENT_CATEGORIES


class CommunityCommunicationAnnouncement(models.Model):
    _name = "community.communication.announcement"
    _description = "Community Announcement"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.audience.mixin",
        "community.communication.attachment.mixin",
        "community.communication.state.mixin",
    ]
    _order = "is_pinned desc, date_publish desc, id desc"
    _rec_name = "title"
    _cc_state_transitions = {
        "draft": {"scheduled", "published", "archived"},
        "scheduled": {"published", "draft", "archived"},
        "published": {"expired", "archived"},
        "expired": {"archived"},
        "archived": {"draft"},
    }

    title = fields.Char(required=True, tracking=True)
    body = fields.Html(sanitize=True)
    category = fields.Selection(ANNOUNCEMENT_CATEGORIES, required=True, default="general")
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("published", "Published"),
            ("expired", "Expired"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    is_pinned = fields.Boolean(string="Pinned")
    building_ids = fields.Many2many(
        "community.communication.building",
        "cc_announcement_building_rel",
        "announcement_id",
        "building_id",
        domain="[('community_id', '=', community_id)]",
    )
    audience_group_ids = fields.Many2many(
        "community.communication.group",
        "cc_announcement_group_rel",
        "announcement_id",
        "group_id",
        domain="[('community_id', '=', community_id)]",
    )
    audience_resident_ids = fields.Many2many(
        "community.communication.resident",
        "cc_announcement_resident_rel",
        "announcement_id",
        "resident_id",
        string="Audience Residents",
        domain="[('community_id', '=', community_id)]",
    )
    audience_user_ids = fields.Many2many(
        "res.users",
        "cc_announcement_user_rel",
        "announcement_id",
        "user_id",
        string="Audience Users",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "cc_announcement_attach_rel",
        "announcement_id",
        "attachment_id",
        string="Attachments",
    )
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    author_name = fields.Char(compute="_compute_author_name")
    date_publish = fields.Datetime(string="Publish Date", index=True)
    date_expiry = fields.Datetime(string="Expiry Date")
    view_ids = fields.One2many(
        "community.communication.announcement.view",
        "announcement_id",
        string="Views",
    )
    ack_ids = fields.One2many(
        "community.communication.announcement.ack",
        "announcement_id",
        string="Acknowledgements",
    )
    view_count = fields.Integer(compute="_compute_engagement", store=True)
    ack_count = fields.Integer(compute="_compute_engagement", store=True)
    reach_count = fields.Integer(compute="_compute_reach")
    view_rate = fields.Float(compute="_compute_reach")
    ack_rate = fields.Float(compute="_compute_reach")

    @api.depends("author_id")
    def _compute_author_name(self):
        # Portal residents cannot read res.users; expose a safe display name.
        for record in self:
            record.author_name = record.sudo().author_id.display_name or ""

    @api.depends("view_ids", "ack_ids")
    def _compute_engagement(self):
        for record in self:
            record.view_count = len(record.view_ids)
            record.ack_count = len(record.ack_ids)

    def _compute_reach(self):
        for record in self:
            if record.audience_type == "users":
                # Count via sudo so residents are not blocked by res.users ACLs.
                reach = len(record.sudo().audience_user_ids)
            else:
                reach = len(record._cc_audience_resident_ids()) if record.community_id else 0
            record.reach_count = reach
            record.view_rate = (record.view_count / reach) if reach else 0.0
            record.ack_rate = (record.ack_count / reach) if reach else 0.0

    @api.constrains("date_publish", "date_expiry")
    def _check_dates(self):
        for record in self:
            if record.date_publish and record.date_expiry and record.date_expiry < record.date_publish:
                raise ValidationError(_("Expiry date must be after the publish date."))

    def action_schedule(self):
        self._cc_require_officer()
        for record in self:
            if not record._cc_has_html_text(record.body):
                raise UserError(_("Content is required before scheduling."))
            if not record.date_publish:
                raise UserError(_("Set a publish date before scheduling."))
            if record.date_publish <= fields.Datetime.now():
                raise UserError(_("Scheduled publish date must be in the future."))
        self._cc_set_state("scheduled")

    def action_publish(self):
        self._cc_require_officer()
        now = fields.Datetime.now()
        for record in self:
            if not record._cc_has_html_text(record.body):
                raise UserError(_("Content is required before publishing."))
            vals = {}
            if not record.date_publish:
                vals["date_publish"] = now
            if vals:
                record.write(vals)
        self._cc_set_state("published")
        self._cc_send_mail_template("community_communication.mail_template_announcement_published")

    def action_expire(self):
        self._cc_require_officer()
        self._cc_set_state("expired")

    def action_archive_record(self):
        self._cc_require_officer()
        self._cc_set_state("archived")

    def action_reset_draft(self):
        self._cc_require_officer()
        self._cc_set_state("draft")

    def action_acknowledge(self):
        self.ensure_one()
        if self.state != "published":
            raise UserError(_("Only published announcements can be acknowledged."))
        resident = self._cc_current_resident()
        existing = self.env["community.communication.announcement.ack"].search(
            [("announcement_id", "=", self.id), ("resident_id", "=", resident.id)],
            limit=1,
        )
        if existing:
            return True
        self.env["community.communication.announcement.ack"].create({
            "announcement_id": self.id,
            "resident_id": resident.id,
        })
        return True

    def action_log_view(self):
        self.ensure_one()
        resident = self.env.user.cc_resident_ids[:1]
        if not resident:
            return False
        View = self.env["community.communication.announcement.view"]
        if not View.search_count([
            ("announcement_id", "=", self.id),
            ("resident_id", "=", resident.id),
        ]):
            View.create({
                "announcement_id": self.id,
                "resident_id": resident.id,
            })
        return True

    @api.model
    def _cron_publish_and_expire(self):
        now = fields.Datetime.now()
        scheduled = self.search([
            ("state", "=", "scheduled"),
            ("date_publish", "<=", now),
        ])
        if scheduled:
            scheduled.action_publish()
        expired = self.search([
            ("state", "=", "published"),
            ("date_expiry", "!=", False),
            ("date_expiry", "<=", now),
        ])
        if expired:
            expired.action_expire()


class CommunityCommunicationAnnouncementView(models.Model):
    _name = "community.communication.announcement.view"
    _description = "Announcement View"
    _order = "viewed_on desc"

    announcement_id = fields.Many2one(
        "community.communication.announcement",
        required=True,
        ondelete="cascade",
        index=True,
    )
    resident_id = fields.Many2one(
        "community.communication.resident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    community_id = fields.Many2one(related="announcement_id.community_id", store=True, index=True)
    company_id = fields.Many2one(related="announcement_id.company_id", store=True, index=True)
    viewed_on = fields.Datetime(default=fields.Datetime.now, required=True)

    _announcement_resident_view_uniq = models.Constraint(
        "unique(announcement_id, resident_id)",
        "A resident can view an announcement only once for counting.",
    )


class CommunityCommunicationAnnouncementAck(models.Model):
    _name = "community.communication.announcement.ack"
    _description = "Announcement Acknowledgement"
    _order = "acked_on desc"

    announcement_id = fields.Many2one(
        "community.communication.announcement",
        required=True,
        ondelete="cascade",
        index=True,
    )
    resident_id = fields.Many2one(
        "community.communication.resident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    community_id = fields.Many2one(related="announcement_id.community_id", store=True, index=True)
    company_id = fields.Many2one(related="announcement_id.company_id", store=True, index=True)
    acked_on = fields.Datetime(default=fields.Datetime.now, required=True)

    _announcement_resident_ack_uniq = models.Constraint(
        "unique(announcement_id, resident_id)",
        "A resident can acknowledge an announcement only once.",
    )
