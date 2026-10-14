# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from .constants import NOTICE_CATEGORIES


class CommunityCommunicationNotice(models.Model):
    _name = "community.communication.notice"
    _description = "Community Notice"
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
        "published": {"archived"},
        "archived": {"draft"},
    }

    title = fields.Char(required=True, tracking=True)
    body = fields.Html(sanitize=True)
    category = fields.Selection(NOTICE_CATEGORIES, required=True, default="general")
    is_important = fields.Boolean(string="Important")
    is_pinned = fields.Boolean(string="Pinned")
    building_ids = fields.Many2many(
        "community.communication.building",
        "cc_notice_building_rel",
        "notice_id",
        "building_id",
        domain="[('community_id', '=', community_id)]",
    )
    audience_group_ids = fields.Many2many(
        "community.communication.group",
        "cc_notice_group_rel",
        "notice_id",
        "group_id",
        domain="[('community_id', '=', community_id)]",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "cc_notice_attach_rel",
        "notice_id",
        "attachment_id",
        string="Attachments",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
    )
    date_publish = fields.Datetime(index=True)
    date_expiry = fields.Datetime()

    @api.constrains("date_publish", "date_expiry")
    def _check_dates(self):
        for record in self:
            if record.date_publish and record.date_expiry and record.date_expiry < record.date_publish:
                raise ValidationError(_("Notice expiry must be after the publish date."))

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
            if not record.date_publish:
                record.date_publish = now
        self._cc_set_state("published")
        self._cc_send_mail_template("community_communication.mail_template_notice_published")

    def action_archive_record(self):
        self._cc_require_officer()
        self._cc_set_state("archived")

    @api.model
    def _cron_publish_and_archive(self):
        now = fields.Datetime.now()
        to_publish = self.search([
            ("state", "=", "scheduled"),
            ("date_publish", "<=", now),
        ])
        if to_publish:
            to_publish.action_publish()
        to_archive = self.search([
            ("state", "=", "published"),
            ("date_expiry", "!=", False),
            ("date_expiry", "<=", now),
        ])
        if to_archive:
            to_archive.action_archive_record()
