# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _


class AiCopilotConversation(models.Model):
    _name = "ai.copilot.conversation"
    _description = "AI Copilot Conversation"
    _order = "write_date desc, id desc"

    name = fields.Char(required=True, default="New conversation")
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    context_json = fields.Json(default=dict)
    message_ids = fields.One2many("ai.copilot.message", "conversation_id")
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        is_admin = self.env.su or self.env.user.has_group("ai_copilot.group_copilot_admin")
        for vals in vals_list:
            if not is_admin:
                vals["user_id"] = self.env.user.id
                vals["company_id"] = self.env.company.id
        return super().create(vals_list)


class AiCopilotMessage(models.Model):
    _name = "ai.copilot.message"
    _description = "AI Copilot Message"
    _order = "id"

    conversation_id = fields.Many2one(
        "ai.copilot.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role = fields.Selection(
        [("user", "User"), ("assistant", "Assistant")],
        required=True,
        default="user",
    )
    body = fields.Text(required=True)
    payload = fields.Json(default=dict)
    feedback = fields.Selection(
        [("none", "None"), ("up", "Helpful"), ("down", "Not helpful")],
        default="none",
        required=True,
    )
    user_id = fields.Many2one(related="conversation_id.user_id", store=True, index=True)
    company_id = fields.Many2one(related="conversation_id.company_id", store=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("ai_copilot.group_copilot_admin"):
            for vals in vals_list:
                if vals.get("role", "user") != "user":
                    raise AccessError(_("Only the Copilot service can store assistant replies."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group("ai_copilot.group_copilot_admin"):
            allowed = {"feedback"}
            if set(vals) - allowed:
                raise AccessError(_("You can only update feedback on a Copilot reply."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group("ai_copilot.group_copilot_admin"):
            raise UserError(_("Conversations are archived instead of deleting individual messages."))
        return super().unlink()
