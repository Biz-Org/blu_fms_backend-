# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

from .constants import POLL_CATEGORIES


class CommunityCommunicationPoll(models.Model):
    _name = "community.communication.poll"
    _description = "Community Poll"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.audience.mixin",
        "community.communication.state.mixin",
    ]
    _order = "date_start desc, id desc"
    _rec_name = "question"
    _cc_state_transitions = {
        "draft": {"scheduled", "active", "closed"},
        "scheduled": {"active", "draft", "closed"},
        "active": {"closed"},
        "closed": set(),
    }

    question = fields.Char(required=True, tracking=True)
    description = fields.Text()
    category = fields.Selection(POLL_CATEGORIES, default="events", required=True)
    response_type = fields.Selection(
        [("single", "Single Choice"), ("multiple", "Multiple Choice")],
        default="single",
        required=True,
    )
    anonymous = fields.Boolean(string="Anonymous Voting")
    one_per_unit = fields.Boolean(string="Limit 1 Response / Unit")
    building_ids = fields.Many2many(
        "community.communication.building",
        "cc_poll_building_rel",
        "poll_id",
        "building_id",
        domain="[('community_id', '=', community_id)]",
    )
    audience_group_ids = fields.Many2many(
        "community.communication.group",
        "cc_poll_group_rel",
        "poll_id",
        "group_id",
        domain="[('community_id', '=', community_id)]",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("active", "Active"),
            ("closed", "Closed"),
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
    date_start = fields.Datetime(string="Start")
    date_end = fields.Datetime(string="End")
    option_ids = fields.One2many(
        "community.communication.poll.option",
        "poll_id",
        string="Options",
        copy=True,
    )
    vote_ids = fields.One2many(
        "community.communication.poll.vote",
        "poll_id",
        string="Votes",
    )
    participant_count = fields.Integer(compute="_compute_participant_count", store=True, compute_sudo=True)
    response_rate = fields.Float(compute="_compute_response_rate", compute_sudo=True)

    @api.depends("vote_ids")
    def _compute_participant_count(self):
        for record in self:
            record.participant_count = len(record.vote_ids)

    @api.depends("vote_ids", "community_id", "audience_type")
    def _compute_response_rate(self):
        for record in self:
            reach = len(record._cc_audience_resident_ids()) if record.community_id else 0
            record.response_rate = (record.participant_count / reach) if reach else 0.0

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_("Poll end must be after the start."))

    @api.constrains("option_ids")
    def _check_options_on_publish(self):
        for record in self:
            if record.state in ("active", "scheduled") and len(record.option_ids) < 2:
                raise ValidationError(_("A poll needs at least two options."))

    def action_schedule(self):
        self._cc_require_officer()
        for record in self:
            if not record.date_start:
                raise UserError(_("Set a start date before scheduling."))
            if len(record.option_ids) < 2:
                raise UserError(_("Add at least two options before scheduling."))
        self._cc_set_state("scheduled")

    def action_open(self):
        self._cc_require_officer()
        for record in self:
            if len(record.option_ids) < 2:
                raise UserError(_("Add at least two options before publishing."))
            if not record.date_start:
                record.date_start = fields.Datetime.now()
        self._cc_set_state("active")
        self._cc_send_mail_template("community_communication.mail_template_poll_opened")

    def action_close(self):
        self._cc_require_officer()
        self._cc_set_state("closed")

    def action_vote(self, option_ids):
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("This poll is not open for voting."))
        if self.date_end and self.date_end < fields.Datetime.now():
            raise UserError(_("This poll has closed."))
        option_records = self.option_ids.filtered(lambda o: o.id in option_ids)
        if not option_records:
            raise UserError(_("Select a valid option."))
        if self.response_type == "single" and len(option_records) != 1:
            raise UserError(_("Select exactly one option."))
        resident = self._cc_current_resident()
        Vote = self.env["community.communication.poll.vote"].sudo()
        if Vote.search_count([("poll_id", "=", self.id), ("voter_id", "=", resident.id)]):
            raise UserError(_("You have already voted in this poll."))
        if self.one_per_unit and resident.unit_id:
            if Vote.search_count([
                ("poll_id", "=", self.id),
                ("unit_id", "=", resident.unit_id.id),
            ]):
                raise UserError(_("This household has already voted."))
        Vote.create({
            "poll_id": self.id,
            "option_ids": [(6, 0, option_records.ids)],
            "voter_id": resident.id,
            "unit_id": resident.unit_id.id,
            "community_id": self.community_id.id,
        })
        return self.get_vote_payload()

    def get_vote_payload(self):
        self.ensure_one()
        resident = self.env.user.cc_resident_ids[:1]
        voted = False
        if resident:
            voted = bool(self.env["community.communication.poll.vote"].sudo().search_count([
                ("poll_id", "=", self.id),
                ("voter_id", "=", resident.id),
            ]))
        return {
            "id": self.id,
            "question": self.question,
            "description": self.description or "",
            "category": self.category,
            "state": self.state,
            "anonymous": self.anonymous,
            "response_type": self.response_type,
            "audience_type": self.audience_type,
            "date_end": fields.Datetime.to_string(self.date_end) if self.date_end else "",
            "has_voted": voted,
            "participant_count": self.participant_count,
            "options": [{
                "id": option.id,
                "name": option.name,
                "vote_count": option.vote_count,
                "vote_percent": int(round((option.vote_percent or 0.0) * 100)),
            } for option in self.option_ids],
        }

    @api.model
    def _cron_open_and_close(self):
        now = fields.Datetime.now()
        to_open = self.search([("state", "=", "scheduled"), ("date_start", "<=", now)])
        if to_open:
            to_open.action_open()
        to_close = self.search([
            ("state", "=", "active"),
            ("date_end", "!=", False),
            ("date_end", "<=", now),
        ])
        if to_close:
            to_close.action_close()


class CommunityCommunicationPollOption(models.Model):
    _name = "community.communication.poll.option"
    _description = "Poll Option"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    poll_id = fields.Many2one(
        "community.communication.poll",
        required=True,
        ondelete="cascade",
        index=True,
    )
    community_id = fields.Many2one(related="poll_id.community_id", store=True, index=True)
    company_id = fields.Many2one(related="poll_id.company_id", store=True, index=True)
    vote_count = fields.Integer(compute="_compute_vote_count", compute_sudo=True)
    vote_percent = fields.Float(compute="_compute_vote_count", compute_sudo=True)

    def _compute_vote_count(self):
        for option in self:
            votes = option.poll_id.vote_ids.filtered(lambda v: option in v.option_ids)
            option.vote_count = len(votes)
            total = len(option.poll_id.vote_ids)
            option.vote_percent = (len(votes) / total) if total else 0.0


class CommunityCommunicationPollVote(models.Model):
    _name = "community.communication.poll.vote"
    _description = "Poll Vote"
    _order = "voted_on desc"

    poll_id = fields.Many2one(
        "community.communication.poll",
        required=True,
        ondelete="cascade",
        index=True,
    )
    option_ids = fields.Many2many(
        "community.communication.poll.option",
        "cc_poll_vote_option_rel",
        "vote_id",
        "option_id",
        required=True,
    )
    voter_id = fields.Many2one(
        "community.communication.resident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    unit_id = fields.Many2one("community.communication.unit", index=True)
    voted_on = fields.Datetime(default=fields.Datetime.now, required=True)
    community_id = fields.Many2one(
        related="poll_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="poll_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "vote_voter_uniq",
            "unique(poll_id, voter_id)",
            "Each resident can vote only once in a poll.",
        ),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            resident = self.env.user.cc_resident_ids[:1]
            if not resident:
                raise ValidationError(_("No resident profile is linked to the current user."))
            for vals in vals_list:
                vals["voter_id"] = resident.id
                if resident.unit_id:
                    vals["unit_id"] = resident.unit_id.id
                poll = self.env["community.communication.poll"].browse(int(vals.get("poll_id") or 0))
                if not poll.exists() or poll.state != "active":
                    raise UserError(_("This poll is not open for voting."))
        return super().create(vals_list)
