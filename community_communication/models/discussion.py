# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

from .constants import DISCUSSION_CATEGORIES


class CommunityCommunicationDiscussion(models.Model):
    _name = "community.communication.discussion"
    _description = "Community Discussion"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.bound.mixin",
        "community.communication.attachment.mixin",
        "community.communication.state.mixin",
    ]
    _order = "is_pinned desc, last_activity_at desc, id desc"
    _rec_name = "title"
    _cc_state_transitions = {
        "active": {"resolved", "locked", "removed"},
        "resolved": {"active", "locked", "removed"},
        "locked": {"active", "removed"},
        "removed": set(),
    }

    title = fields.Char(required=True, tracking=True)
    body = fields.Html(sanitize=True)
    category = fields.Selection(DISCUSSION_CATEGORIES, required=True, default="general")
    state = fields.Selection(
        [
            ("active", "Active"),
            ("resolved", "Resolved"),
            ("locked", "Locked"),
            ("removed", "Removed"),
        ],
        default="active",
        required=True,
        index=True,
        tracking=True,
    )
    is_pinned = fields.Boolean()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "cc_discussion_attach_rel",
        "discussion_id",
        "attachment_id",
        string="Attachments",
    )
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    group_id = fields.Many2one(
        "community.communication.group",
        domain="[('community_id', '=', community_id)]",
        ondelete="set null",
        index=True,
    )
    comment_ids = fields.One2many(
        "community.communication.discussion.comment",
        "discussion_id",
        string="Comments",
    )
    comment_count = fields.Integer(compute="_compute_metrics", store=True)
    view_count = fields.Integer(default=0)
    last_activity_at = fields.Datetime(default=fields.Datetime.now, index=True)
    follow_ids = fields.One2many("community.communication.follow", "discussion_id")
    is_followed = fields.Boolean(compute="_compute_is_followed")
    support_count = fields.Integer(compute="_compute_reactions")
    oppose_count = fields.Integer(compute="_compute_reactions")

    @api.depends("comment_ids", "comment_ids.state")
    def _compute_metrics(self):
        for record in self:
            record.comment_count = len(record.comment_ids.filtered(lambda c: c.state == "active"))

    def _compute_is_followed(self):
        follows = self.env["community.communication.follow"].search([
            ("discussion_id", "in", self.ids),
            ("user_id", "=", self.env.uid),
        ])
        followed = set(follows.discussion_id.ids)
        for record in self:
            record.is_followed = record.id in followed

    def _compute_reactions(self):
        Reaction = self.env["community.communication.reaction"].sudo()
        for record in self:
            reactions = Reaction.search([
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ])
            record.support_count = len(reactions.filtered(lambda r: r.reaction_type == "support"))
            record.oppose_count = len(reactions.filtered(lambda r: r.reaction_type == "oppose"))

    def _touch_activity(self):
        self.sudo().write({"last_activity_at": fields.Datetime.now()})

    @api.model_create_multi
    def create(self, vals_list):
        officer = self.env.su or self.env.user._cc_is_community_officer()
        if not officer:
            for vals in vals_list:
                vals["author_id"] = self.env.uid
                vals["is_pinned"] = False
                vals["state"] = "active"
        return super().create(vals_list)

    def action_pin(self):
        self._cc_require_officer()
        self.write({"is_pinned": True})
        self._log_moderation("pin")

    def action_unpin(self):
        self._cc_require_officer()
        self.write({"is_pinned": False})
        self._log_moderation("unpin")

    def action_lock(self):
        self._cc_require_officer()
        self._cc_set_state("locked")
        self._log_moderation("lock")

    def action_unlock(self):
        self._cc_require_officer()
        self._cc_set_state("active")
        self._log_moderation("unlock")

    def action_resolve(self):
        self._cc_require_officer()
        self._cc_set_state("resolved")
        self._log_moderation("resolve")

    def action_remove(self):
        self._cc_require_officer()
        self._cc_set_state("removed")
        self._log_moderation("remove")

    def action_follow(self):
        Follow = self.env["community.communication.follow"]
        for record in self:
            if not Follow.search_count([
                ("discussion_id", "=", record.id),
                ("user_id", "=", self.env.uid),
            ]):
                Follow.create({"discussion_id": record.id, "user_id": self.env.uid})
        return True

    def action_unfollow(self):
        self.env["community.communication.follow"].search([
            ("discussion_id", "in", self.ids),
            ("user_id", "=", self.env.uid),
        ]).unlink()
        return True

    def action_react(self, reaction_type):
        self.ensure_one()
        if reaction_type not in ("support", "oppose"):
            raise UserError(_("Invalid reaction."))
        Reaction = self.env["community.communication.reaction"]
        existing = Reaction.search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("user_id", "=", self.env.uid),
        ], limit=1)
        if existing:
            existing.reaction_type = reaction_type
        else:
            Reaction.create({
                "res_model": self._name,
                "res_id": self.id,
                "user_id": self.env.uid,
                "reaction_type": reaction_type,
                "community_id": self.community_id.id,
            })
        return True

    def action_post_comment(self, body, parent_id=False):
        self.ensure_one()
        if self.state in ("locked", "removed"):
            raise UserError(_("This discussion is locked."))
        if not body or not str(body).strip():
            raise UserError(_("Write a reply before posting."))
        comment = self.env["community.communication.discussion.comment"].create({
            "discussion_id": self.id,
            "body": body,
            "parent_id": parent_id or False,
            "author_id": self.env.uid,
        })
        return comment.id

    def action_report(self, reason):
        self.ensure_one()
        text = (reason or "").strip()
        if not text:
            raise UserError(_("Please describe why you are reporting this discussion."))
        return self.env["community.communication.report"].sudo().create({
            "res_model": self._name,
            "res_id": self.id,
            "reason": text,
            "community_id": self.community_id.id,
            "reporter_id": self.env.uid,
        }).id

    def get_thread_payload(self):
        self.ensure_one()
        comments = self.comment_ids.filtered(lambda c: c.state == "active").sorted("create_date")
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body or "",
            "category": self.category,
            "state": self.state,
            "is_pinned": self.is_pinned,
            "is_followed": self.is_followed,
            "support_count": self.support_count,
            "oppose_count": self.oppose_count,
            "view_count": self.view_count,
            "comment_count": self.comment_count,
            "author": self.author_id.name,
            "can_moderate": self.env.user.has_group("community_communication.group_community_moderator"),
            "community_id": self.community_id.id,
            "attachment_ids": self.attachment_ids.ids,
            "comments": [{
                "id": comment.id,
                "body": comment.body or "",
                "author": comment.author_id.name,
                "parent_id": comment.parent_id.id,
                "date": fields.Datetime.to_string(comment.create_date),
                "is_admin": comment.author_id.has_group("community_communication.group_community_officer"),
            } for comment in comments],
        }

    def _log_moderation(self, action, note=False):
        logs = self.env["community.communication.moderation.log"]
        for record in self:
            logs.create({
                "res_model": record._name,
                "res_id": record.id,
                "action": action,
                "note": note,
                "actor_id": self.env.user.id,
                "community_id": record.community_id.id,
            })


class CommunityCommunicationDiscussionComment(models.Model):
    _name = "community.communication.discussion.comment"
    _description = "Discussion Comment"
    _inherit = "community.communication.state.mixin"
    _order = "create_date, id"
    _cc_state_transitions = {
        "active": {"removed"},
        "removed": set(),
    }

    discussion_id = fields.Many2one(
        "community.communication.discussion",
        required=True,
        ondelete="cascade",
        index=True,
    )
    parent_id = fields.Many2one(
        "community.communication.discussion.comment",
        ondelete="cascade",
        index=True,
    )
    child_ids = fields.One2many(
        "community.communication.discussion.comment",
        "parent_id",
        string="Replies",
    )
    body = fields.Html(required=True, sanitize=True)
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    state = fields.Selection(
        [("active", "Active"), ("removed", "Removed")],
        default="active",
        required=True,
    )
    community_id = fields.Many2one(
        related="discussion_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="discussion_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            for vals in vals_list:
                vals["author_id"] = self.env.uid
        records = super().create(vals_list)
        locked = records.discussion_id.filtered(lambda d: d.state in ("locked", "removed"))
        if locked:
            raise UserError(_("This discussion is locked."))
        records.discussion_id._touch_activity()
        return records

    @api.constrains("parent_id", "discussion_id")
    def _check_parent(self):
        for record in self:
            if record.parent_id and record.parent_id.discussion_id != record.discussion_id:
                raise ValidationError(_("Replies must belong to the same discussion."))

    def action_remove(self):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            if self.filtered(lambda rec: rec.author_id != self.env.user):
                raise AccessError(_("You can only remove your own comments."))
        self._cc_set_state("removed")


class CommunityCommunicationReaction(models.Model):
    _name = "community.communication.reaction"
    _description = "Community Reaction"
    _inherit = "community.communication.bound.mixin"

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    reaction_type = fields.Selection(
        [("support", "Support"), ("oppose", "Oppose")],
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
    )
    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        default=lambda self: self.env.user.cc_resident_ids[:1].community_id,
        index=True,
    )

    _sql_constraints = [
        (
            "reaction_user_uniq",
            "unique(res_model, res_id, user_id)",
            "A user can react only once to a given record.",
        ),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            for vals in vals_list:
                vals["user_id"] = self.env.uid
        return super().create(vals_list)


class CommunityCommunicationFollow(models.Model):
    _name = "community.communication.follow"
    _description = "Discussion Follow"

    discussion_id = fields.Many2one(
        "community.communication.discussion",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
    )
    community_id = fields.Many2one(
        related="discussion_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="discussion_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "follow_uniq",
            "unique(discussion_id, user_id)",
            "Already following this discussion.",
        ),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            for vals in vals_list:
                vals["user_id"] = self.env.uid
        return super().create(vals_list)


class CommunityCommunicationReport(models.Model):
    _name = "community.communication.report"
    _description = "Reported Content"
    _inherit = ["community.communication.bound.mixin", "community.communication.state.mixin"]
    _order = "create_date desc"
    _cc_state_transitions = {
        "pending": {"reviewed", "dismissed", "actioned"},
        "reviewed": {"actioned", "dismissed"},
        "dismissed": set(),
        "actioned": set(),
    }

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    reason = fields.Text(required=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("reviewed", "Reviewed"),
            ("dismissed", "Dismissed"),
            ("actioned", "Actioned"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    reporter_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    reviewer_id = fields.Many2one("res.users")

    def action_dismiss(self):
        self._cc_require_officer()
        self.write({"reviewer_id": self.env.uid})
        self._cc_set_state("dismissed")

    def action_mark_actioned(self):
        self._cc_require_officer()
        self.write({"reviewer_id": self.env.uid})
        self._cc_set_state("actioned")


class CommunityCommunicationModerationLog(models.Model):
    _name = "community.communication.moderation.log"
    _description = "Moderation History"
    _inherit = "community.communication.bound.mixin"
    _order = "create_date desc"

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    action = fields.Char(required=True)
    note = fields.Text()
    actor_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        index=True,
    )
