# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import FEEDBACK_CATEGORIES


class CommunityCommunicationFeedback(models.Model):
    _name = "community.communication.feedback"
    _description = "Resident Feedback"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.bound.mixin",
        "community.communication.attachment.mixin",
        "community.communication.state.mixin",
    ]
    _order = "create_date desc"
    _cc_state_transitions = {
        "submitted": {"in_progress", "closed"},
        "in_progress": {"resolved", "closed"},
        "resolved": {"closed", "in_progress"},
        "closed": set(),
    }

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "cc_feedback_attach_rel",
        "feedback_id",
        "attachment_id",
        string="Attachments",
    )
    subject = fields.Char(required=True, tracking=True)
    category = fields.Selection(FEEDBACK_CATEGORIES, required=True, default="other")
    description = fields.Html(sanitize=True)
    anonymous = fields.Boolean()
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("submitted", "Submitted"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
        default="submitted",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    resident_id = fields.Many2one(
        "community.communication.resident",
        ondelete="set null",
        index=True,
    )
    assignee_id = fields.Many2one("res.users", tracking=True)
    note_ids = fields.One2many(
        "community.communication.feedback.note",
        "feedback_id",
        string="Internal Notes",
    )
    response_ids = fields.One2many(
        "community.communication.feedback.response",
        "feedback_id",
        string="Responses",
    )

    @api.model_create_multi
    def create(self, vals_list):
        officer = self.env.su or self.env.user._cc_is_community_officer()
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code(
                    "community.communication.feedback"
                ) or "New"
            if not officer:
                vals.pop("state", None)
                vals.pop("assignee_id", None)
            if vals.get("anonymous"):
                vals["resident_id"] = False
            elif not officer or not vals.get("resident_id"):
                if self.env.user.cc_resident_ids:
                    vals["resident_id"] = self.env.user.cc_resident_ids[:1].id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            allowed = {"attachment_ids"}
            if set(vals) - allowed:
                raise AccessError(_("Residents cannot update feedback status or staff fields."))
            own = self.filtered(
                lambda rec: rec.resident_id.user_id == self.env.user or rec.create_uid == self.env.user
            )
            if own != self:
                raise AccessError(_("You can only update your own feedback."))
        return super().write(vals)

    def action_in_progress(self):
        self._cc_require_officer()
        self._cc_set_state("in_progress")
        self._cc_notify_resident()

    def action_resolve(self):
        self._cc_require_officer()
        self._cc_set_state("resolved")
        self._cc_notify_resident()

    def _cc_notify_resident(self):
        for record in self:
            partner = record.resident_id.partner_id
            if partner:
                record._cc_send_mail_template(
                    "community_communication.mail_template_feedback_status",
                    partners=partner,
                )

    def action_close(self):
        self._cc_require_officer()
        self._cc_set_state("closed")

    def action_reopen(self):
        self._cc_require_officer()
        self._cc_set_state("in_progress")

    def action_respond(self, body):
        self._cc_require_officer()
        if not body:
            raise UserError(_("Response text is required."))
        self.ensure_one()
        self.env["community.communication.feedback.response"].create({
            "feedback_id": self.id,
            "body": body,
            "author_id": self.env.user.id,
            "community_id": self.community_id.id,
        })
        if self.state == "submitted":
            self.action_in_progress()
        return True


class CommunityCommunicationFeedbackNote(models.Model):
    _name = "community.communication.feedback.note"
    _description = "Feedback Internal Note"
    _order = "create_date desc"

    feedback_id = fields.Many2one(
        "community.communication.feedback",
        required=True,
        ondelete="cascade",
        index=True,
    )
    body = fields.Text(required=True)
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
    )
    community_id = fields.Many2one(related="feedback_id.community_id", store=True, index=True)
    company_id = fields.Many2one(related="feedback_id.company_id", store=True, index=True)


class CommunityCommunicationFeedbackResponse(models.Model):
    _name = "community.communication.feedback.response"
    _description = "Feedback Resident Response"
    _order = "create_date desc"

    feedback_id = fields.Many2one(
        "community.communication.feedback",
        required=True,
        ondelete="cascade",
        index=True,
    )
    body = fields.Html(required=True, sanitize=True)
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
    )
    community_id = fields.Many2one(
        related="feedback_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="feedback_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
