# -*- coding: utf-8 -*-

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .catalog import APP_LINKS, PROPOSAL_MODELS, SOURCES, SUGGESTIONS

PROVIDER_TIMEOUT = 25


class AiCopilotService(models.AbstractModel):
    _name = "ai.copilot.service"
    _inherit = "ai.copilot.retrieval"
    _description = "AI Copilot Service"

    @api.model
    def _check_user(self):
        if not self.env.user.has_group("ai_copilot.group_copilot_user"):
            raise AccessError(_("You are not allowed to use AI Copilot."))

    @api.model
    def _check_admin(self):
        self._check_user()
        if not self.env.user.has_group("ai_copilot.group_copilot_admin"):
            raise AccessError(_("Only an AI Copilot administrator can change this configuration."))

    @api.model
    def _config(self):
        return self.env["ai.copilot.config"].sudo()._ensure_config()

    @api.model
    def _provider_meta(self, config, used=False, error=""):
        return {
            "configured": bool(config._provider_ready()),
            "enabled": bool(config.enabled),
            "provider": config.provider,
            "label": dict(config._fields["provider"].selection).get(config.provider, config.provider),
            "model_name": config.model_name or "",
            "used": used,
            "error": error or "",
        }

    @api.model
    def _navigation(self):
        apps = []
        for xmlid, label, icon in APP_LINKS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu:
                continue
            visible = self.env["ir.ui.menu"].search_count([("id", "=", menu.id)])
            if not visible or not menu.action:
                continue
            apps.append({
                "id": menu.id,
                "label": label,
                "icon": icon,
                "action_id": menu.action.id,
            })
        return apps

    @api.model
    def _suggestions(self, context):
        module = (context or {}).get("module") or ""
        model_name = (context or {}).get("model") or ""
        if not module and model_name:
            for spec in SOURCES:
                if spec["model"] == model_name:
                    module = spec["module"]
                    break
        return SUGGESTIONS.get(module) or SUGGESTIONS["default"]

    @api.model
    def get_bootstrap(self, context=None):
        self._check_user()
        context = context or {}
        config = self._config()
        user = self.env.user
        return {
            "user_name": user.name,
            "company_name": self.env.company.name,
            "can_admin": user.has_group("ai_copilot.group_copilot_admin"),
            "provider": self._provider_meta(config),
            "suggestions": self._suggestions(context),
            "apps": self._navigation(),
            "context": {
                "model": context.get("model") or "",
                "res_id": context.get("res_id") or False,
                "module": context.get("module") or "",
            },
        }

    @api.model
    def _serialize_message(self, message):
        payload = message.payload or {}
        return {
            "id": message.id,
            "role": message.role,
            "body": message.body or "",
            "feedback": message.feedback,
            "payload": payload,
            "created": fields.Datetime.to_string(message.create_date),
        }

    @api.model
    def _serialize_conversation(self, conversation, with_messages=False):
        data = {
            "id": conversation.id,
            "name": conversation.name,
            "updated": fields.Datetime.to_string(conversation.write_date),
        }
        if with_messages:
            data["messages"] = [self._serialize_message(message) for message in conversation.message_ids]
        return data

    @api.model
    def list_conversations(self):
        self._check_user()
        conversations = self.env["ai.copilot.conversation"].search([("active", "=", True)], limit=40)
        return [self._serialize_conversation(conversation) for conversation in conversations]

    @api.model
    def get_conversation(self, conversation_id):
        self._check_user()
        conversation = self.env["ai.copilot.conversation"].browse(conversation_id).exists()
        if not conversation:
            raise AccessError(_("That conversation is not available to you."))
        return self._serialize_conversation(conversation, with_messages=True)

    @api.model
    def _owned_conversation(self, conversation_id, context):
        if conversation_id:
            conversation = self.env["ai.copilot.conversation"].browse(int(conversation_id)).exists()
            if not conversation:
                raise AccessError(_("That conversation is not available to you."))
            return conversation
        return self.env["ai.copilot.conversation"].create({
            "name": _("New conversation"),
            "context_json": {
                "screen_model": (context or {}).get("model") or "",
                "screen_res_id": (context or {}).get("res_id") or False,
            },
        })

    @api.model
    def ask(self, conversation_id, question, context=None):
        self._check_user()
        question = (question or "").strip()
        if not question:
            raise UserError(_("Enter a question."))
        if len(question) > 4000:
            raise UserError(_("Ask a shorter question (4000 characters or fewer)."))
        context = context or {}
        conversation = self._owned_conversation(conversation_id, context)
        self.env["ai.copilot.message"].create({
            "conversation_id": conversation.id,
            "role": "user",
            "body": question,
        })
        if conversation.name in (_("New conversation"), "New conversation"):
            conversation.write({"name": question[:80]})
        memory = conversation.context_json or {}
        try:
            retrieved = self.retrieve(question, context=context, memory=memory)
            provider_meta, answer = self._maybe_generate(retrieved)
            retrieved["provider"] = provider_meta
            if answer:
                retrieved.setdefault("sections", []).insert(0, {
                    "kind": "ai_summary",
                    "title": _("AI summary"),
                    "text": answer,
                })
            status = retrieved.get("status") or "ok"
            if status == "ok" and not provider_meta.get("configured"):
                retrieved["provider_note"] = _(
                    "This answer summarizes records you can access. A generative AI provider is not configured."
                )
            payload = {
                "status": status,
                "answer_kind": retrieved.get("answer_kind") or "fms_data",
                "sections": retrieved.get("sections") or [],
                "sources": retrieved.get("sources") or [],
                "recommendations": retrieved.get("recommendations") or [],
                "table": retrieved.get("table"),
                "stats": retrieved.get("stats"),
                "proposal": retrieved.get("proposal"),
                "provider": provider_meta,
                "provider_note": retrieved.get("provider_note") or "",
            }
            body = retrieved.get("answer") or _("No answer was produced.")
        except Exception as error:
            message = getattr(error, "name", None) or str(error)
            if isinstance(error, (AccessError, UserError)):
                raise
            payload = {
                "status": "error",
                "answer_kind": "fms_data",
                "sections": [],
                "sources": [],
                "recommendations": [],
                "table": None,
                "stats": None,
                "proposal": None,
                "provider": self._provider_meta(self._config(), error=message),
                "provider_note": "",
            }
            body = _("Something went wrong while preparing this answer.")
            retrieved = {"memory": memory}
        self.env["ai.copilot.message"].sudo().create({
            "conversation_id": conversation.id,
            "role": "assistant",
            "body": body,
            "payload": payload,
        })
        conversation.write({"context_json": retrieved.get("memory") or memory})
        sources = payload.get("sources") or []
        self.env["ai.copilot.audit"].create({
            "name": question[:80],
            "conversation_id": conversation.id,
            "question": question[:500],
            "status": payload.get("status"),
            "source_summary": ", ".join(
                "%s (%s)" % (source.get("label"), source.get("count")) for source in sources[:6]
            )[:240],
        })
        return self._serialize_conversation(conversation, with_messages=True)

    @api.model
    def _maybe_generate(self, retrieved):
        config = self._config()
        meta = self._provider_meta(config)
        if retrieved.get("status") not in ("ok", None):
            return meta, ""
        if not config._provider_ready():
            return meta, ""
        facts = retrieved.get("context_facts") or {}
        system = (
            "You are the facility management copilot. Answer only from the JSON context. "
            "Do not invent counts, names, dates, or records. If the context is insufficient, say so. "
            "Distinguish facility records, knowledge documents, and recommendations. "
            "Do not claim that an action was performed."
        )
        user_content = json.dumps({
            "question": facts.get("question"),
            "facts": facts.get("packs"),
            "knowledge": facts.get("knowledge"),
            "current_record": facts.get("current"),
            "draft_answer": retrieved.get("answer"),
            "recommendations": retrieved.get("recommendations"),
        }, default=str)[:12000]
        text, error = self._call_provider(config, [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ])
        meta = self._provider_meta(config, used=bool(text), error=error or "")
        return meta, text or ""

    @api.model
    def _call_provider(self, config, messages):
        try:
            base_url = self._validate_base_url(config.base_url or "https://api.openai.com/v1")
        except UserError as error:
            return "", str(error)
        url = base_url.rstrip("/") + "/chat/completions"
        body = json.dumps({
            "model": config.model_name or "gpt-4o-mini",
            "temperature": config.temperature or 0,
            "messages": messages,
        }).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": "Bearer %s" % (config.api_key or "").strip(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=PROVIDER_TIMEOUT) as response:
                data = json.loads(response.read().decode())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            return text.strip(), ""
        except urllib.error.HTTPError as error:
            return "", _("The AI provider returned an error (%s).") % error.code
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return "", _("The AI provider is unavailable.")

    @api.model
    def _validate_base_url(self, url):
        parsed = urlparse((url or "").strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "https" and host:
            return (url or "").strip().rstrip("/")
        if parsed.scheme == "http" and host in ("localhost", "127.0.0.1"):
            return (url or "").strip().rstrip("/")
        raise UserError(_("The AI provider URL must use HTTPS."))

    @api.model
    def set_feedback(self, message_id, value):
        self._check_user()
        if value not in ("up", "down", "none"):
            raise UserError(_("Unknown feedback value."))
        message = self.env["ai.copilot.message"].browse(message_id).exists()
        if not message or message.role != "assistant":
            raise AccessError(_("That reply is not available to you."))
        message.write({"feedback": value})
        return True

    @api.model
    def confirm_action(self, message_id):
        self._check_user()
        message = self.env["ai.copilot.message"].browse(message_id).exists()
        if not message:
            raise AccessError(_("That reply is not available to you."))
        payload = dict(message.payload or {})
        proposal = dict(payload.get("proposal") or {})
        if proposal.get("status") != "pending":
            raise UserError(_("There is no pending action to confirm."))
        model_name = proposal.get("model")
        if model_name not in PROPOSAL_MODELS:
            raise UserError(_("This action is not allowed."))
        if model_name not in self.env:
            raise UserError(_("%s is not installed.") % PROPOSAL_MODELS[model_name]["module"])
        model = self.env[model_name]
        if not model.has_access("create"):
            raise AccessError(_("You are not allowed to create this record."))
        vals = self._whitelist_vals(model, proposal.get("vals") or {})
        if not vals:
            raise UserError(_("The proposed action has no values to save."))
        record = model.create(vals)
        proposal["status"] = "done"
        proposal["res_id"] = record.id
        proposal["res_model"] = model_name
        proposal["result_label"] = record.display_name
        payload["proposal"] = proposal
        message.sudo().write({"payload": payload})
        self.env["ai.copilot.audit"].create({
            "name": _("Confirmed %s") % record.display_name,
            "conversation_id": message.conversation_id.id,
            "question": proposal.get("title"),
            "status": "confirmed",
            "source_summary": "%s,%s" % (model_name, record.id),
        })
        return {
            "res_model": model_name,
            "res_id": record.id,
            "label": record.display_name,
            "conversation": self._serialize_conversation(message.conversation_id, with_messages=True),
        }

    @api.model
    def _whitelist_vals(self, model, vals):
        allowed = {"name", "description", "category"}
        clean = {}
        for key, value in vals.items():
            if key in allowed and key in model._fields and isinstance(value, str):
                clean[key] = value
        return clean

    @api.model
    def cancel_action(self, message_id):
        self._check_user()
        message = self.env["ai.copilot.message"].browse(message_id).exists()
        if not message:
            raise AccessError(_("That reply is not available to you."))
        payload = dict(message.payload or {})
        proposal = dict(payload.get("proposal") or {})
        if proposal.get("status") != "pending":
            raise UserError(_("There is no pending action to cancel."))
        proposal["status"] = "cancelled"
        payload["proposal"] = proposal
        message.sudo().write({"payload": payload})
        return self._serialize_conversation(message.conversation_id, with_messages=True)

    @api.model
    def archive_conversation(self, conversation_id):
        self._check_user()
        conversation = self.env["ai.copilot.conversation"].browse(conversation_id).exists()
        if not conversation:
            raise AccessError(_("That conversation is not available to you."))
        conversation.write({"active": False})
        return True

    @api.model
    def get_settings(self):
        self._check_admin()
        config = self._config()
        return {
            "enabled": config.enabled,
            "provider": config.provider,
            "base_url": config.base_url or "",
            "model_name": config.model_name or "",
            "temperature": config.temperature,
            "api_key_set": bool((config.api_key or "").strip()),
        }

    @api.model
    def save_settings(self, values):
        self._check_admin()
        values = values or {}
        config = self._config()
        vals = {}
        if "enabled" in values:
            vals["enabled"] = bool(values["enabled"])
        if values.get("provider") in ("none", "openai", "compatible"):
            vals["provider"] = values["provider"]
        if "base_url" in values:
            url = (values.get("base_url") or "").strip()
            if url:
                vals["base_url"] = self._validate_base_url(url)
            else:
                vals["base_url"] = "https://api.openai.com/v1"
        if "model_name" in values:
            vals["model_name"] = (values.get("model_name") or "")[:120]
        if "temperature" in values:
            vals["temperature"] = float(values["temperature"])
        api_key = values.get("api_key")
        if isinstance(api_key, str) and api_key.strip() and api_key != "********":
            vals["api_key"] = api_key.strip()
        if values.get("clear_api_key"):
            vals["api_key"] = False
        config.write(vals)
        return self.get_settings()

    @api.model
    def list_documents(self):
        self._check_user()
        documents = self.env["ai.copilot.document"].search([("active", "=", True)], limit=80)
        return [{
            "id": document.id,
            "name": document.name,
            "category": document.category,
            "summary": document.summary or "",
            "restricted": document.restricted,
        } for document in documents]

    @api.model
    def save_document(self, values):
        self._check_admin()
        values = values or {}
        name = (values.get("name") or "").strip()
        body = (values.get("body") or "").strip()
        if not name or not body:
            raise UserError(_("A knowledge document needs a title and body."))
        category = values.get("category") or "internal"
        allowed = {key for key, _label in self.env["ai.copilot.document"]._fields["category"].selection}
        if category not in allowed:
            category = "internal"
        document = self.env["ai.copilot.document"].create({
            "name": name[:200],
            "category": category,
            "summary": (values.get("summary") or "")[:240],
            "body": body[:20000],
            "restricted": bool(values.get("restricted")),
        })
        return {"id": document.id, "name": document.name}
