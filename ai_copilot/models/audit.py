# -*- coding: utf-8 -*-

from odoo import fields, models


class AiCopilotAudit(models.Model):
    _name = "ai.copilot.audit"
    _description = "AI Copilot Audit"
    _order = "id desc"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    conversation_id = fields.Many2one("ai.copilot.conversation", ondelete="set null")
    question = fields.Char()
    status = fields.Char()
    source_summary = fields.Char()
