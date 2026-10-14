# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

from .constants import GROUP_CATEGORIES


class CommunityCommunicationGroup(models.Model):
    _name = "community.communication.group"
    _description = "Community Group"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "community.communication.bound.mixin",
        "community.communication.state.mixin",
    ]
    _order = "name"
    _cc_state_transitions = {
        "active": {"archived"},
        "archived": {"active"},
    }

    name = fields.Char(required=True, tracking=True)
    description = fields.Html(sanitize=True)
    image_1920 = fields.Image()
    category = fields.Selection(GROUP_CATEGORIES, required=True, default="other")
    visibility = fields.Selection(
        [
            ("public", "Public"),
            ("restricted", "Restricted"),
            ("invite", "Invite-only"),
        ],
        default="public",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [("active", "Active"), ("archived", "Archived")],
        default="active",
        required=True,
        index=True,
        tracking=True,
    )
    member_ids = fields.One2many(
        "community.communication.group.member",
        "group_id",
        string="Members",
    )
    member_count = fields.Integer(compute="_compute_member_count", store=True)
    discussion_ids = fields.One2many(
        "community.communication.discussion",
        "group_id",
        string="Discussions",
    )

    @api.depends("member_ids.state")
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids.filtered(lambda m: m.state == "member"))

    def action_archive_record(self):
        self._cc_require_officer()
        self._cc_set_state("archived")

    def action_restore(self):
        self._cc_require_officer()
        self._cc_set_state("active")

    def action_join(self):
        self.ensure_one()
        resident = self._cc_current_resident()
        Member = self.env["community.communication.group.member"]
        existing = Member.search([
            ("group_id", "=", self.id),
            ("resident_id", "=", resident.id),
        ], limit=1)
        if self.visibility == "invite":
            raise UserError(_("This group is invite-only."))
        if existing:
            if existing.state == "member":
                raise UserError(_("You are already a member of this group."))
            if existing.state == "requested":
                raise UserError(_("Your join request is pending."))
            if existing.state == "left":
                existing.sudo().write({"role": "member"})
                existing.sudo()._cc_set_state("member" if self.visibility == "public" else "requested")
                return existing
        state = "member" if self.visibility == "public" else "requested"
        return Member.create({
            "group_id": self.id,
            "resident_id": resident.id,
            "state": state,
            "community_id": self.community_id.id,
        })

    def action_leave(self):
        self.ensure_one()
        resident = self._cc_current_resident()
        membership = self.member_ids.filtered(
            lambda m: m.resident_id == resident and m.state == "member"
        )
        if not membership:
            raise UserError(_("You are not a member of this group."))
        membership.action_leave()

    def action_add_member(self, resident_id):
        self.ensure_one()
        self._cc_require_officer()
        resident = self.env["community.communication.resident"].browse(int(resident_id))
        if not resident.exists():
            raise UserError(_("Select a resident to add."))
        if resident.community_id != self.community_id:
            raise ValidationError(_("Members must belong to the group's community."))
        Member = self.env["community.communication.group.member"]
        existing = Member.search([
            ("group_id", "=", self.id),
            ("resident_id", "=", resident.id),
        ], limit=1)
        if existing:
            if existing.state == "member":
                raise UserError(_("This resident is already a member."))
            existing.write({"role": "member"})
            existing._cc_set_state("member")
            return existing
        return Member.create({
            "group_id": self.id,
            "resident_id": resident.id,
            "role": "member",
            "state": "member",
        })


class CommunityCommunicationGroupMember(models.Model):
    _name = "community.communication.group.member"
    _description = "Community Group Member"
    _inherit = "community.communication.state.mixin"
    _rec_name = "resident_id"
    _cc_state_transitions = {
        "invited": {"member", "left"},
        "requested": {"member", "left"},
        "member": {"left"},
        "left": {"member", "requested", "invited"},
    }

    group_id = fields.Many2one(
        "community.communication.group",
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
    role = fields.Selection(
        [
            ("member", "Member"),
            ("moderator", "Moderator"),
            ("administrator", "Administrator"),
        ],
        default="member",
        required=True,
    )
    state = fields.Selection(
        [
            ("invited", "Invited"),
            ("requested", "Requested"),
            ("member", "Member"),
            ("left", "Left"),
        ],
        default="member",
        required=True,
        index=True,
    )
    community_id = fields.Many2one(
        related="group_id.community_id",
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="group_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    _group_resident_uniq = models.Constraint(
        "unique(group_id, resident_id)",
        "A resident can appear only once in a group.",
    )

    @api.constrains("resident_id", "group_id")
    def _check_same_community(self):
        for record in self:
            if record.resident_id.community_id != record.group_id.community_id:
                raise ValidationError(_("Members must belong to the group's community."))

    @api.model_create_multi
    def create(self, vals_list):
        officer = self.env.su or self.env.user._cc_is_community_officer()
        if not officer:
            resident = self.env.user.cc_resident_ids[:1]
            if not resident:
                raise ValidationError(_("No resident profile is linked to the current user."))
            for vals in vals_list:
                vals["resident_id"] = resident.id
                vals["role"] = "member"
                group = self.env["community.communication.group"].browse(int(vals.get("group_id") or 0))
                if not group.exists():
                    raise UserError(_("Select a valid group."))
                if group.visibility == "invite":
                    raise UserError(_("This group is invite-only."))
                if group.state != "active":
                    raise UserError(_("This group is not available."))
                if group.community_id != resident.community_id:
                    raise ValidationError(_("Members must belong to the group's community."))
                vals["state"] = "member" if group.visibility == "public" else "requested"
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            raise AccessError(_("Residents cannot manage group memberships directly."))
        return super().write(vals)

    def action_approve(self):
        self.env["community.communication.group"]._cc_require_officer()
        self._cc_set_state("member")

    def action_leave(self):
        if not self.env.su and not self.env.user._cc_is_community_officer():
            if self.filtered(lambda rec: rec.resident_id.user_id != self.env.user):
                raise UserError(_("You can only leave your own membership."))
        self.sudo()._cc_set_state("left")
