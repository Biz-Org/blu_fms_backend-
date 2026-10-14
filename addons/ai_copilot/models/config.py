# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


class AiCopilotConfig(models.Model):
    _name = "ai.copilot.config"
    _description = "AI Copilot Configuration"

    name = fields.Char(default="AI Copilot", required=True)
    enabled = fields.Boolean(
        default=True,
        help="When disabled, Copilot still searches authorized records but does not call a generative provider.",
    )
    provider = fields.Selection(
        [
            ("none", "Not configured"),
            ("openai", "OpenAI"),
            ("compatible", "OpenAI-compatible endpoint"),
        ],
        default="none",
        required=True,
    )
    base_url = fields.Char(
        string="API Base URL",
        default="https://api.openai.com/v1",
        help="Chat completions base URL. The API key stays on the server.",
    )
    model_name = fields.Char(string="Model", default="gpt-4o-mini")
    api_key = fields.Char(string="API Key", copy=False)
    temperature = fields.Float(default=0.2)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.constrains("temperature")
    def _check_temperature(self):
        for record in self:
            if record.temperature < 0 or record.temperature > 2:
                raise ValidationError(_("Temperature must be between 0 and 2."))

    @api.model
    def _ensure_config(self):
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({"name": "AI Copilot", "provider": "none"})
        return config

    def _provider_ready(self):
        self.ensure_one()
        return bool(self.enabled and self.provider != "none" and (self.api_key or "").strip())
